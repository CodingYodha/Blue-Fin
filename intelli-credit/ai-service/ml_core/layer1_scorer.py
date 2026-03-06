from typing import List
from dataclasses import dataclass

@dataclass
class Layer1Result:
    score: float
    explanations: List[str]
    layer: str

def compute_layer1_score(raw: dict, sector_config: dict) -> Layer1Result:
    """
    Computes rule-based score anchored to RBI/CRISIL guidelines.
    Returns score out of 100 and a list of penalty/bonus explanations.
    """
    score = 100.0
    explanations = []

    # ── MODEL 1: FINANCIAL HEALTH (max 40 pts deducted from 40) ──────────────

    dscr = raw.get("DSCR", 0)
    dscr_ok = sector_config.get("dscr_ok", 0.0)
    dscr_good = sector_config.get("dscr_good", 0.0)

    if dscr < 1.0:
        score -= 25
        explanations.append(f"DSCR {dscr:.2f}x below 1.0x — severe debt service risk (-25pts) [RBI Prudential Norms]")
    elif dscr < dscr_ok:
        score -= 15
        explanations.append(f"DSCR {dscr:.2f}x below sector threshold {dscr_ok}x (-15pts) [RBI Prudential Norms]")
    elif dscr < dscr_good:
        score -= 5
        explanations.append(f"DSCR {dscr:.2f}x below sector good threshold {dscr_good}x (-5pts)")

    de = raw.get("Debt_to_Equity", 0)
    de_max = sector_config.get("de_max", 0.0)
    if de > de_max * 1.5:
        score -= 15
        explanations.append(f"D/E {de:.2f}x severely exceeds sector max {de_max}x (-15pts) [CRISIL Leverage Assessment]")
    elif de > de_max:
        score -= 8
        explanations.append(f"D/E {de:.2f}x exceeds sector max {de_max}x (-8pts) [CRISIL Leverage Assessment]")

    icr = raw.get("Interest_Coverage_Ratio", 0)
    if icr < 1.0:
        score -= 15
        explanations.append(f"ICR {icr:.2f}x below 1.0x — cannot cover interest (-15pts) [CRISIL SME Rating 2024]")
    elif icr < 2.0:
        score -= 10
        explanations.append(f"ICR {icr:.2f}x below 2.0x warning threshold (-10pts) [CRISIL SME Rating 2024]")

    cr = raw.get("Current_Ratio", 0)
    if cr < 1.0:
        score -= 10
        explanations.append(f"Current Ratio {cr:.2f}x below 1.0x — acute liquidity stress (-10pts) [RBI Working Capital Guidelines]")
    elif cr < 1.2:
        score -= 5
        explanations.append(f"Current Ratio {cr:.2f}x below 1.2x (-5pts) [RBI Working Capital Guidelines]")

    ebitda_m = raw.get("EBITDA_Margin", 0)
    ebitda_floor = sector_config.get("ebitda_floor", 0.0)
    if ebitda_m < 0:
        score -= 12
        explanations.append(f"EBITDA margin {ebitda_m*100:.1f}% negative — operating loss (-12pts)")
    elif ebitda_m < ebitda_floor:
        score -= 6
        explanations.append(f"EBITDA {ebitda_m*100:.1f}% below sector floor {ebitda_floor*100:.1f}% (-6pts)")

    npm = raw.get("Net_Profit_Margin", 0)
    if npm < 0:
        score -= 8
        explanations.append(f"Net profit margin negative ({npm*100:.1f}%) — net loss position (-8pts)")

    # ── MODEL 2: CREDIT BEHAVIOUR (max 30 pts) ────────────────────────────────

    gst_var = raw.get("GST_vs_Bank_Variance_Pct", 0)
    gst_var_normal = sector_config.get("gst_var_normal", 0.0)
    if gst_var > 0.40:
        score -= 15
        explanations.append(f"GST-Bank variance {gst_var*100:.1f}% — severe revenue quality concern (-15pts) [GSTN Circular]")
    elif gst_var > 0.25:
        score -= 10
        explanations.append(f"GST-Bank variance {gst_var*100:.1f}% exceeds 25% mandatory flag (-10pts) [GSTN Circular]")
    elif gst_var > gst_var_normal:
        score -= 4
        explanations.append(f"GST-Bank variance {gst_var*100:.1f}% above sector normal {gst_var_normal*100:.1f}% (-4pts)")

    itc_mismatch = raw.get("GSTR_2A_3B_ITC_Mismatch_Pct", 0)
    if itc_mismatch > 0.25:
        score -= 12
        explanations.append(f"ITC mismatch {itc_mismatch*100:.1f}% (lag-adjusted) — ITC fraud flag (-12pts) [CGST Act S.16]")
    elif itc_mismatch > 0.10:
        score -= 5
        explanations.append(f"ITC mismatch {itc_mismatch*100:.1f}% — moderate concern (-5pts)")

    if raw.get("Round_Trip_Transaction_Count", 0) > 0:
        score -= 10
        explanations.append(f"Round-trip transactions detected — circular trading signal (-10pts)")

    if raw.get("Historical_Defaults", 0) > 0:
        score -= 15
        explanations.append(f"Historical defaults on record — serious character concern (-15pts)")

    # ── MODEL 3: EXTERNAL RISK (max 20 pts) ───────────────────────────────────

    sentiment = raw.get("Sector_News_Sentiment", 0)
    if sentiment < -0.40:
        score -= 8
        explanations.append(f"Sector sentiment {sentiment:.2f} (HEADWIND) — elevated macro risk (-8pts)")

    if raw.get("Regulatory_Action_Flag", 0):
        score -= 6
        explanations.append(f"Active regulatory action in sector (-6pts)")

    # ── MODEL 4: TEXT / CHARACTER RISK (max 10 pts) ───────────────────────────

    if raw.get("NCLT_Active_Flag", 0):
        score -= 20  # sledgehammer — character risk, overrides everything
        explanations.append(f"ACTIVE NCLT petition — character risk CRITICAL (-20pts) [CRO override trigger]")

    if raw.get("SARFAESI_Action_Flag", 0):
        score -= 15
        explanations.append(f"SARFAESI action by a lender — severe distress signal (-15pts)")

    fraud_kw = raw.get("Fraud_Keywords_Count", 0)
    if fraud_kw > 0:
        score -= min(fraud_kw * 3, 12)
        explanations.append(f"{fraud_kw} ED/CBI/SFIO keyword(s) in news (-{min(fraud_kw*3,12)}pts)")

    if raw.get("DIN_Disqualification_Flag", 0):
        score -= 10
        explanations.append(f"Promoter DIN disqualification (MCA Section 164) (-10pts)")

    if raw.get("Auditor_Qualified_Opinion_Flag", 0):
        score -= 5
        explanations.append(f"Qualified auditor opinion — governance concern (-5pts)")

    if raw.get("Related_Party_Anomaly_Flag", 0):
        score -= 8
        explanations.append(f"Related-party transaction anomaly (Entity Graph) (-8pts)")

    # Clamp to [0, 100]
    score = max(0.0, min(100.0, score))

    return Layer1Result(
        score=round(score, 2),
        explanations=explanations,
        layer="layer1_rbi_crisil"
    )
