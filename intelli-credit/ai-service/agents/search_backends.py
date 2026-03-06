"""
Search Backends — Serper API + DuckDuckGo fallback for escalation deep searches.

=============================================================================
Replaces Tavily in run_escalation_searches node.

Strategy:
  1. Try Serper API first (raw Google Search, 2500 free credits, gl=in for India)
  2. On HTTP 429 / quota error / missing key → fall back to DuckDuckGo automatically
  3. Log which backend was used — visible in SSE progress stream

Why Serper over Tavily for escalation:
  - Better for targeted site: queries against Indian legal portals
    (nclt.gov.in, ecourts.gov.in, mca.gov.in)
  - Raw Google results preserve exact portal URLs for verification
  - Tavily's "advanced" search summarizes content, losing source fidelity

Query construction:
  build_escalation_queries() generates site-specific queries based on which
  keywords triggered escalation — not a fixed list, adapts to the signals found.
=============================================================================
"""

import asyncio
import logging
import os
import re
from typing import List

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("agents.search_backends")

# =============================================================================
# Schemas
# =============================================================================

class SearchResult(BaseModel):
    """A single search result from any backend."""

    model_config = ConfigDict(json_schema_extra={"title": "SearchResult"})

    title: str = Field(default="", description="Page title")
    url: str = Field(default="", description="Page URL")
    snippet: str = Field(default="", description="Text snippet / summary")
    source: str = Field(default="", description="Backend that produced this: 'serper' or 'duckduckgo'")


class SerperResult(BaseModel):
    """Batch result from a single deep search call."""

    model_config = ConfigDict(json_schema_extra={"title": "SerperResult"})

    results: List[SearchResult] = Field(default_factory=list, description="Search results")
    backend: str = Field(default="", description="Backend used: 'serper', 'duckduckgo', 'duckduckgo_fallback'")
    query: str = Field(default="", description="Original query string")


# =============================================================================
# Custom exceptions
# =============================================================================

class SerperQuotaExhausted(Exception):
    """Raised when Serper returns HTTP 429 or a quota error."""
    pass


class SerperAPIError(Exception):
    """Raised when Serper returns a non-200/non-429 status code."""
    pass


# =============================================================================
# Serper client
# =============================================================================

SERPER_API_URL = "https://google.serper.dev/search"


async def serper_search(query: str, num_results: int = 5) -> SerperResult:
    """
    Search via Serper API (raw Google Search).

    Args:
        query:       Search query string.
        num_results: Number of results to return.

    Returns:
        SerperResult with results from Google via Serper.

    Raises:
        SerperQuotaExhausted: If Serper returns HTTP 429.
        SerperAPIError: If Serper returns any other error status.
    """
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        raise SerperAPIError("SERPER_API_KEY not set")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": num_results,
        "gl": "in",   # India-specific Google results
        "hl": "en",   # English results
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(SERPER_API_URL, json=payload, headers=headers)

    if response.status_code == 429:
        raise SerperQuotaExhausted("Serper quota exhausted (HTTP 429)")

    if response.status_code != 200:
        raise SerperAPIError(f"Serper returned HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()
    results = []
    for item in data.get("organic", []):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source="serper",
            )
        )

    return SerperResult(results=results, backend="serper", query=query)


# =============================================================================
# DuckDuckGo fallback client
# =============================================================================

async def duckduckgo_search(query: str, num_results: int = 5) -> SerperResult:
    """
    Search via DuckDuckGo (free, no API key needed).

    DDGS is synchronous — wrapped in asyncio.to_thread to keep FastAPI async.

    Args:
        query:       Search query string.
        num_results: Number of results to return.

    Returns:
        SerperResult with results from DuckDuckGo.
    """
    from duckduckgo_search import DDGS

    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=num_results, region="in-en"))

    try:
        raw = await asyncio.to_thread(_search)
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return SerperResult(results=[], backend="duckduckgo", query=query)

    results = [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("href", ""),
            snippet=r.get("body", ""),
            source="duckduckgo",
        )
        for r in raw
    ]

    return SerperResult(results=results, backend="duckduckgo", query=query)


# =============================================================================
# Unified deep search — Serper with DuckDuckGo fallback
# =============================================================================

async def deep_search(query: str, num_results: int = 5) -> SerperResult:
    """
    Try Serper first. On quota exhaustion (429) or missing API key,
    fall back to DuckDuckGo automatically.

    This is the ONLY function that run_escalation_searches should call.

    Args:
        query:       Search query string.
        num_results: Number of results to return.

    Returns:
        SerperResult — check .backend to see which engine was used.
    """
    serper_key = os.environ.get("SERPER_API_KEY", "")

    if not serper_key:
        logger.info(f"SERPER_API_KEY not set — using DuckDuckGo for: '{query[:60]}'")
        return await duckduckgo_search(query, num_results)

    try:
        result = await serper_search(query, num_results)
        logger.info(
            f"Deep search via Serper ({len(result.results)} results): '{query[:60]}'"
        )
        return result

    except SerperQuotaExhausted:
        logger.warning(
            f"Serper quota exhausted — falling back to DuckDuckGo for: '{query[:60]}'"
        )
        result = await duckduckgo_search(query, num_results)
        result.backend = "duckduckgo_fallback"
        return result

    except SerperAPIError as e:
        logger.warning(
            f"Serper error ({e}) — falling back to DuckDuckGo for: '{query[:60]}'"
        )
        return await duckduckgo_search(query, num_results)


# =============================================================================
# Indian legal portal query builder
# =============================================================================

def _sanitize(text: str) -> str:
    """Strip non-alphanumeric/space characters to prevent query injection."""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()


def build_escalation_queries(
    company_name: str,
    promoter_names: List[str],
    triggered_keywords: List[str],
) -> List[str]:
    """
    Build site-specific queries for Indian legal portals based on which
    escalation keywords were triggered.

    Called by the run_escalation_searches node with the keywords that
    check_escalation found. Generates targeted queries — not a fixed list,
    adapts to the signals found.

    Args:
        company_name:      Borrower company name.
        promoter_names:    List of promoter/director names.
        triggered_keywords: Keywords that triggered escalation.

    Returns:
        List of query strings to run through deep_search().
    """
    queries: List[str] = []
    s_company = _sanitize(company_name)
    primary_promoter = _sanitize(promoter_names[0]) if promoter_names else ""
    kw_lower = [k.lower() for k in triggered_keywords]

    # NCLT / insolvency / default
    if any(k in kw_lower for k in ["nclt", "insolvency", "default"]):
        queries.append(f"site:nclt.gov.in {primary_promoter} {s_company}")
        queries.append(f"site:nclt.gov.in {s_company} petition")

    # Court / NPA / DRT / arrested
    if any(k in kw_lower for k in ["court", "npa", "drt", "arrested"]):
        queries.append(f"site:ecourts.gov.in {primary_promoter} {s_company}")

    # ED / Enforcement Directorate / FEMA
    if any(k in kw_lower for k in ["ed", "enforcement directorate", "fema"]):
        queries.append(f"Enforcement Directorate attachment order {s_company}")
        queries.append(f"ED raid {primary_promoter} {s_company}")

    # SEBI / debarment
    if any(k in kw_lower for k in ["sebi", "debarment"]):
        queries.append(f"SEBI order debarment {primary_promoter}")

    # CBI / fraud / SFIO
    if any(k in kw_lower for k in ["cbi", "fraud", "sfio"]):
        queries.append(f"CBI FIR {primary_promoter} {s_company}")
        queries.append(f"SFIO investigation {s_company}")

    # Money laundering
    if "money laundering" in kw_lower:
        queries.append(f"PMLA money laundering {primary_promoter} {s_company}")

    # Always check MCA regardless of keywords
    queries.append(f"site:mca.gov.in {s_company} director disqualification")

    # Always check RBI penalty
    queries.append(f"RBI penalty {s_company} 2024 2025")

    logger.info(
        f"Built {len(queries)} escalation queries for '{company_name}' "
        f"(triggered: {triggered_keywords})"
    )

    return queries


# =============================================================================
# Batch deep search — runs all escalation queries via deep_search()
# =============================================================================

async def run_deep_searches(
    company_name: str,
    promoter_names: List[str],
    triggered_keywords: List[str],
    num_results: int = 3,
) -> List[SerperResult]:
    """
    Build escalation queries and run them all through deep_search().

    Runs sequentially to avoid rate-limiting issues with Serper.
    Returns one SerperResult per query.

    Args:
        company_name:      Borrower company name.
        promoter_names:    List of promoter/director names.
        triggered_keywords: Keywords from check_escalation.
        num_results:       Results per query (default 3).

    Returns:
        List of SerperResult, one per query.
    """
    queries = build_escalation_queries(company_name, promoter_names, triggered_keywords)

    if not queries:
        logger.info("No escalation queries generated — no deep searches to run")
        return []

    results: List[SerperResult] = []

    for query in queries:
        result = await deep_search(query, num_results)
        results.append(result)
        # Brief delay between queries to respect rate limits
        await asyncio.sleep(0.3)

    backends_used = set(r.backend for r in results)
    total_hits = sum(len(r.results) for r in results)

    logger.info(
        f"Deep searches complete: {len(queries)} queries, "
        f"{total_hits} total results, backends={backends_used}"
    )

    return results
