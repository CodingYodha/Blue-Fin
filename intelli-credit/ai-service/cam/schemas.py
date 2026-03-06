from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class OfficerNotesRequest(BaseModel):
    job_id: str
    notes_text: str
    officer_id: str

class OfficerNotesResponse(BaseModel):
    injection_detected: bool
    penalty: float
    score_before: float
    score_after: float
    adjustments: Dict[str, float]
    interpretation: str
    new_final_score: float
    new_decision: str
    escalation_triggered: bool

class CAMGenerateRequest(BaseModel):
    job_id: str

class SourceCitation(BaseModel):
    claim: str
    source: str
    module: str
    confidence: str  # HIGH / LOW

class PersonaOutput(BaseModel):
    section: str
    persona: str
    content: str
    source_citations: List[SourceCitation]

class AccountantOutput(PersonaOutput):
    key_financial_risks: List[str]
    confidence_flags: List[Dict[str, Any]]

class ComplianceOutput(PersonaOutput):
    promoter_integrity_verdict: str
    active_legal_proceedings: List[str]
    excluded_findings_count: int
    governance_flags: List[str]

class CROOutput(PersonaOutput):
    final_decision: str
    ml_decision: str
    override_applied: bool
    override_reason: Optional[str]
    sanctioned_limit_crore: Optional[float]
    interest_rate_pct: Optional[float]
    mandatory_covenants: List[str]
    monitoring_triggers: List[str]

class CAMResult(BaseModel):
    status: str  # "processing" | "ready" | "error"
    job_id: str
    final_decision: str
    override_applied: bool
    override_reason: Optional[str]
    sanctioned_limit_crore: Optional[float]
    interest_rate_pct: Optional[float]
    accountant_section: str
    compliance_section: str
    cro_section: str
    officer_notes_section: Optional[str]
    audit_trail: List[SourceCitation]
    download_urls: Dict[str, str]  # {"docx": "/api/v1/cam/download/{id}/docx", "pdf": "..."}
    generated_at: datetime
