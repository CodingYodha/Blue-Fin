"""
Deep Learning module — Document Intelligence for Intelli-Credit.

Sub-modules:
  - page_classifier : PyMuPDF smart page targeting (V6 fix)
  - ocr_engine      : DeepSeek-VL2 local OCR for scanned pages
  - info_extractor  : Claude-based structured financial + entity extraction
  - schemas         : Pydantic v2 models for all I/O
"""

from .schemas import (
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    JobStatusResponse,
    DocumentProcessingResult,
)

__all__ = [
    "ProcessDocumentRequest",
    "ProcessDocumentResponse",
    "JobStatusResponse",
    "DocumentProcessingResult",
]
