"""
Claude-based Structured Information Extraction.

Architecture doc Section 5 (RAG) + Section 3.2 (NER):
  After OCR and text extraction, Claude reads the combined text and
  extracts a structured JSON covering:
    - Financial figures (Revenue, EBITDA, PAT, Debt, Net Worth, DSCR, etc.)
    - Named entities (Promoters, Directors, CIN, Auditor, Related Parties)
    - Risk signals (Auditor qualifications, covenant breaches, litigation)

  The extraction prompt instructs Claude to return null rather than guess
  when a year label or value is uncertain (V4 hardening).
"""

import json
import logging
import os
from typing import Optional

from anthropic import AsyncAnthropic

from .schemas import (
    DocType,
    ExtractedEntities,
    ExtractedFinancials,
    ExtractedRiskSignals,
    ExtractionResult,
)

logger = logging.getLogger("deep_learning.info_extractor")


# ---------------------------------------------------------------------------
# Extraction prompts — one per doc_type for maximum precision
# ---------------------------------------------------------------------------

_ANNUAL_REPORT_PROMPT = """\
You are a credit analyst extracting structured data from an Indian company's Annual Report.
Extract the following into a JSON object.  For every financial figure, include the column
header verbatim to confirm the correct fiscal year.  If a year label or value is uncertain,
return null — never guess.

{
  "financials": {
    "revenue_fy": {"FY2022": <float|null>, "FY2023": <float|null>, "FY2024": <float|null>},
    "ebitda_margin": <float 0-1 | null>,
    "net_profit_margin": <float 0-1 | null>,
    "total_debt_crore": <float | null>,
    "net_worth_crore": <float | null>,
    "dscr": <float | null>,
    "debt_to_equity": <float | null>,
    "interest_coverage_ratio": <float | null>,
    "current_ratio": <float | null>
  },
  "entities": {
    "company_name": <str | null>,
    "cin": <str | null>,
    "promoter_names": [<str>],
    "directors": [<str>],
    "auditor": <str | null>,
    "related_parties": [<str>]
  },
  "risk_signals": {
    "auditor_qualifications": [<str>],
    "contingent_liabilities": [<str>],
    "covenant_breaches": [<str>],
    "litigation_mentions": [<str>],
    "going_concern_flag": <bool>
  }
}

Amounts should be in ₹ Crore.  If amounts are in lakhs, convert to crore (÷100).
Respond ONLY with the JSON object, no markdown fences.
"""

_BANK_STATEMENT_PROMPT = """\
You are analysing an Indian company's bank statement.  Extract:
{
  "financials": {
    "total_credits_crore": <float | null>,
    "total_debits_crore": <float | null>,
    "cash_deposits_crore": <float | null>,
    "peak_balance_crore": <float | null>
  },
  "entities": {
    "company_name": <str | null>,
    "bank_name": <str | null>,
    "account_number": <str | null>
  },
  "risk_signals": {
    "large_cash_deposits": [<str description>],
    "round_trip_patterns": [<str description>]
  }
}
Respond ONLY with the JSON object, no markdown fences.
"""

_GST_FILING_PROMPT = """\
You are analysing Indian GST filings (GSTR-1, GSTR-2A, GSTR-3B).  Extract:
{
  "financials": {
    "gst_turnover_crore": <float | null>,
    "itc_claimed_crore": <float | null>,
    "itc_eligible_crore": <float | null>,
    "gstr_2a_3b_mismatch_pct": <float 0-100 | null>
  },
  "entities": {
    "company_name": <str | null>,
    "gstin": <str | null>
  },
  "risk_signals": {
    "filing_delays": [<str>],
    "mismatch_warnings": [<str>]
  }
}
Respond ONLY with the JSON object, no markdown fences.
"""

_GENERIC_PROMPT = """\
You are extracting structured information from an Indian financial document.  Extract:
{
  "entities": {
    "company_name": <str | null>,
    "key_persons": [<str>]
  },
  "risk_signals": {
    "negative_findings": [<str>],
    "key_observations": [<str>]
  }
}
Respond ONLY with the JSON object, no markdown fences.
"""


def _get_prompt_for_doc_type(doc_type: DocType) -> str:
    """Return the extraction prompt matching the document type."""
    mapping = {
        DocType.ANNUAL_REPORT: _ANNUAL_REPORT_PROMPT,
        DocType.BANK_STATEMENT: _BANK_STATEMENT_PROMPT,
        DocType.GST_FILING: _GST_FILING_PROMPT,
        DocType.RATING_REPORT: _GENERIC_PROMPT,
        DocType.LEGAL_NOTICE: _GENERIC_PROMPT,
    }
    return mapping.get(doc_type, _GENERIC_PROMPT)


def _safe_parse_json(raw: str) -> dict:
    """Parse JSON from Claude output, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


async def extract_structured_info(
    combined_text: str,
    doc_type: DocType,
    page_count: int = 0,
) -> ExtractionResult:
    """
    Send combined page text (PyMuPDF + OCR Markdown) to Claude for
    structured information extraction.

    Args:
        combined_text: Merged text from all pages of the document.
        doc_type:      Type of document being processed.
        page_count:    Number of pages whose text is included.

    Returns:
        ExtractionResult with financials, entities, and risk signals.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — returning empty extraction")
        return ExtractionResult(
            doc_type=doc_type,
            raw_text_pages=page_count,
            confidence="LOW",
        )

    client = AsyncAnthropic(api_key=api_key)
    extraction_prompt = _get_prompt_for_doc_type(doc_type)

    # Truncate to keep within token budget (approx 12k chars ≈ 3k tokens)
    text_input = combined_text[:12000]

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=(
                "You are a financial document extraction engine. "
                "Always respond with valid JSON only. Never guess uncertain values — "
                "return null instead."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"{extraction_prompt}\n\n---\nDOCUMENT TEXT:\n{text_input}",
                }
            ],
        )

        raw_output = response.content[0].text
        parsed = _safe_parse_json(raw_output)

        # Build typed sub-objects (gracefully handle missing keys)
        financials = None
        if "financials" in parsed:
            financials = ExtractedFinancials(**parsed["financials"])

        entities = None
        if "entities" in parsed:
            entities = ExtractedEntities(**parsed["entities"])

        risk_signals = None
        if "risk_signals" in parsed:
            risk_signals = ExtractedRiskSignals(**parsed["risk_signals"])

        return ExtractionResult(
            doc_type=doc_type,
            financials=financials,
            entities=entities,
            risk_signals=risk_signals,
            raw_text_pages=page_count,
            confidence="HIGH",
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude extraction JSON: {e}")
        return ExtractionResult(
            doc_type=doc_type,
            raw_text_pages=page_count,
            confidence="LOW",
        )
    except Exception as e:
        logger.error(f"Claude extraction failed: {e}")
        return ExtractionResult(
            doc_type=doc_type,
            raw_text_pages=page_count,
            confidence="LOW",
        )
