import json
import logging
from typing import Dict, Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from .context_assembler import CAMContext

logger = logging.getLogger(__name__)

ACCOUNTANT_SYSTEM = """You are a Senior Forensic Accountant at an Indian bank credit committee.
Your role is to write the Financial Assessment section of a Credit Appraisal Memo (CAM).

STRICT RULES:
1. Write only about financial data, ratios, trends, and fraud signals.
   Do NOT comment on legal cases, promoter character, or make a final credit recommendation.
2. Every single factual claim MUST end with a source citation in square brackets.
   Format: [Source: {document_name}, {section_name}, Page {N}]
   For computed ratios: [Source: Computed from Annual Report FY{year} financials]
   For fraud signals: [Source: Go Service fraud analysis, {specific data source}]
3. Flag every financial figure with its confidence level:
   HIGH CONFIDENCE — figure matches Go service extraction within 5%
   LOW CONFIDENCE — discrepancy >5% detected, manual verification required
4. Use ₹ symbol and crore denomination for all Indian amounts.
5. Write in formal banking language. Present tense for current state.
6. If a figure is missing or null, state "Not available — manual extraction required."
   Never invent or estimate financial figures.
7. Use industry-aware benchmarks — compare every ratio against the sector threshold,
   not a generic threshold. The sector config is provided.
8. ALWAYS return your output strictly as a JSON object, adhering exactly to the schema requested."""

def build_accountant_prompt(ctx: CAMContext) -> str:
    # Build financial figures section with confidence badges
    figures_text = ""
    for field, data in ctx.financial_figures.items():
        if not isinstance(data, dict):
            continue
        conf_badge = "✅ HIGH CONFIDENCE" if data.get("confidence") == "HIGH" else "⚠ LOW CONFIDENCE — manual verification required"
        val = data.get('value', 0.0)
        src_sec = data.get('source_section', 'Unknown')
        src_pg = data.get('source_page', 'Unknown')
        figures_text += (
            f"  {field}: ₹{val:.2f} Cr "
            f"[Source: {src_sec}, Page {src_pg}] "
            f"[{conf_badge}]\n"
        )

    # Build SHAP drivers text for M1 and M2
    shap_text = "Top financial risk drivers (ML model feature importance):\n"
    for driver in ctx.shap_by_model.get("financial_health", [])[:5]:
        direction = "↑ Risk increased" if driver.get("direction") == "risk_increasing" else "↓ Risk reduced"
        shap_text += f"  {direction}: {driver.get('human_label', 'Unknown')} (SHAP: {driver.get('shap_value', 0):+.4f})\n"
    for driver in ctx.shap_by_model.get("credit_behaviour", [])[:3]:
        direction = "↑ Risk increased" if driver.get("direction") == "risk_increasing" else "↓ Risk reduced"
        shap_text += f"  {direction}: {driver.get('human_label', 'Unknown')} (SHAP: {driver.get('shap_value', 0):+.4f})\n"

    # Build stress test table
    stress_text = "Stress Test Results:\n"
    for scenario, result in ctx.stress_summary.items():
        if not isinstance(result, dict):
             continue
        flip_note = " ⚠ DECISION FLIPS TO REJECT" if result.get("flipped") else ""
        stress_text += (
            f"  {scenario}: Score {ctx.final_score:.1f} → {result.get('stressed_score', 0):.1f} "
            f"({result.get('decision', 'UNKNOWN')}){flip_note}\n"
            f"  Recommended action if approved: {result.get('action', 'None')}\n"
        )
    if ctx.structurally_fragile:
        stress_text += f"\n  ⚠ STRUCTURALLY FRAGILE: {ctx.fragile_note}\n"

    # Build layer 1 explanations relevant to finance
    l1_financials = [
        e for e in ctx.layer1_explanations 
        if any(kw in e for kw in ["DSCR","ICR","Current","EBITDA","D/E","revenue","GST","ITC","variance"])
    ]
    formatted_l1 = "\n".join("  " + e for e in l1_financials) if l1_financials else "  None identified."

    going_concern_warn = "⚠ GOING CONCERN FLAG raised by auditor" if ctx.going_concern else ""
    auditor_warn = f"⚠ AUDITOR QUALIFICATION: {ctx.auditor_qualification_text}" if ctx.auditor_qualified else ""

    dscr_ok = ctx.sector_config.get('dscr_ok', 0.0)
    dscr_good = ctx.sector_config.get('dscr_good', 0.0)
    de_max = ctx.sector_config.get('de_max', 0.0)
    ebitda_floor = ctx.sector_config.get('ebitda_floor', 0.0)
    gst_var_normal = ctx.sector_config.get('gst_var_normal', 0.0)

    return f"""Write the FINANCIAL ASSESSMENT section of the Credit Appraisal Memo for:

COMPANY: {ctx.company_name} (CIN: {ctx.company_cin})
SECTOR: {ctx.sector}
LOAN REQUESTED: ₹{ctx.loan_amount_requested:.2f} Cr

SECTOR-SPECIFIC THRESHOLDS (use these, not generic benchmarks):
  DSCR acceptable: {dscr_ok}x (good: {dscr_good}x)
  D/E maximum: {de_max}x
  EBITDA floor: {ebitda_floor*100:.1f}%
  GST-Bank variance normal: {gst_var_normal*100:.1f}%

FINANCIAL FIGURES (with source citations and confidence):
{figures_text}

DERIVED ANALYSIS:
  Revenue trend: {ctx.revenue_growth_pct:+.1f}% YoY
  {ctx.dscr_vs_threshold_note}
  {going_concern_warn}
  {auditor_warn}

ML FINANCIAL HEALTH SCORE: {ctx.score_financial:.1f}/40 pts
ML CREDIT BEHAVIOUR SCORE: {ctx.score_behaviour:.1f}/30 pts
Layer 1 RBI/CRISIL rule-based findings:
{formatted_l1}

{shap_text}

{stress_text}

Current Credit Rating: {ctx.current_rating}
Rating Action: {ctx.rating_action}
Rating Agency Rationale Summary: {ctx.rating_rationale}

Write the Financial Assessment section. Structure it with these sub-sections:
1. Revenue and Profitability Analysis
2. Debt Service Capacity (DSCR, ICR — compared against {ctx.sector} sector thresholds)
3. Leverage and Capital Structure
4. Liquidity Position
5. GST and Transaction Behaviour Analysis (fraud signal section)
6. Credit Rating and Trend
7. Stress Test Findings
8. Financial Risk Summary (1 paragraph synthesising the above)

Every factual claim must include a source citation. Every financial figure must
include a confidence badge. Flag every below-threshold ratio with its exact
deviation from the sector benchmark.

RETURN YOUR RESPONSE EXACTLY IN THIS JSON FORMAT:
{{
  "section": "financial_assessment",
  "persona": "forensic_accountant",
  "content": "<full text of Financial Assessment section with newlines>",
  "source_citations": [
    {{"claim": "DSCR of 1.28x", "source": "Annual Report FY2024, P&L Statement, Page 47", "module": "RAG Extraction"}}
  ],
  "confidence_flags": [
    {{"figure": "revenue_crore", "confidence": "HIGH", "value": 41.2}}
  ],
  "key_financial_risks": ["<1-line summary of each major risk found>"]
}}"""

async def run_accountant_persona(ctx: CAMContext) -> Dict[str, Any]:
    llm = ChatAnthropic(
        model_name="claude-3-5-sonnet-20240620",
        temperature=0.0,
        max_tokens=3000
    )
    
    prompt = build_accountant_prompt(ctx)
    messages = [
        SystemMessage(content=ACCOUNTANT_SYSTEM),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = await llm.ainvoke(messages)
        content = response.content
        
        # Try finding JSON boundaries if response contains markdown formatting
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
            
        data = json.loads(json_str)
        return data
        
    except json.JSONDecodeError as je:
        logger.warning(f"Persona 1 returned invalid JSON. Falling back to plain text wrap. Err: {je}")
        return {
            "section": "financial_assessment",
            "persona": "forensic_accountant",
            "content": response.content if 'response' in locals() else "LLM Generation Failed.",
            "source_citations": [],
            "confidence_flags": [],
            "key_financial_risks": []
        }
    except Exception as e:
        logger.error(f"Accountant Persona completely failed: {e}")
        return {
            "section": "financial_assessment",
            "persona": "forensic_accountant",
            "content": "Forensic accounting generation failed due to a system error.",
            "source_citations": [],
            "confidence_flags": [],
            "key_financial_risks": ["Error blocked evaluation"]
        }
