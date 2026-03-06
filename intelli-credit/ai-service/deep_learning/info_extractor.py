"""
Claude-based Structured Information Extraction.

=============================================================================
ARCHITECTURE DOC: Section 5 (RAG) + Section 3.2 (NER) + V4 Fix
=============================================================================
V4 PROBLEM: Claude cross-substitutes FY values in complex financial tables
  (e.g., reports FY23 EBITDA as FY24).
V4 FIX: Claude returns every figure WITH its column header verbatim.
  If the year label is uncertain, it returns null — never guesses.
  Cross-verification against Go service values happens downstream.

TWO SEPARATE CALLS:
  1. extract_financial_ratios() — financial figures, ratios, audit info
  2. extract_entities()         — NER for Entity Graph module

Both use claude-haiku-4-5-20251001 for cost efficiency.
=============================================================================
"""

import json
import logging
import os
from typing import Optional

from anthropic import AsyncAnthropic

from model_config import (
    CLAUDE_FINANCIAL_EXTRACTION_MODEL,
    CLAUDE_ENTITY_EXTRACTION_MODEL,
)
from .schemas import (
    EntityExtraction,
    ExtractionResult,
    FinancialExtraction,
    PromoterEntity,
    RelatedPartyEntity,
    SubsidiaryEntity,
    LenderEntity,
    GuarantorEntity,
    AuditorEntity,
)

logger = logging.getLogger("deep_learning.info_extractor")


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_FINANCIAL_SYSTEM_PROMPT = (
    "You are a financial data extraction engine for Indian corporate credit assessment. "
    "You will receive text extracted from a financial document (possibly with OCR artifacts). "
    "Extract ONLY the explicitly stated figures. Do NOT calculate, infer, or estimate any value. "
    "If a figure is not present or the year label is uncertain, return null for that field. "
    "Return every numeric value with its exact column header from the document. "
    "Indian amount notation: amounts may be in Lakhs (1 Lakh = 100,000) or Crores (1 Crore = 10,000,000). "
    "Always normalize to Crores in your output. State the original unit in a separate field."
)

_ENTITY_SYSTEM_PROMPT = (
    "You are a Named Entity Recognition engine for Indian corporate documents. "
    "Extract exact legal names as they appear in the document. Do not paraphrase. "
    "For person names: include full name with initials as written. "
    "For company names: include the full legal suffix (Pvt Ltd, LLP, Ltd, etc.). "
    "Return only entities that are EXPLICITLY stated in the text."
)


# ---------------------------------------------------------------------------
# Doc-type-specific user prompts for financial extraction
# ---------------------------------------------------------------------------

_ANNUAL_REPORT_PROMPT = """\
Extract the following from this Annual Report text. Return ONLY valid JSON, no explanation.

{
  "revenue": {"fy_current": null, "fy_previous": null, "fy_two_years_ago": null, "unit_in_document": null},
  "ebitda": {"fy_current": null, "fy_previous": null, "fy_two_years_ago": null},
  "pat": {"fy_current": null, "fy_previous": null},
  "total_debt": {"value": null, "as_of_date": null},
  "net_worth": {"value": null, "as_of_date": null},
  "current_assets": null,
  "current_liabilities": null,
  "ebit": null,
  "interest_expense": null,
  "operating_cash_flow": null,
  "debt_service": null,
  "auditor_qualification": null,
  "auditor_name": null,
  "fiscal_year_end": null,
  "extraction_notes": "Any ambiguity, merged cells, or confidence issues observed"
}

All amounts must be normalized to Crores. State the original unit in unit_in_document."""

_GST_FILING_PROMPT = """\
Extract the following from this GST Filing text. Return ONLY valid JSON, no explanation.

{
  "gst_turnover_declared": null,
  "itc_claimed_3b": null,
  "period_covered": null,
  "gstin": null,
  "extraction_notes": "Any ambiguity or confidence issues observed"
}

All amounts in Crores."""

_RATING_REPORT_PROMPT = """\
Extract the following from this Credit Rating Report text. Return ONLY valid JSON, no explanation.

{
  "rating_assigned": null,
  "rating_outlook": null,
  "rating_date": null,
  "rating_agency": null,
  "key_rationale_summary": "Max 3 sentences summarizing rating rationale",
  "previous_rating": null,
  "extraction_notes": "Any ambiguity or confidence issues observed"
}"""

_BANK_STATEMENT_PROMPT = """\
Extract the following from this Bank Statement text. Return ONLY valid JSON, no explanation.

{
  "extraction_notes": "Bank statements are typically digital CSVs. Note any anomalies."
}"""

_LEGAL_NOTICE_PROMPT = """\
Extract the following from this Legal Notice text. Return ONLY valid JSON, no explanation.

{
  "extraction_notes": "Note any legal actions, dates, or amounts mentioned."
}"""

_ENTITY_USER_PROMPT = """\
Extract the following entities from this document. Return ONLY valid JSON.

{
  "promoters": [{"name": "", "designation": "", "din": null}],
  "company_name": "",
  "cin": null,
  "related_parties": [{"name": "", "relationship": "", "transaction_amount_crore": null}],
  "subsidiaries": [{"name": "", "cin": null}],
  "existing_lenders": [{"bank_name": "", "facility_type": "", "amount_crore": null}],
  "collateral_descriptions": [""],
  "guarantors": [{"name": "", "relationship_to_borrower": ""}],
  "auditor": {"name": "", "firm": ""}
}

Extract ONLY entities explicitly stated in the text. Use exact legal names."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_financial_prompt(doc_type: str) -> str:
    """Return the extraction prompt matching the document type."""
    mapping = {
        "annual_report": _ANNUAL_REPORT_PROMPT,
        "gst_filing": _GST_FILING_PROMPT,
        "rating_report": _RATING_REPORT_PROMPT,
        "bank_statement": _BANK_STATEMENT_PROMPT,
        "legal_notice": _LEGAL_NOTICE_PROMPT,
    }
    return mapping.get(doc_type, _ANNUAL_REPORT_PROMPT)


def _safe_parse_json(raw: str) -> dict:
    """Parse JSON from Claude output, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _count_critical_nulls(data: dict, doc_type: str) -> int:
    """Count null values in critical fields to determine confidence."""
    if doc_type == "annual_report":
        critical_fields = [
            data.get("revenue"),
            data.get("ebitda"),
            data.get("pat"),
            data.get("total_debt"),
            data.get("net_worth"),
        ]
    elif doc_type == "gst_filing":
        critical_fields = [
            data.get("gst_turnover_declared"),
            data.get("itc_claimed_3b"),
            data.get("gstin"),
        ]
    elif doc_type == "rating_report":
        critical_fields = [
            data.get("rating_assigned"),
            data.get("rating_agency"),
            data.get("rating_date"),
        ]
    else:
        return 0

    return sum(1 for f in critical_fields if f is None)


async def _call_claude(
    system_prompt: str,
    user_prompt: str,
    document_text: str,
) -> str:
    """
    Send a prompt to Claude and return the raw response text.
    Truncates document text to ~12k chars (~3k tokens) to stay within budget.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = AsyncAnthropic(api_key=api_key)

    # Truncate to keep within token budget
    text_input = document_text[:12000]

    response = await client.messages.create(
        model=CLAUDE_FINANCIAL_EXTRACTION_MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"{user_prompt}\n\n---\nDOCUMENT TEXT:\n{text_input}",
            }
        ],
    )

    return response.content[0].text


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

async def extract_financial_ratios(
    merged_text: str,
    doc_type: str,
) -> FinancialExtraction:
    """
    Extract structured financial data from merged document text using Claude.

    Implements the V4 fix: Claude returns null for uncertain values rather
    than guessing.  Every figure includes its column header verbatim.

    Args:
        merged_text: Full document text from merge_document_text().
        doc_type:    One of the DocType values as a string.

    Returns:
        FinancialExtraction with all extracted figures and confidence level.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set — returning empty financial extraction")
        return FinancialExtraction(doc_type=doc_type, confidence="LOW")

    try:
        user_prompt = _get_financial_prompt(doc_type)
        raw_output = await _call_claude(
            _FINANCIAL_SYSTEM_PROMPT, user_prompt, merged_text
        )

        parsed = _safe_parse_json(raw_output)

        # Determine confidence based on critical null count
        null_count = _count_critical_nulls(parsed, doc_type)
        confidence = "LOW" if null_count >= 3 else "HIGH"

        # Build the extraction, safely handling nested objects
        revenue = None
        if parsed.get("revenue") and isinstance(parsed["revenue"], dict):
            revenue = parsed["revenue"]

        ebitda = None
        if parsed.get("ebitda") and isinstance(parsed["ebitda"], dict):
            ebitda = parsed["ebitda"]

        pat = None
        if parsed.get("pat") and isinstance(parsed["pat"], dict):
            pat = parsed["pat"]

        total_debt = None
        if parsed.get("total_debt") and isinstance(parsed["total_debt"], dict):
            total_debt = parsed["total_debt"]

        net_worth = None
        if parsed.get("net_worth") and isinstance(parsed["net_worth"], dict):
            net_worth = parsed["net_worth"]

        result = FinancialExtraction(
            doc_type=doc_type,
            extraction_model=CLAUDE_FINANCIAL_EXTRACTION_MODEL,
            confidence=confidence,
            revenue=revenue,
            ebitda=ebitda,
            pat=pat,
            total_debt=total_debt,
            net_worth=net_worth,
            current_assets=parsed.get("current_assets"),
            current_liabilities=parsed.get("current_liabilities"),
            ebit=parsed.get("ebit"),
            interest_expense=parsed.get("interest_expense"),
            operating_cash_flow=parsed.get("operating_cash_flow"),
            debt_service=parsed.get("debt_service"),
            auditor_qualification=parsed.get("auditor_qualification"),
            auditor_name=parsed.get("auditor_name"),
            fiscal_year_end=parsed.get("fiscal_year_end"),
            extraction_notes=parsed.get("extraction_notes"),
            # GST fields
            gst_turnover_declared=parsed.get("gst_turnover_declared"),
            itc_claimed_3b=parsed.get("itc_claimed_3b"),
            period_covered=parsed.get("period_covered"),
            gstin=parsed.get("gstin"),
            # Rating fields
            rating_assigned=parsed.get("rating_assigned"),
            rating_outlook=parsed.get("rating_outlook"),
            rating_date=parsed.get("rating_date"),
            rating_agency=parsed.get("rating_agency"),
            key_rationale_summary=parsed.get("key_rationale_summary"),
            previous_rating=parsed.get("previous_rating"),
        )

        logger.info(
            f"Financial extraction complete: doc_type={doc_type}, "
            f"confidence={confidence}, critical_nulls={null_count}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude financial extraction JSON: {e}")
        return FinancialExtraction(doc_type=doc_type, confidence="LOW")
    except Exception as e:
        logger.error(f"Financial extraction failed: {e}")
        return FinancialExtraction(doc_type=doc_type, confidence="LOW")


async def extract_entities(
    merged_text: str,
    doc_type: str = "annual_report",
) -> EntityExtraction:
    """
    Extract named entities from merged document text using Claude.

    This feeds the Entity Graph module.  Extracts exact legal names:
    promoters, related parties, subsidiaries, lenders, guarantors, auditor.

    Args:
        merged_text: Full document text from merge_document_text().
        doc_type:    Source document type for metadata.

    Returns:
        EntityExtraction with all entities and entity_count.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set — returning empty entity extraction")
        return EntityExtraction(source_doc_type=doc_type, entity_count=0)

    try:
        raw_output = await _call_claude(
            _ENTITY_SYSTEM_PROMPT, _ENTITY_USER_PROMPT, merged_text
        )

        parsed = _safe_parse_json(raw_output)

        # Build typed entity lists, handling malformed entries gracefully
        promoters = []
        for p in parsed.get("promoters", []):
            if isinstance(p, dict) and p.get("name"):
                promoters.append(PromoterEntity(**p))

        related_parties = []
        for rp in parsed.get("related_parties", []):
            if isinstance(rp, dict) and rp.get("name"):
                related_parties.append(RelatedPartyEntity(**rp))

        subsidiaries = []
        for s in parsed.get("subsidiaries", []):
            if isinstance(s, dict) and s.get("name"):
                subsidiaries.append(SubsidiaryEntity(**s))

        lenders = []
        for l in parsed.get("existing_lenders", []):
            if isinstance(l, dict) and l.get("bank_name"):
                lenders.append(LenderEntity(**l))

        guarantors = []
        for g in parsed.get("guarantors", []):
            if isinstance(g, dict) and g.get("name"):
                guarantors.append(GuarantorEntity(**g))

        collateral = [
            c for c in parsed.get("collateral_descriptions", [])
            if isinstance(c, str) and c.strip()
        ]

        auditor = None
        if parsed.get("auditor") and isinstance(parsed["auditor"], dict):
            auditor = AuditorEntity(**parsed["auditor"])

        # Total entity count
        entity_count = (
            len(promoters) + len(related_parties) + len(subsidiaries)
            + len(lenders) + len(guarantors) + len(collateral)
            + (1 if auditor else 0)
            + (1 if parsed.get("company_name") else 0)
        )

        result = EntityExtraction(
            source_doc_type=doc_type,
            entity_count=entity_count,
            extraction_model=CLAUDE_ENTITY_EXTRACTION_MODEL,
            company_name=parsed.get("company_name"),
            cin=parsed.get("cin"),
            promoters=promoters,
            related_parties=related_parties,
            subsidiaries=subsidiaries,
            existing_lenders=lenders,
            collateral_descriptions=collateral,
            guarantors=guarantors,
            auditor=auditor,
        )

        logger.info(
            f"Entity extraction complete: {entity_count} entities found"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude entity extraction JSON: {e}")
        return EntityExtraction(source_doc_type=doc_type, entity_count=0)
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return EntityExtraction(source_doc_type=doc_type, entity_count=0)


async def extract_structured_info(
    combined_text: str,
    doc_type: str,
    page_count: int = 0,
) -> ExtractionResult:
    """
    Run both financial and entity extraction in parallel.

    This is the main entry point called by the pipeline in main.py.
    Runs both Claude calls concurrently via asyncio.gather.

    Args:
        combined_text: Full merged document text.
        doc_type:      Document type string.
        page_count:    Total page count (metadata only).

    Returns:
        ExtractionResult combining both extractions.
    """
    import asyncio

    financial_task = extract_financial_ratios(combined_text, doc_type)
    entity_task = extract_entities(combined_text, doc_type)

    financial_result, entity_result = await asyncio.gather(
        financial_task, entity_task
    )

    logger.info(
        f"Combined extraction complete: "
        f"financial confidence={financial_result.confidence}, "
        f"entities={entity_result.entity_count}"
    )

    return ExtractionResult(
        doc_type=doc_type,
        financial_extraction=financial_result,
        entity_extraction=entity_result,
    )
