"""
RAG Extractor — Claude-based structured extraction from retrieved chunks.

=============================================================================
ARCHITECTURE DOC: Section 5 (RAG Pipeline) — Final Extraction Layer

This is the last step of the RAG pipeline. It produces the JSON that feeds
LightGBM for credit scoring.

V4 FIX — Cross-Verification:
  The Go service extracts financial figures deterministically from PDF coords.
  Claude extracts the SAME figures from RAG-retrieved text.
  If they agree (within 5%) → HIGH_CONFIDENCE
  If they disagree (>5%)   → LOW_CONFIDENCE flag, Go's value used as primary.
  Claude returns null rather than guess — never hallucinate.

Extraction Functions:
  1. extract_financial_summary()     → revenue, EBITDA, debt, etc.
  2. extract_qualitative_signals()   → auditor notes, litigation, management
  3. extract_covenant_and_collateral() → covenants, collateral items
  4. extract_rating_intelligence()   → rating, outlook, strengths/weaknesses

Orchestrator:
  run_full_extraction()              → runs all 4, writes rag_extraction.json
=============================================================================
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from anthropic import AsyncAnthropic

from model_config import CLAUDE_RAG_EXTRACTION_MODEL
from .retriever import retrieve_for_extraction, format_chunks_for_prompt

logger = logging.getLogger("rag.extractor")

# Shared volume base path
_BASE_PATH = Path("/tmp/intelli-credit")


# =============================================================================
# System prompt — shared across all extraction calls
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = (
    "You are a financial data extraction engine for Indian corporate credit assessment.\n"
    "You will receive text chunks retrieved from financial documents "
    "(Annual Reports, Rating Reports, Legal Notices).\n"
    "Each chunk is labeled with its source: document type, page number, and section name.\n\n"
    "EXTRACTION RULES — follow these exactly:\n"
    "1. Extract ONLY figures that are explicitly stated in the provided text. "
    "Do NOT calculate, infer, or estimate.\n"
    "2. If a figure is not present in the text, return null for that field. Never guess.\n"
    "3. Return every numeric value with its EXACT column header as it appears in the document.\n"
    "4. If a year label is ambiguous or uncertain (e.g. merged cell, unclear header), return null.\n"
    "5. Indian amounts: normalize all values to Crores in your output.\n"
    "   - If stated in Lakhs: divide by 100. State original_unit as \"Lakhs\".\n"
    "   - If stated in Crores: use as-is. State original_unit as \"Crores\".\n"
    "   - If stated in Thousands: divide by 10000. State original_unit as \"Thousands\".\n"
    "6. For every extracted figure, include the source citation:\n"
    "   source_page: int, source_section: str — copy these from the [SOURCE:] label above the chunk.\n"
    "7. Return ONLY valid JSON. No explanation, no preamble, no markdown code fences."
)


# =============================================================================
# User prompts — one per extraction function
# =============================================================================

_FINANCIAL_SUMMARY_PROMPT = """\
Extract the following from the provided financial document chunks.
Return ONLY valid JSON matching this exact structure:
{
  "revenue": {
    "fy_current": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null},
    "fy_previous": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null},
    "fy_two_years_ago": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null}
  },
  "ebitda": {
    "fy_current": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null},
    "fy_previous": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null}
  },
  "pat": {
    "fy_current": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null},
    "fy_previous": {"value": null, "year_label": null, "original_unit": null, "source_page": null, "source_section": null}
  },
  "total_debt": {"value": null, "as_of_date": null, "original_unit": null, "source_page": null, "source_section": null},
  "net_worth": {"value": null, "as_of_date": null, "original_unit": null, "source_page": null, "source_section": null},
  "current_assets": {"value": null, "original_unit": null, "source_page": null, "source_section": null},
  "current_liabilities": {"value": null, "original_unit": null, "source_page": null, "source_section": null},
  "ebit": {"value": null, "original_unit": null, "source_page": null, "source_section": null},
  "interest_expense": {"value": null, "original_unit": null, "source_page": null, "source_section": null},
  "operating_cash_flow": {"value": null, "original_unit": null, "source_page": null, "source_section": null},
  "debt_service": {"value": null, "original_unit": null, "source_page": null, "source_section": null},
  "fiscal_year_end": null,
  "extraction_notes": "any ambiguity, merged cells, or uncertainty observed — be specific"
}"""

_QUALITATIVE_PROMPT = """\
Extract the following qualitative signals from the provided document chunks.
Return ONLY valid JSON:
{
  "auditor_qualification": {
    "has_qualification": null,
    "qualification_text": null,
    "qualification_type": null,
    "source_page": null
  },
  "going_concern_flag": {
    "mentioned": null,
    "context": null,
    "source_page": null
  },
  "litigation_disclosures": [
    {
      "description": null,
      "amount_crore": null,
      "status": null,
      "source_page": null
    }
  ],
  "management_commentary_summary": null,
  "key_risks_mentioned": [],
  "extraction_notes": null
}"""

_COVENANT_PROMPT = """\
Extract loan covenant and collateral information from the provided document chunks.
Return ONLY valid JSON:
{
  "existing_covenants": [
    {
      "covenant_description": null,
      "lender": null,
      "threshold_value": null,
      "breach_status": null,
      "source_page": null,
      "source_doc_type": null
    }
  ],
  "collateral_items": [
    {
      "description": null,
      "type": null,
      "estimated_value_crore": null,
      "charge_type": null,
      "source_page": null
    }
  ],
  "extraction_notes": null
}"""

_RATING_PROMPT = """\
Extract rating agency information from the provided document chunks.
Return ONLY valid JSON:
{
  "current_rating": null,
  "rating_agency": null,
  "rating_date": null,
  "rating_outlook": null,
  "previous_rating": null,
  "rating_action": null,
  "key_strengths": [],
  "key_weaknesses": [],
  "rationale_summary": null,
  "source_page": null
}"""


# =============================================================================
# Pydantic response models
# =============================================================================

class FinancialSummaryExtraction(BaseModel):
    """Structured financial data extracted by Claude from RAG chunks."""
    model_config = ConfigDict(from_attributes=True)
    data: Dict[str, Any] = Field(default_factory=dict)
    extraction_model: str = Field(default="")
    status: str = Field(default="success")


class QualitativeExtraction(BaseModel):
    """Qualitative signals: auditor notes, litigation, management commentary."""
    model_config = ConfigDict(from_attributes=True)
    data: Dict[str, Any] = Field(default_factory=dict)
    extraction_model: str = Field(default="")
    status: str = Field(default="success")


class CovenantExtraction(BaseModel):
    """Covenant and collateral information."""
    model_config = ConfigDict(from_attributes=True)
    data: Dict[str, Any] = Field(default_factory=dict)
    extraction_model: str = Field(default="")
    status: str = Field(default="success")


class RatingExtraction(BaseModel):
    """Rating agency intelligence."""
    model_config = ConfigDict(from_attributes=True)
    data: Dict[str, Any] = Field(default_factory=dict)
    extraction_model: str = Field(default="")
    status: str = Field(default="success")


class RAGExtractionResult(BaseModel):
    """Combined result from all 4 extraction functions."""
    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(...)
    financial_summary: Optional[FinancialSummaryExtraction] = None
    qualitative_signals: Optional[QualitativeExtraction] = None
    covenant_collateral: Optional[CovenantExtraction] = None
    rating_intelligence: Optional[RatingExtraction] = None
    extraction_model: str = Field(default=CLAUDE_RAG_EXTRACTION_MODEL)
    status: str = Field(default="success")
    errors: List[str] = Field(default_factory=list)
    extracted_at: str = Field(default="")


# =============================================================================
# Private helper — shared Claude call logic
# =============================================================================

async def _call_claude_extraction(
    system: str,
    user: str,
) -> dict:
    """
    Call Claude for structured extraction and return parsed JSON.

    - Model: from model_config.CLAUDE_RAG_EXTRACTION_MODEL
    - temperature: 0 (deterministic extraction)
    - Strips ```json fences before parsing
    - Returns {} on JSON parse failure (no crash)

    Args:
        system: System prompt.
        user:   User prompt with document chunks.

    Returns:
        Parsed JSON dict, or {} on failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = AsyncAnthropic(api_key=api_key)

    response = await client.messages.create(
        model=CLAUDE_RAG_EXTRACTION_MODEL,
        max_tokens=2000,
        temperature=0,
        system=system,
        messages=[
            {"role": "user", "content": user},
        ],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse Claude extraction JSON: {e}\n"
            f"Raw response (first 500 chars): {raw[:500]}"
        )
        return {}


# =============================================================================
# Extraction functions
# =============================================================================

async def extract_financial_summary(
    job_id: str,
) -> FinancialSummaryExtraction:
    """
    Extract financial figures from RAG chunks: revenue, EBITDA, debt, etc.

    Retrieves chunks for: financial_ratios, balance_sheet, cash_flow.
    Combines into one Claude call.

    Args:
        job_id: Loan application job ID.

    Returns:
        FinancialSummaryExtraction with parsed data.
    """
    try:
        # Retrieve chunks for all financial targets
        chunks_ratios = await retrieve_for_extraction(job_id, "financial_ratios")
        chunks_balance = await retrieve_for_extraction(job_id, "balance_sheet")
        chunks_cashflow = await retrieve_for_extraction(job_id, "cash_flow")

        all_chunks = chunks_ratios + chunks_balance + chunks_cashflow

        if not all_chunks:
            logger.warning(f"[{job_id}] No financial chunks retrieved — skipping extraction")
            return FinancialSummaryExtraction(
                extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
                status="skipped",
            )

        formatted = format_chunks_for_prompt(all_chunks)
        user_prompt = f"{_FINANCIAL_SUMMARY_PROMPT}\n\n---\nDOCUMENT CHUNKS:\n{formatted}"

        data = await _call_claude_extraction(EXTRACTION_SYSTEM_PROMPT, user_prompt)

        logger.info(f"[{job_id}] Financial summary extraction complete")
        return FinancialSummaryExtraction(
            data=data,
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="success" if data else "failed",
        )

    except Exception as e:
        logger.error(f"[{job_id}] Financial summary extraction failed: {e}")
        return FinancialSummaryExtraction(
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="failed",
        )


async def extract_qualitative_signals(
    job_id: str,
) -> QualitativeExtraction:
    """
    Extract qualitative signals: auditor notes, litigation, management discussion.

    Retrieves chunks for: auditor_notes, litigation, management_discussion.

    Args:
        job_id: Loan application job ID.

    Returns:
        QualitativeExtraction with parsed data.
    """
    try:
        chunks_auditor = await retrieve_for_extraction(job_id, "auditor_notes")
        chunks_litigation = await retrieve_for_extraction(job_id, "litigation")
        chunks_mgmt = await retrieve_for_extraction(job_id, "management_discussion")

        all_chunks = chunks_auditor + chunks_litigation + chunks_mgmt

        if not all_chunks:
            logger.warning(f"[{job_id}] No qualitative chunks retrieved — skipping")
            return QualitativeExtraction(
                extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
                status="skipped",
            )

        formatted = format_chunks_for_prompt(all_chunks)
        user_prompt = f"{_QUALITATIVE_PROMPT}\n\n---\nDOCUMENT CHUNKS:\n{formatted}"

        data = await _call_claude_extraction(EXTRACTION_SYSTEM_PROMPT, user_prompt)

        logger.info(f"[{job_id}] Qualitative signals extraction complete")
        return QualitativeExtraction(
            data=data,
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="success" if data else "failed",
        )

    except Exception as e:
        logger.error(f"[{job_id}] Qualitative signals extraction failed: {e}")
        return QualitativeExtraction(
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="failed",
        )


async def extract_covenant_and_collateral(
    job_id: str,
) -> CovenantExtraction:
    """
    Extract covenant terms and collateral details.

    Retrieves chunks for: covenants, collateral.

    Args:
        job_id: Loan application job ID.

    Returns:
        CovenantExtraction with parsed data.
    """
    try:
        chunks_covenants = await retrieve_for_extraction(job_id, "covenants")
        chunks_collateral = await retrieve_for_extraction(job_id, "collateral")

        all_chunks = chunks_covenants + chunks_collateral

        if not all_chunks:
            logger.warning(f"[{job_id}] No covenant/collateral chunks retrieved — skipping")
            return CovenantExtraction(
                extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
                status="skipped",
            )

        formatted = format_chunks_for_prompt(all_chunks)
        user_prompt = f"{_COVENANT_PROMPT}\n\n---\nDOCUMENT CHUNKS:\n{formatted}"

        data = await _call_claude_extraction(EXTRACTION_SYSTEM_PROMPT, user_prompt)

        logger.info(f"[{job_id}] Covenant/collateral extraction complete")
        return CovenantExtraction(
            data=data,
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="success" if data else "failed",
        )

    except Exception as e:
        logger.error(f"[{job_id}] Covenant/collateral extraction failed: {e}")
        return CovenantExtraction(
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="failed",
        )


async def extract_rating_intelligence(
    job_id: str,
) -> RatingExtraction:
    """
    Extract rating agency intelligence: rating, outlook, strengths/weaknesses.

    Retrieves chunks for: rating_rationale.

    Args:
        job_id: Loan application job ID.

    Returns:
        RatingExtraction with parsed data.
    """
    try:
        chunks = await retrieve_for_extraction(job_id, "rating_rationale")

        if not chunks:
            logger.warning(f"[{job_id}] No rating chunks retrieved — skipping")
            return RatingExtraction(
                extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
                status="skipped",
            )

        formatted = format_chunks_for_prompt(chunks)
        user_prompt = f"{_RATING_PROMPT}\n\n---\nDOCUMENT CHUNKS:\n{formatted}"

        data = await _call_claude_extraction(EXTRACTION_SYSTEM_PROMPT, user_prompt)

        logger.info(f"[{job_id}] Rating intelligence extraction complete")
        return RatingExtraction(
            data=data,
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="success" if data else "failed",
        )

    except Exception as e:
        logger.error(f"[{job_id}] Rating intelligence extraction failed: {e}")
        return RatingExtraction(
            extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
            status="failed",
        )


# =============================================================================
# Main orchestrator
# =============================================================================

async def run_full_extraction(job_id: str) -> RAGExtractionResult:
    """
    Run all 4 extraction functions sequentially and write rag_extraction.json.

    Results are written to /tmp/intelli-credit/{job_id}/rag_extraction.json
    (V11 pattern — ML scorer reads this file directly, no HTTP needed).

    Args:
        job_id: Loan application job ID.

    Returns:
        RAGExtractionResult combining all extractions.
    """
    errors: List[str] = []

    logger.info(f"[{job_id}] Starting full RAG extraction pipeline")

    # 1. Financial summary
    logger.info(f"[{job_id}] Step 1/4 — Financial summary extraction")
    financial = await extract_financial_summary(job_id)
    if financial.status == "failed":
        errors.append("Financial summary extraction failed")

    # 2. Qualitative signals
    logger.info(f"[{job_id}] Step 2/4 — Qualitative signals extraction")
    qualitative = await extract_qualitative_signals(job_id)
    if qualitative.status == "failed":
        errors.append("Qualitative signals extraction failed")

    # 3. Covenant and collateral
    logger.info(f"[{job_id}] Step 3/4 — Covenant/collateral extraction")
    covenant = await extract_covenant_and_collateral(job_id)
    if covenant.status == "failed":
        errors.append("Covenant/collateral extraction failed")

    # 4. Rating intelligence
    logger.info(f"[{job_id}] Step 4/4 — Rating intelligence extraction")
    rating = await extract_rating_intelligence(job_id)
    if rating.status == "failed":
        errors.append("Rating intelligence extraction failed")

    # Determine overall status
    statuses = [financial.status, qualitative.status, covenant.status, rating.status]
    if all(s == "success" for s in statuses):
        overall_status = "success"
    elif all(s == "failed" for s in statuses):
        overall_status = "failed"
    else:
        overall_status = "partial"

    now_iso = datetime.now(timezone.utc).isoformat()

    result = RAGExtractionResult(
        job_id=job_id,
        financial_summary=financial,
        qualitative_signals=qualitative,
        covenant_collateral=covenant,
        rating_intelligence=rating,
        extraction_model=CLAUDE_RAG_EXTRACTION_MODEL,
        status=overall_status,
        errors=errors,
        extracted_at=now_iso,
    )

    # Write to filesystem (V11 handoff)
    output_dir = _BASE_PATH / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "rag_extraction.json"

    try:
        output_file.write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info(f"[{job_id}] ✅ RAG extraction complete → {output_file}")
    except Exception as e:
        logger.error(f"[{job_id}] Failed to write rag_extraction.json: {e}")
        result.errors.append(f"Failed to write output: {e}")

    logger.info(
        f"[{job_id}] RAG extraction summary: status={overall_status}, "
        f"errors={len(errors)}"
    )

    return result
