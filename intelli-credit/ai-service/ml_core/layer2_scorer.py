import logging
import shap
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from dataclasses import dataclass

from .model_loader import MLArtifacts

logger = logging.getLogger(__name__)

@dataclass
class Layer2Result:
    score_m1: float
    score_m2: float
    score_m3: float
    score_m4: float
    composite_score: float
    final_pd: float
    pd_m1: float
    pd_m2: float
    pd_m3: float
    pd_m4: float
    shap_m1: List[Dict[str, Any]]
    shap_m2: List[Dict[str, Any]]
    shap_m3: List[Dict[str, Any]]
    shap_m4: List[Dict[str, Any]]
    layer: str

HUMAN_LABELS = {
    # M1 Financial Health
    "DSCR_Stress_Margin":         lambda r: f"DSCR {r.get('DSCR',0):.2f}x (sector threshold {r.get('dscr_ok',0):.2f}x)",
    "DSCR_vs_Sector_Threshold":   lambda r: f"DSCR delta vs sector: {r.get('DSCR',0)-r.get('dscr_ok',0):+.2f}x",
    "Net_Profit_Margin":          lambda r: f"Net Profit Margin {r.get('Net_Profit_Margin',0)*100:.1f}%",
    "EBITDA_Margin":              lambda r: f"EBITDA Margin {r.get('EBITDA_Margin',0)*100:.1f}%",
    "Current_Ratio":              lambda r: f"Current Ratio {r.get('Current_Ratio',0):.2f}x",
    "Debt_to_Equity":             lambda r: f"Debt/Equity {r.get('Debt_to_Equity',0):.2f}x",
    "Interest_Coverage_Ratio":    lambda r: f"Interest Coverage {r.get('Interest_Coverage_Ratio',0):.2f}x",
    "Revenue_Growth_YoY":         lambda r: f"Revenue YoY Growth {r.get('Revenue_Growth_YoY',0)*100:.1f}%",
    "Rating_Score":               lambda r: f"Rating Score {r.get('Rating_Score',0):.0f}",
    "Financial_Risk_Score":       lambda r: f"Composite Financial Risk Score elevated",
    
    # M2 Credit Behaviour
    "GST_Filing_Delay_Days":      lambda r: f"GST filing delay {r.get('GST_Filing_Delay_Days',0):.0f} days",
    "GST_vs_Bank_Variance_Pct":   lambda r: f"GST-Bank Variance {r.get('GST_vs_Bank_Variance_Pct',0)*100:.1f}%",
    "ITC_Mismatch_Fraud_Flag":    lambda r: f"ITC mismatch {r.get('GSTR_2A_3B_ITC_Mismatch_Pct',0)*100:.1f}%",
    "Payment_Delays_Days":        lambda r: f"Payment Delays {r.get('Payment_Delays_Days',0):.0f} days",
    "Rating_Downgrade_Flag":      lambda r: f"Rating downgrade history: {r.get('Rating_Downgrades_Count',0)} downgrades",
    "Round_Trip_Transaction_Count": lambda r: f"Round-trip transactions: {r.get('Round_Trip_Transaction_Count',0)}",
    "Historical_Defaults":        lambda r: f"Historical defaults: {r.get('Historical_Defaults',0)}",
    "GST_Variance_vs_Sector":     lambda r: f"GST Variance vs Sector {r.get('GST_Variance_vs_Sector',0)*100:.1f}%",
    "Tax_Compliance_Score":       lambda r: f"Tax Compliance {r.get('Tax_Compliance_Score',0):.1f}/100",
    "Behaviour_Risk_Score":       lambda r: f"Composite Behaviour Risk Score elevated",
    "Beh_Anomaly_Score":          lambda r: "Anomaly score elevated — multiple behavioural risk signals",
    
    # M3 External Risk
    "Negative_News_Sentiment":    lambda r: f"Sector/news sentiment {r.get('Sector_News_Sentiment',0):.2f}",
    "Industry_Growth_Rate":       lambda r: f"Industry Growth {r.get('Industry_Growth_Rate',0)*100:.1f}%",
    "Sector_Volatility_Beta":     lambda r: f"Sector Volatility {r.get('Sector_Volatility_Beta',0):.2f}",
    "Supply_Chain_Risk_Score":    lambda r: f"Supply chain risk score {r.get('Supply_Chain_Risk_Score',0):.0f}/100",
    "Commodity_Exposure_Index":   lambda r: f"Commodity Exposure Index {r.get('Commodity_Exposure_Index',0):.2f}",
    "Industry_Risk_Score":        lambda r: f"Composite Industry Risk Score elevated",
    "Ind_Anomaly_Score":          lambda r: "Anomaly score elevated — multiple external risk signals",
    
    # M4 Text / Character Risk
    "Character_Risk_Score":       lambda r: "Composite character risk score elevated",
    "Text_Anomaly_Score":         lambda r: "Anomaly score elevated — multiple character risk signals",
    "Auditor_Qualified_Opinion_Flag": lambda r: "Qualified auditor opinion on file",
    "Litigation_Count":           lambda r: f"Active Litigations: {r.get('Litigation_Count',0)}",
    "NCLT_Active_Flag":           lambda r: "ACTIVE NCLT petition detected",
    "SARFAESI_Action_Flag":       lambda r: "SARFAESI lender action detected",
    "Fraud_Keywords_Count":       lambda r: f"Fraud keywords matched ({r.get('Fraud_Keywords_Count',0)})",
    "DIN_Disqualification_Flag":  lambda r: "Promoter DIN disqualification flagged",
    "Related_Party_Anomaly_Flag": lambda r: "Related-party transaction anomaly flagged",
    "Promoter_Disputes_Flag":     lambda r: "Promoter disputes flagged",
    "Governance_Issues_Flag":     lambda r: "Governance issues flagged"
}

def build_human_label(feat: str, raw: dict, model: str) -> str:
    fn = HUMAN_LABELS.get(feat)
    return fn(raw) if fn else feat.replace("_", " ")

def compute_layer2_score(
    X1: pd.DataFrame, 
    X2: pd.DataFrame, 
    X3: pd.DataFrame, 
    X4: pd.DataFrame,
    artifacts: MLArtifacts,
    raw_features: dict
) -> Layer2Result:

    # ── Run the 4 sub-models ─────────────────────────────────────────────────

    pd_m1 = artifacts.model_1.predict_proba(X1)[:, 1][0]
    pd_m2 = artifacts.model_2.predict_proba(X2)[:, 1][0]
    pd_m3 = artifacts.model_3.predict_proba(X3)[:, 1][0]
    pd_m4 = artifacts.model_4.predict_proba(X4)[:, 1][0]

    score_m1 = round((1 - pd_m1) * 40, 2)   # Financial Health  (0–40)
    score_m2 = round((1 - pd_m2) * 30, 2)   # Credit Behaviour  (0–30)
    score_m3 = round((1 - pd_m3) * 20, 2)   # External Risk     (0–20)
    score_m4 = round((1 - pd_m4) * 10, 2)   # Text Signals      (0–10)

    composite = score_m1 + score_m2 + score_m3 + score_m4

    # ── Meta-model ensemble PD ───────────────────────────────────────────────

    X_meta = np.array([[pd_m1, pd_m2, pd_m3, pd_m4, composite]])
    final_pd = float(artifacts.meta_model.predict_proba(X_meta)[:, 1][0])

    # ── SHAP Explainability ──────────────────────────────────────────────────
    
    def get_shap_values(booster, X: pd.DataFrame, model_name: str) -> list:
        try:
            explainer = shap.TreeExplainer(booster)
            shap_values = explainer.shap_values(X)
            
            # TreeExplainer generally returns a list [neg_class, pos_class]
            if isinstance(shap_values, list):
                sv = shap_values[1][0]
            else:
                sv = shap_values[0]
                
            features = X.columns.tolist()
            shap_ranked = sorted(
                zip(features, sv),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:10]  # top 10 drivers
            
            return [
                {
                    "feature": feat,
                    "shap_value": round(float(val), 4),
                    "direction": "risk_increasing" if val > 0 else "risk_decreasing",
                    "human_label": build_human_label(feat, raw_features, model_name)
                }
                for feat, val in shap_ranked
            ]
        except Exception as e:
            logger.warning(f"SHAP failed for {model_name}: {e}")
            return []

    shap_m1 = get_shap_values(artifacts.lgbm_booster_1, X1, "financial_health")
    shap_m2 = get_shap_values(artifacts.lgbm_booster_2, X2, "credit_behaviour")
    shap_m3 = get_shap_values(artifacts.lgbm_booster_3, X3, "external_risk")
    shap_m4 = get_shap_values(artifacts.lgbm_booster_4, X4, "text_signals")

    return Layer2Result(
        score_m1=score_m1, score_m2=score_m2,
        score_m3=score_m3, score_m4=score_m4,
        composite_score=composite,
        final_pd=final_pd,
        pd_m1=pd_m1, pd_m2=pd_m2, pd_m3=pd_m3, pd_m4=pd_m4,
        shap_m1=shap_m1, shap_m2=shap_m2,
        shap_m3=shap_m3, shap_m4=shap_m4,
        layer="layer2_lightgbm"
    )
