import json
import logging
from typing import Dict, Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from .context_assembler import CAMContext

logger = logging.getLogger(__name__)

COMPLIANCE_SYSTEM = """You are the Compliance Officer at an Indian bank credit committee.
Your role is to write the Legal, Governance, and External Risk sections of a Credit Appraisal Memo.

STRICT RULES:
1. Write only about legal proceedings, regulatory actions, governance red flags,
   related-party risks, and macro/sector conditions. Do NOT assess financial ratios.
2. Every legal finding must cite its exact source URL or case number.
   Format: [Source: {source_url} | Verified: entity match confirmed for {company_name} + {promoter}]
3. For REJECTED research findings (name collision false positives), you MUST note
   their existence and exclusion: 
   "[NOTE: {N} search results excluded — name collision detected. 
   Finding mentioned {common_name} but company name did not match {company_name}. 
   Excluded per V1 entity verification protocol.]"
4. Distinguish clearly between ACTIVE and HISTORICAL legal risk.
   Active NCLT petition = mandatory CRO alert. Historical = noted but not blocking.
5. Use Indian regulatory vocabulary correctly:
   NCLT (insolvency), SARFAESI (secured asset enforcement), ED (Enforcement Directorate),
   DRT (Debt Recovery Tribunal), SEBI (securities regulator), RBI (banking regulator),
   MCA Section 164 (director disqualification), CIBIL (credit bureau).
6. Related-party findings from the Entity Graph are primary evidence — cite the
   Annual Report note number AND the entity graph analysis as dual sources.
7. Never speculate about guilt. State findings factually. Use "flagged", "detected",
   "identified" — not "proves" or "confirms fraud".
8. ALWAYS return your output strictly as a JSON object, adhering exactly to the schema requested."""

def build_compliance_prompt(ctx: CAMContext) -> str:
    # Format verified findings
    findings_text = ""
    for i, f in enumerate(ctx.verified_findings, 1):
        findings_text += (
            f"  Finding {i}: {f.get('finding', 'Unknown')}\n"
            f"  Source: {f.get('source_url', 'Not available')}\n"
            f"  Confidence: {f.get('confidence', 'UNKNOWN')}\n\n"
        )

    # Format rejected findings (V1 fix — must be disclosed)
    rejected_text = ""
    if ctx.rejected_findings:
        rejected_text = f"\nEXCLUDED FINDINGS (name collision — V1 entity verification):\n"
        for f in ctx.rejected_findings:
            rejected_text += f"  - {f.get('finding', 'Unknown')} [EXCLUDED: company name mismatch]\n"

    # Format entity graph related-party data
    rpt_text = ""
    if ctx.related_party_flag:
        for rp in ctx.related_party_details:
            rpt_text += (
                f"  Entity: {rp.get('entity_name', 'Unknown')}\n"
                f"  Relationship: {rp.get('relationship', 'Unknown')}\n"
                f"  Transaction amount: ₹{rp.get('transaction_amount_crore', 0.0):.2f} Cr\n"
                f"  Source: {rp.get('source', 'Unknown')}\n\n"
            )

    # Format Layer 1 character/legal explanations
    legal_l1 = [e for e in ctx.layer1_explanations
                if any(kw in e for kw in ["NCLT","SARFAESI","DIN","auditor","Related","fraud","ED","CBI"])]

    # Format SHAP text signals
    shap_text = "Text Risk Signal drivers (ML model):\n"
    for driver in ctx.shap_by_model.get("text_signals", [])[:5]:
        direction = "↑ Risk" if driver.get("direction") == "risk_increasing" else "↓ Risk"
        shap_text += f"  {direction}: {driver.get('human_label', 'Unknown')} (SHAP: {driver.get('shap_value', 0):+.4f})\n"

    sentiment_label = ('HEADWIND' if ctx.sector_sentiment_score < -0.30 
                       else 'TAILWIND' if ctx.sector_sentiment_score > 0.30 
                       else 'NEUTRAL')

    related_party_anomaly_yes_no = "YES" if ctx.related_party_flag else "NO"
    din_disq_yes_no = "YES" if ctx.din_disqualification else "NO"
    din_details_str = f"  DIN details: {ctx.din_details}" if ctx.din_disqualification else ""
    gov_issues_yes_no = "YES" if ctx.governance_flag else "NO"
    sarf_action_yes_no = "YES" if ctx.sarfaesi_flag else "NO"
    auditor_opinion = "YES — " + ctx.auditor_qualification_text if ctx.auditor_qualified else "NO"
    going_concern_yes_no = "YES — CRITICAL" if ctx.going_concern else "NO"

    return f"""Write the LEGAL, GOVERNANCE, and EXTERNAL RISK sections of the Credit Appraisal Memo for:

COMPANY: {ctx.company_name} (CIN: {ctx.company_cin})
PROMOTERS: {', '.join(ctx.promoter_names)}
SECTOR: {ctx.sector}

ML CLASSIFICATION:
  Promoter Risk:   {ctx.promoter_risk}
  Litigation Risk: {ctx.litigation_risk}
  Sector Risk:     {ctx.sector_risk}
  Sector Sentiment Score: {ctx.sector_sentiment_score:.2f} ({sentiment_label})

ML TEXT RISK SCORE: {ctx.score_text:.1f}/10 pts
Layer 1 RBI/CRISIL character/legal findings:
{chr(10).join("  " + e for e in legal_l1) if legal_l1 else "  None triggered"}

{shap_text}

VERIFIED RESEARCH FINDINGS ({len(ctx.verified_findings)} confirmed, {len(ctx.rejected_findings)} excluded):
{findings_text if findings_text else "  No significant legal findings detected."}
{rejected_text}

ENTITY GRAPH ANALYSIS:
  Related-party anomaly flag: {related_party_anomaly_yes_no}
  {rpt_text if rpt_text else "  No related-party anomalies detected."}
  DIN disqualification flag: {din_disq_yes_no}
{din_details_str}
  Governance issues flag: {gov_issues_yes_no}
  SARFAESI action flag: {sarf_action_yes_no}

AUDITOR AND GOVERNANCE:
  Auditor qualified opinion: {auditor_opinion}
  Going concern flag: {going_concern_yes_no}
  Active litigation disclosures in Annual Report: {len(ctx.litigation_list)} cases
  {chr(10).join("  - " + str(l) for l in ctx.litigation_list[:5])}

EXISTING COVENANTS (from rag extraction):
  {chr(10).join("  - " + str(c) for c in ctx.covenant_terms) if ctx.covenant_terms else "  None identified"}

Write these sections:
1. Legal Risk Assessment
   - Active proceedings (NCLT, DRT, SARFAESI, criminal) with case numbers and sources
   - Historical proceedings (note and dismiss or flag as pattern)
   - Explicitly state: "{len(ctx.rejected_findings)} search results excluded due to name collision 
     (V1 entity verification protocol). These are not counted in risk assessment."
2. Promoter Integrity Assessment
   - DIN status, disqualification check
   - Director network and related-party connections (Entity Graph findings)
   - News-based character signals
3. Governance and Reporting Quality
   - Auditor opinion quality
   - Related-party transaction disclosure adequacy
   - Going concern assessment if flagged
4. External / Macro Risk Assessment
   - Sector sentiment score and what drives it
   - Regulatory environment for {ctx.sector}
   - Supply chain and commodity exposure
5. Compliance Summary: Promoter Integrity verdict (LOW / MEDIUM / HIGH RISK)

Every legal finding must cite source URL. Every entity graph finding must cite
both the Annual Report note number and Entity Graph Analysis as dual sources.

RETURN YOUR RESPONSE EXACTLY IN THIS JSON FORMAT:
{{
  "section": "compliance_assessment",
  "persona": "compliance_officer",
  "content": "<full text of Legal + Governance + External Risk sections>",
  "promoter_integrity_verdict": "HIGH RISK",
  "active_legal_proceedings": ["<case summary1>", "<case summary2>"],
  "excluded_findings_count": {len(ctx.rejected_findings)},
  "governance_flags": ["Related-party supplier detected", "Auditor qualified opinion"],
  "source_citations": [
    {{"claim": "Active NCLT case", "source": "https://...", "module": "Research Agent"}}
  ]
}}"""

async def run_compliance_persona(ctx: CAMContext) -> Dict[str, Any]:
    llm = ChatAnthropic(
        model_name="claude-3-5-sonnet-20240620",
        temperature=0.0,
        max_tokens=3000
    )
    
    prompt = build_compliance_prompt(ctx)
    messages = [
        SystemMessage(content=COMPLIANCE_SYSTEM),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = await llm.ainvoke(messages)
        content = response.content
        
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
            
        data = json.loads(json_str)
        return data
        
    except json.JSONDecodeError as je:
        logger.warning(f"Persona 2 Compliance Officer returned invalid JSON. Falling back to text wrap. Err: {je}")
        return {
            "section": "compliance_assessment",
            "persona": "compliance_officer",
            "content": response.content if 'response' in locals() else "LLM Generation Failed.",
            "promoter_integrity_verdict": "UNKNOWN",
            "active_legal_proceedings": [],
            "excluded_findings_count": len(ctx.rejected_findings),
            "governance_flags": ["Error blocked evaluation"],
            "source_citations": []
        }
    except Exception as e:
        logger.error(f"Compliance Persona completely failed: {e}")
        return {
            "section": "compliance_assessment",
            "persona": "compliance_officer",
            "content": f"Compliance assessment generation failed due to system error: {e}",
            "promoter_integrity_verdict": "ERROR",
            "active_legal_proceedings": [],
            "excluded_findings_count": len(ctx.rejected_findings),
            "governance_flags": ["System connectivity error"],
            "source_citations": []
        }
