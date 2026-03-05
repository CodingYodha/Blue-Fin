"""
Deep Learning module — Document Intelligence for Intelli-Credit.

Sub-modules:
  - page_classifier : PyMuPDF smart page targeting (V6 fix)
  - ocr_engine      : DeepSeek-OCR integration for scanned pages
  - info_extractor  : Claude-based structured financial extraction
  - schemas         : Pydantic models for all I/O
"""

from .schemas import (
    DocType,
    ProcessingStatus,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    JobStatusResponse,
    DocumentProcessingOutput,
)

__all__ = [
    "DocType",
    "ProcessingStatus",
    "ProcessDocumentRequest",
    "ProcessDocumentResponse",
    "JobStatusResponse",
    "DocumentProcessingOutput",
]
