from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd

from .layer1_scorer import Layer1Result
from .layer2_scorer import Layer2Result
from .model_loader import MLArtifacts

@dataclass
class CombinedScore:
    layer1_score: float
    layer2_score: float
    final_score: float
    deviation: float
    distribution_anomaly: bool
    anomaly_note: Optional[str]
    score_m1: float
    score_m2: float
    score_m3: float
    score_m4: float
    final_pd: float

@dataclass
class DecisionResult:
    decision: str
    loan_limit_crore: float
    interest_rate_pct: Optional[float]
    reason: str

@dataclass
class StressTestResult:
    scenarios: Dict[str, Any]
    structurally_fragile: bool

def combine_scores(
    l1: Layer1Result,
    l2: Layer2Result,
    sector_config: dict
) -> CombinedScore:

    l1_score = l1.score
    l2_score = l2.composite_score

    deviation = l2_score - l1_score

    if abs(deviation) > 15:
        # Distribution Anomaly detected — cap L2's adjustment to ±10 from L1
        capped_deviation = 10.0 * (1 if deviation > 0 else -1)
        final_score = l1_score + capped_deviation
        distribution_anomaly = True
        anomaly_note = (
            f"Distribution anomaly: L1 rule-based={l1_score:.1f}, "
            f"L2 LightGBM={l2_score:.1f} (deviation {deviation:+.1f}pts > 15pt cap). "
            f"L2 adjustment capped to {capped_deviation:+.1f}pts. "
            f"Final score anchored to RBI/CRISIL baseline."
        )
    else:
        # L1 and L2 agree — use L2 (more nuanced) as final
        final_score = l2_score
        distribution_anomaly = False
        anomaly_note = None

    final_score = round(max(0.0, min(100.0, final_score)), 2)

    return CombinedScore(
        layer1_score=l1_score,
        layer2_score=l2_score,
        final_score=final_score,
        deviation=round(deviation, 2),
        distribution_anomaly=distribution_anomaly,
        anomaly_note=anomaly_note,
        score_m1=l2.score_m1, 
        score_m2=l2.score_m2,
        score_m3=l2.score_m3, 
        score_m4=l2.score_m4,
        final_pd=l2.final_pd
    )

def make_decision(
    score: float,
    net_worth_crore: float,
    base_rate: float = 9.5
) -> DecisionResult:
    if score >= 75:
        limit = 2.0 * net_worth_crore
        rate = base_rate + 0.5
        decision = "APPROVE"
        reason = f"Strong credit profile. Score {score:.1f}/100."
    elif score >= 55:
        limit = 1.2 * net_worth_crore
        rate = base_rate + 1.5 + (100 - score) * 0.05
        decision = "CONDITIONAL"
        reason = f"Acceptable with conditions. Score {score:.1f}/100."
    else:
        limit = 0
        rate = None
        decision = "REJECT"
        reason = f"Credit risk exceeds threshold. Score {score:.1f}/100."

    return DecisionResult(
        decision=decision,
        loan_limit_crore=round(limit, 2),
        interest_rate_pct=round(rate, 2) if rate else None,
        reason=reason
    )

def run_stress_tests(
    raw_features: dict,
    artifacts: MLArtifacts,
    base_score: float,
    base_decision: str,
    sector_config: dict,
    X1: pd.DataFrame,
    X2: pd.DataFrame,
    X3: pd.DataFrame,
    X4: pd.DataFrame,
    l2_score_m1: float,
    l2_score_m2: float,
    l2_score_m3: float,
    l2_score_m4: float
) -> StressTestResult:

    results = {}

    # Scenario 1: Revenue Shock — Revenue growth -20%
    X1_s1 = X1.copy()
    X1_s1["Revenue_Growth_YoY"] = X1_s1["Revenue_Growth_YoY"] - 0.20
    pd_s1 = artifacts.model_1.predict_proba(X1_s1)[:, 1][0]
    score_s1_m1 = (1 - pd_s1) * 40
    score_s1 = score_s1_m1 + l2_score_m2 + l2_score_m3 + l2_score_m4
    dec_s1 = make_decision(score_s1, raw_features.get("net_worth_crore", 0))
    results["Revenue_Shock"] = {
        "scenario": "Revenue growth -20% (recession / demand destruction)",
        "stressed_score": round(score_s1, 2),
        "decision": dec_s1.decision,
        "flipped": dec_s1.decision != base_decision,
        "action": "Recommend escrow account + quarterly revenue monitoring"
    }

    # Scenario 2: Rate Hike +200bps — ICR ×0.75, DSCR ×0.88
    X1_s2 = X1.copy()
    X1_s2["Interest_Coverage_Ratio"] = X1_s2["Interest_Coverage_Ratio"] * 0.75
    X1_s2["DSCR"] = X1_s2["DSCR"] * 0.88
    dscr_val = X1_s2["DSCR"].iloc[0] if isinstance(X1_s2["DSCR"], pd.Series) else X1_s2["DSCR"]
    X1_s2["DSCR_vs_Sector_Threshold"] = dscr_val - sector_config.get("dscr_ok", 0.0)
    pd_s2 = artifacts.model_1.predict_proba(X1_s2)[:, 1][0]
    score_s2_m1 = (1 - pd_s2) * 40
    score_s2 = score_s2_m1 + l2_score_m2 + l2_score_m3 + l2_score_m4
    dec_s2 = make_decision(score_s2, raw_features.get("net_worth_crore", 0))
    results["Rate_Hike_200bps"] = {
        "scenario": "Interest rate +200bps (RBI tightening cycle)",
        "stressed_score": round(score_s2, 2),
        "decision": dec_s2.decision,
        "flipped": dec_s2.decision != base_decision,
        "action": "Recommend fixed rate covenant or hedging requirement"
    }

    # Scenario 3: GST Scrutiny — variance ×1.5 + scrutiny flag = 1
    X2_s3 = X2.copy()
    X2_s3["GST_vs_Bank_Variance_Pct"] = X2_s3["GST_vs_Bank_Variance_Pct"] * 1.5
    X2_s3["GST_Scrutiny_Notice_Flag"] = 1
    var_val = X2_s3["GST_vs_Bank_Variance_Pct"].iloc[0] if isinstance(X2_s3["GST_vs_Bank_Variance_Pct"], pd.Series) else X2_s3["GST_vs_Bank_Variance_Pct"]
    X2_s3["GST_Variance_Anomaly"] = int(var_val > 0.20)
    X2_s3["GST_Variance_Severe"] = int(var_val > 0.40)
    pd_s3 = artifacts.model_2.predict_proba(X2_s3)[:, 1][0]
    score_s3_m2 = (1 - pd_s3) * 30
    score_s3 = l2_score_m1 + score_s3_m2 + l2_score_m3 + l2_score_m4
    dec_s3 = make_decision(score_s3, raw_features.get("net_worth_crore", 0))
    results["GST_Scrutiny"] = {
        "scenario": "GST scrutiny (variance ×1.5 + notice issued)",
        "stressed_score": round(score_s3, 2),
        "decision": dec_s3.decision,
        "flipped": dec_s3.decision != base_decision,
        "action": "Recommend independent auditor certificate as condition precedent"
    }

    any_flip = any(v["flipped"] for v in results.values() if "flipped" in v)
    structurally_fragile = (
        base_decision in ["APPROVE", "CONDITIONAL"] and
        any(v["decision"] == "REJECT" for v in results.values() if "decision" in v)
    )

    results["_meta"] = {
        "base_score": base_score,
        "base_decision": base_decision,
        "structurally_fragile": structurally_fragile,
        "auto_covenants": structurally_fragile,
        "fragile_note": (
            "⚠ Structurally fragile: loan flips to REJECT under stress. "
            "Auto-covenant protection recommended." if structurally_fragile else None
        )
    }

    return StressTestResult(scenarios=results, structurally_fragile=structurally_fragile)
