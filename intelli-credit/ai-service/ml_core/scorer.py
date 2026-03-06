import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from .model_loader import load_artifacts, validate_feature_dataframe
from .feature_assembler import assemble_features
from .layer1_scorer import compute_layer1_score
from .layer2_scorer import compute_layer2_score
from .score_combiner import combine_scores, make_decision, run_stress_tests

from utils import validate_job_id

logger = logging.getLogger(__name__)

class ScoringResult(BaseModel):
    job_id: str
    layer1_score: float
    layer1_explanations: List[str]
    layer2_score: float
    distribution_anomaly: bool
    anomaly_note: Optional[str]
    final_score: float
    score_financial_health: float
    score_credit_behaviour: float
    score_external_risk: float
    score_text_signals: float
    pd_meta: float
    pd_m1: float
    pd_m2: float
    pd_m3: float
    pd_m4: float
    decision: str
    loan_limit_crore: float
    interest_rate_pct: Optional[float]
    decision_reason: str
    shap_drivers: List[Dict[str, Any]]
    shap_by_model: Dict[str, List[Dict[str, Any]]]
    stress_tests: Dict[str, Any]
    structurally_fragile: bool
    schema_warnings: List[str]
    databricks_backend: str
    sector: str
    scored_at: str

async def run_full_scoring(job_id: str) -> ScoringResult:
    validate_job_id(job_id)
    artifacts = load_artifacts()

    # Step 1: Assemble features from all upstream sources
    assembly = await assemble_features(job_id, artifacts)
    X1, X2, X3, X4 = assembly.X1, assembly.X2, assembly.X3, assembly.X4

    # Step 2: Validate feature DataFrames against schema
    X1, w1 = validate_feature_dataframe(X1, "model_1", artifacts)
    X2, w2 = validate_feature_dataframe(X2, "model_2", artifacts)
    X3, w3 = validate_feature_dataframe(X3, "model_3", artifacts)
    X4, w4 = validate_feature_dataframe(X4, "model_4", artifacts)
    all_warnings = assembly.assembly_warnings + w1 + w2 + w3 + w4

    # Step 3: Layer 1 — RBI/CRISIL rule-based score
    l1 = compute_layer1_score(assembly.raw_features, assembly.sector_config)

    # Step 4: Layer 2 — LightGBM inference + SHAP
    l2 = compute_layer2_score(X1, X2, X3, X4, artifacts, assembly.raw_features)

    # Step 5: Combine (V13 deviation cap)
    combined = combine_scores(l1, l2, assembly.sector_config)

    # Step 6: Decision
    decision = make_decision(combined.final_score, assembly.net_worth_crore)

    # Step 7: Stress tests
    stress = run_stress_tests(
        raw_features=assembly.raw_features, 
        artifacts=artifacts,
        base_score=combined.final_score, 
        base_decision=decision.decision,
        sector_config=assembly.sector_config, 
        X1=X1, X2=X2, X3=X3, X4=X4,
        l2_score_m1=l2.score_m1,
        l2_score_m2=l2.score_m2,
        l2_score_m3=l2.score_m3,
        l2_score_m4=l2.score_m4
    )

    result = ScoringResult(
        job_id=job_id,
        # Layer breakdown
        layer1_score=l1.score,
        layer1_explanations=l1.explanations,
        layer2_score=l2.composite_score,
        distribution_anomaly=combined.distribution_anomaly,
        anomaly_note=combined.anomaly_note,
        # Component scores
        final_score=combined.final_score,
        score_financial_health=l2.score_m1,
        score_credit_behaviour=l2.score_m2,
        score_external_risk=l2.score_m3,
        score_text_signals=l2.score_m4,
        # PD
        pd_meta=round(l2.final_pd, 4),
        pd_m1=round(l2.pd_m1, 4),
        pd_m2=round(l2.pd_m2, 4),
        pd_m3=round(l2.pd_m3, 4),
        pd_m4=round(l2.pd_m4, 4),
        # Decision
        decision=decision.decision,
        loan_limit_crore=decision.loan_limit_crore,
        interest_rate_pct=decision.interest_rate_pct,
        decision_reason=decision.reason,
        # SHAP
        shap_drivers=l2.shap_m1[:5] + l2.shap_m2[:3] + l2.shap_m3[:2] + l2.shap_m4[:3],
        shap_by_model={
            "financial_health": l2.shap_m1,
            "credit_behaviour": l2.shap_m2,
            "external_risk": l2.shap_m3,
            "text_signals": l2.shap_m4
        },
        # Stress
        stress_tests=stress.scenarios,
        structurally_fragile=stress.structurally_fragile,
        # Meta
        schema_warnings=all_warnings,
        databricks_backend=assembly.raw_features.get("_backend", "unknown"),
        sector=assembly.sector,
        scored_at=datetime.utcnow().isoformat()
    )

    # Write to shared volume (V11 pattern)
    import os
    out_dir = f"/tmp/intelli-credit/{job_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/scoring_result.json"
    with open(out_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)

    return result
