import joblib
import json
import os
import logging
import hashlib
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)

# Default to the local ml_core/models directory if not specified
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_DIR = os.environ.get("MODEL_DIR", DEFAULT_MODEL_DIR)

@dataclass
class MLArtifacts:
    model_1: object        # CalibratedClassifierCV — Financial Health
    model_2: object        # CalibratedClassifierCV — Credit Behaviour
    model_3: object        # CalibratedClassifierCV — External Risk
    model_4: object        # CalibratedClassifierCV — Text Signals
    meta_model: object     # LogisticRegression — Ensemble PD
    encoder_sector: object # LabelEncoder
    encoder_rating: object # LabelEncoder
    encoder_regulatory: object  # LabelEncoder
    industry_config: dict  # 15 sectors + DEFAULT thresholds
    feature_schema: dict   # exact feature lists per model
    lgbm_booster_1: object # raw LightGBM booster for SHAP (extracted from calibrated)
    lgbm_booster_2: object
    lgbm_booster_3: object
    lgbm_booster_4: object
    # RobustScalers fitted during training — required for accurate inference
    # None if ML engineer hasn't saved them yet (graceful fallback in feature_assembler)
    scaler_financial: object | None  # fitted RobustScaler for M1 numeric columns
    scaler_behaviour: object | None  # fitted RobustScaler for M2 numeric columns
    scaler_industry:  object | None  # fitted RobustScaler for M3 numeric columns
    scaler_text:      object | None  # fitted RobustScaler for M4 numeric columns

_artifacts: MLArtifacts | None = None

def _safe_load_model(filepath: str) -> object:
    """Load a joblib model file with path validation."""
    real_path = os.path.realpath(filepath)
    real_model_dir = os.path.realpath(MODEL_DIR)
    if not real_path.startswith(real_model_dir + os.sep) and real_path != real_model_dir:
        raise ValueError(f"Model path escapes MODEL_DIR: {filepath}")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Model file not found: {filepath}")
    return joblib.load(filepath)


def load_artifacts() -> MLArtifacts:
    global _artifacts
    if _artifacts is not None:
        return _artifacts

    logger.info(f"Loading ML artifacts from {MODEL_DIR}...")
    
    # Load primary models
    model_1 = _safe_load_model(os.path.join(MODEL_DIR, "model_1_financial_health.pkl"))
    model_2 = _safe_load_model(os.path.join(MODEL_DIR, "model_2_credit_behaviour.pkl"))
    model_3 = _safe_load_model(os.path.join(MODEL_DIR, "model_3_external_risk.pkl"))
    model_4 = _safe_load_model(os.path.join(MODEL_DIR, "model_4_text_signals.pkl"))
    meta_model = _safe_load_model(os.path.join(MODEL_DIR, "meta_model_aggregator.pkl"))
    
    # Load encoders
    encoder_sector = _safe_load_model(os.path.join(MODEL_DIR, "encoder_sector.pkl"))
    encoder_rating = _safe_load_model(os.path.join(MODEL_DIR, "encoder_rating.pkl"))
    encoder_regulatory = _safe_load_model(os.path.join(MODEL_DIR, "encoder_regulatory.pkl"))
    
    # Load configs
    with open(os.path.join(MODEL_DIR, "industry_config.json"), "r") as f:
        industry_config = json.load(f)
        
    with open(os.path.join(MODEL_DIR, "feature_schema.json"), "r") as f:
        feature_schema = json.load(f)

    # Extract raw LightGBM boosters from CalibratedClassifierCV for SHAP
    lgbm_booster_1 = model_1.calibrated_classifiers_[0].estimator.booster_
    lgbm_booster_2 = model_2.calibrated_classifiers_[0].estimator.booster_
    lgbm_booster_3 = model_3.calibrated_classifiers_[0].estimator.booster_
    lgbm_booster_4 = model_4.calibrated_classifiers_[0].estimator.booster_

    # Load scalers with graceful fallback
    def load_optional(path):
        if os.path.exists(path):
            return _safe_load_model(path)
        logger.warning(f"Optional artifact not found: {path} — will use fallback")
        return None

    scaler_fin  = load_optional(os.path.join(MODEL_DIR, "scaler_financial.pkl"))
    scaler_beh  = load_optional(os.path.join(MODEL_DIR, "scaler_behaviour.pkl"))
    scaler_ind  = load_optional(os.path.join(MODEL_DIR, "scaler_industry.pkl"))
    scaler_text = load_optional(os.path.join(MODEL_DIR, "scaler_text.pkl"))

    _artifacts = MLArtifacts(
        model_1=model_1,
        model_2=model_2,
        model_3=model_3,
        model_4=model_4,
        meta_model=meta_model,
        encoder_sector=encoder_sector,
        encoder_rating=encoder_rating,
        encoder_regulatory=encoder_regulatory,
        industry_config=industry_config,
        feature_schema=feature_schema,
        lgbm_booster_1=lgbm_booster_1,
        lgbm_booster_2=lgbm_booster_2,
        lgbm_booster_3=lgbm_booster_3,
        lgbm_booster_4=lgbm_booster_4,
        scaler_financial=scaler_fin,
        scaler_behaviour=scaler_beh,
        scaler_industry=scaler_ind,
        scaler_text=scaler_text
    )
    
    logger.info("ML artifacts loaded successfully")
    return _artifacts

def validate_feature_dataframe(df: pd.DataFrame, model_name: str, artifacts: MLArtifacts):
    """
    Validates that df has exactly the columns the model expects (from feature_schema.json).
    On missing columns: imputes with 0 (binary flags) or column median (continuous).
    On extra columns: drops silently.
    Logs a WARNING for every missing feature — these warnings appear in API response.
    Returns: (validated_df, list_of_warnings)
    """
    expected = artifacts.feature_schema[f"{model_name}_features"]
    warnings = []

    for col in expected:
        if col not in df.columns:
            # Determine imputation: if column name ends with _Flag, _flag, _Binary → 0
            # Otherwise → 0.0 (continuous missing features imputed to 0 not median
            # because we don't have population statistics at inference time)
            df[col] = 0.0 if not any(col.endswith(s) for s in ["_Flag", "_flag", "_Binary"]) else 0
            warnings.append(f"MISSING FEATURE: {col} imputed with 0 for {model_name}")
            logger.warning(f"Schema mismatch: {col} missing for {model_name}, imputed 0")

    # Reorder columns to exact training order
    df = df[expected]
    return df, warnings

def get_sector_config(sector: str, artifacts: MLArtifacts) -> dict:
    """Returns industry thresholds. Falls back to DEFAULT if sector unknown."""
    return artifacts.industry_config.get(sector, artifacts.industry_config.get("DEFAULT", {}))
