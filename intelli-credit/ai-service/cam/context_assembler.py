import os
import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from ml_core.model_loader import get_sector_config

logger = logging.getLogger(__name__)

@dataclass
class CAMContext:
    # Identity
    company_name: str
    company_cin: str
    sector: str
    promoter_names: List[str]
    loan_amount_requested: float

    # ML Scores
    final_score: float
    layer1_score: float
    ml_decision: str
    loan_limit_crore: float
    interest_rate_pct: float
    pd_meta: float
    score_financial: float
    score_behaviour: float
    score_external: float
    score_text: float
    distribution_anomaly: bool
    anomaly_note: Optional[str]
    structurally_fragile: bool
    fragile_note: Optional[str]
    layer1_explanations: List[str]
    shap_by_model: dict
    stress_summary: dict

    # Financials
    financial_figures: dict
    revenue_growth_pct: float
    dscr_vs_threshold_note: str

    # Qualitative
    auditor_qualified: bool
    auditor_qualification_text: str
    going_concern: bool
    litigation_list: List[dict]
    covenant_terms: List[dict]
    collateral_items: List[dict]
    current_rating: str
    rating_action: str
    rating_rationale: str

    # Entity graph
    related_party_flag: int
    related_party_details: List[dict]
    din_disqualification: int
    governance_flag: int
    sarfaesi_flag: int

    # Research
    promoter_risk: str
    litigation_risk: str
    sector_risk: str
    sector_sentiment_score: float
    key_findings: List[dict]
    verified_findings: List[dict]
    rejected_findings: List[dict]
    active_legal_cases: List[dict]

    # Officer notes
    officer_notes_text: str
    officer_notes_adj: dict
    officer_notes_officer: str
    injection_detected: bool

    # Meta
    job_id: str
    sector_config: dict
    databricks_backend: str

def _safe_load(filepath: str, default_val: Any = None) -> Any:
    if default_val is None:
        default_val = {}
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed loading {filepath}: {e}")
    return default_val

def _cf(fin_dict: dict, key: str, period: str = None) -> dict:
    # Handles retrieving values and structure confidence badges
    # Returns {value, confidence, source_page, source_section, original_unit}
    default_resp = {
        "value": 0.0,
        "confidence": "LOW",
        "source_page": None,
        "source_section": None,
        "original_unit": None
    }
    
    node = fin_dict.get(key)
    if not node:
        return default_resp
    
    if period:
        node = node.get(period)
        if not node:
            return default_resp
            
    # Assuming the underlying extraction returns `[value, confidence, ...]` structure natively
    # If it's a raw scalar, adapt appropriately.
    if isinstance(node, dict) and "value" in node:
        return {
            "value": float(node.get("value", 0.0)),
            "confidence": node.get("confidence", "LOW"),
            "source_page": node.get("source_page"),
            "source_section": node.get("source_section"),
            "original_unit": node.get("original_unit")
        }
    else:
        # Fallback if raw scalar
        try:
            return {**default_resp, "value": float(node), "confidence": "MEDIUM"}
        except (TypeError, ValueError):
            return default_resp

async def assemble_cam_context(job_id: str) -> CAMContext:
    base = f"/tmp/intelli-credit/{job_id}"

    scoring  = _safe_load(os.path.join(base, "scoring_result.json"))
    rag      = _safe_load(os.path.join(base, "rag_extraction.json"))
    entity   = _safe_load(os.path.join(base, "entity_fraud_flags.json"))
    research = _safe_load(os.path.join(base, "research_agent_summary.json"))
    ocr      = _safe_load(os.path.join(base, "ocr_output.json"))

    officer_notes_path = os.path.join(base, "officer_notes.json")
    officer_notes = _safe_load(officer_notes_path)

    # COMPANY IDENTITY
    company_name    = ocr.get("entity_extraction", {}).get("company_name", "Unknown")
    company_cin     = ocr.get("entity_extraction", {}).get("cin", "")
    sector          = ocr.get("entity_extraction", {}).get("industry", "")
    promoter_names  = ocr.get("entity_extraction", {}).get("promoters", [])
    try:
        loan_amount_requested = float(ocr.get("loan_amount_crore", 0.0))
    except:
        loan_amount_requested = 0.0
        
    sector_config = get_sector_config(sector)

    # ML SCORING OUTPUTS
    final_score           = scoring.get("final_score", 0.0)
    layer1_score          = scoring.get("layer1_score", 0.0)
    layer2_score          = scoring.get("layer2_score", 0.0)
    ml_decision           = scoring.get("decision", "REJECT")
    loan_limit_crore      = scoring.get("loan_limit_crore", 0.0)
    interest_rate_pct     = scoring.get("interest_rate_pct", 0.0)
    pd_meta               = scoring.get("pd_meta", 1.0)
    score_financial       = scoring.get("score_financial_health", 0.0)
    score_behaviour       = scoring.get("score_credit_behaviour", 0.0)
    score_external        = scoring.get("score_external_risk", 0.0)
    score_text            = scoring.get("score_text_signals", 0.0)
    distribution_anomaly  = scoring.get("distribution_anomaly", False)
    anomaly_note          = scoring.get("anomaly_note")
    structurally_fragile  = scoring.get("structurally_fragile", False)
    stress_tests          = scoring.get("stress_tests", {})
    layer1_explanations   = scoring.get("layer1_explanations", [])
    shap_by_model         = scoring.get("shap_by_model", {})

    # FINANCIAL DATA
    fin = rag.get("financial_summary", {})
    financial_figures = {
        "revenue_crore":       _cf(fin, "revenue", "fy_current"),
        "revenue_prev_crore":  _cf(fin, "revenue", "fy_previous"),
        "ebitda_crore":        _cf(fin, "ebitda", "fy_current"),
        "pat_crore":           _cf(fin, "pat", "fy_current"),
        "total_debt_crore":    _cf(fin, "total_debt"),
        "net_worth_crore":     _cf(fin, "net_worth"),
        "dscr":                _cf(fin, "dscr"),
        "debt_to_equity":      _cf(fin, "debt_to_equity"),
        "interest_coverage":   _cf(fin, "interest_coverage_ratio"),
        "current_ratio":       _cf(fin, "current_ratio"),
        "ebitda_margin_pct":   _cf(fin, "ebitda_margin"),
    }

    # QUALITATIVE SIGNALS
    qs = rag.get("qualitative_signals", {})
    auditor_qualified     = qs.get("auditor_qualification", {}).get("has_qualification", False)
    auditor_qualification_text = qs.get("auditor_qualification", {}).get("qualification_text", "")
    going_concern         = qs.get("going_concern_flag", False)
    litigation_list       = qs.get("litigation_disclosures", [])
    covenant_terms        = rag.get("covenant_and_collateral", {}).get("covenants", [])
    collateral_items      = rag.get("covenant_and_collateral", {}).get("collateral", [])
    rating_action         = rag.get("rating_intelligence", {}).get("rating_action", "")
    rating_rationale      = rag.get("rating_intelligence", {}).get("rationale_summary", "")
    current_rating        = rag.get("rating_intelligence", {}).get("current_rating", "NR")

    # ENTITY GRAPH FINDINGS
    related_party_flag    = entity.get("related_party_anomaly_flag", 0)
    related_party_details = entity.get("related_party_details", [])
    din_disqualification  = entity.get("din_disqualification_flag", 0)
    din_details           = entity.get("din_details", {})
    governance_flag       = entity.get("governance_issues_flag", 0)
    sarfaesi_flag         = entity.get("sarfaesi_action_flag", 0)
    fraud_risk_score      = entity.get("entity_fraud_risk_score", 0)

    # RESEARCH AGENT FINDINGS
    promoter_risk         = research.get("promoter_risk", "UNKNOWN")
    litigation_risk       = research.get("litigation_risk", "UNKNOWN")
    sector_risk           = research.get("sector_risk", "UNKNOWN")
    sector_sentiment_score = research.get("sector_sentiment_score", 0.0)
    key_findings          = research.get("key_findings", [])
    verified_findings     = research.get("verified_findings", [])
    rejected_findings     = research.get("rejected_findings", [])
    databricks_backend    = scoring.get("databricks_backend", "unknown")

    # OFFICER NOTES
    officer_notes_text    = officer_notes.get("notes_text", "")
    officer_notes_adj     = officer_notes.get("score_adjustments", {})
    officer_notes_officer = officer_notes.get("officer_id", "")
    injection_detected    = officer_notes.get("injection_detected", False)

    # DERIVED SUMMARY FIELDS
    try:
        prev_rev = financial_figures["revenue_prev_crore"]["value"]
        curr_rev = financial_figures["revenue_crore"]["value"]
        revenue_growth_pct = round(
            (curr_rev - prev_rev) / max(prev_rev, 0.001) * 100, 1
        )
    except Exception:
        revenue_growth_pct = 0.0

    dscr_ok_val = float(sector_config.get("dscr_ok", 0.0))
    dscr_val = float(financial_figures["dscr"]["value"])
    above_below = 'BELOW' if dscr_val < dscr_ok_val else 'ABOVE'
    dscr_vs_threshold_note = (
        f"DSCR {dscr_val:.2f}x vs "
        f"sector threshold {dscr_ok_val}x "
        f"({above_below})"
    )

    active_legal_cases = [
        f for f in verified_findings 
        if "NCLT" in f.get("finding", "").upper()
    ]

    stress_summary = {
        k: v for k, v in stress_tests.items() if not k.startswith("_")
    }
    fragile_note = stress_tests.get("_meta", {}).get("fragile_note", None)

    return CAMContext(
        company_name=company_name,
        company_cin=company_cin,
        sector=sector,
        promoter_names=promoter_names,
        loan_amount_requested=loan_amount_requested,
        final_score=final_score,
        layer1_score=layer1_score,
        ml_decision=ml_decision,
        loan_limit_crore=loan_limit_crore,
        interest_rate_pct=interest_rate_pct,
        pd_meta=pd_meta,
        score_financial=score_financial,
        score_behaviour=score_behaviour,
        score_external=score_external,
        score_text=score_text,
        distribution_anomaly=distribution_anomaly,
        anomaly_note=anomaly_note,
        structurally_fragile=structurally_fragile,
        fragile_note=fragile_note,
        layer1_explanations=layer1_explanations,
        shap_by_model=shap_by_model,
        stress_summary=stress_summary,
        financial_figures=financial_figures,
        revenue_growth_pct=revenue_growth_pct,
        dscr_vs_threshold_note=dscr_vs_threshold_note,
        auditor_qualified=auditor_qualified,
        auditor_qualification_text=auditor_qualification_text,
        going_concern=going_concern,
        litigation_list=litigation_list,
        covenant_terms=covenant_terms,
        collateral_items=collateral_items,
        current_rating=current_rating,
        rating_action=rating_action,
        rating_rationale=rating_rationale,
        related_party_flag=related_party_flag,
        related_party_details=related_party_details,
        din_disqualification=din_disqualification,
        governance_flag=governance_flag,
        sarfaesi_flag=sarfaesi_flag,
        promoter_risk=promoter_risk,
        litigation_risk=litigation_risk,
        sector_risk=sector_risk,
        sector_sentiment_score=sector_sentiment_score,
        key_findings=key_findings,
        verified_findings=verified_findings,
        rejected_findings=rejected_findings,
        active_legal_cases=active_legal_cases,
        officer_notes_text=officer_notes_text,
        officer_notes_adj=officer_notes_adj,
        officer_notes_officer=officer_notes_officer,
        injection_detected=injection_detected,
        job_id=job_id,
        sector_config=sector_config,
        databricks_backend=databricks_backend
    )
