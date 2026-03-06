from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: Literal["tavily", "serper", "duckduckgo", "duckduckgo_fallback"]

class VerifiedFinding(BaseModel):
    result: SearchResult
    match: Optional[bool]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    reason: str

class SectorSentimentResult(BaseModel):
    score: float
    label: Literal["HEADWIND", "NEUTRAL", "TAILWIND"]
    articles_scored: int
    key_signals: List[str]
    override_triggered: bool
    source: str

class ResearchAgentSummary(BaseModel):
    job_id: str
    promoter_risk: Literal["LOW", "MEDIUM", "HIGH"]
    litigation_risk: Literal["NONE", "HISTORICAL", "ACTIVE"]
    sector_risk: Literal["TAILWIND", "NEUTRAL", "HEADWIND"]
    sector_sentiment_score: float
    sector_sentiment_label: str
    sector_sentiment_articles_scored: int
    escalation_triggered: bool
    deep_search_backend: str
    entity_verification: Dict[str, Any]
    key_findings: List[Dict[str, Any]]
    completed_at: datetime

class RunAgentRequest(BaseModel):
    job_id: str
    company_name: str
    promoter_names: List[str]
    industry: str
    cin: Optional[str] = None
