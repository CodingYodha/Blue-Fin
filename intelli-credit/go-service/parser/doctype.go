// Package parser — doc type detection from filenames.
// Maps uploaded filenames to doc_type values expected by the RAG pipeline.
package parser

import "strings"

// DocType constants matching the RAG schema's Literal types.
const (
	DocAnnualReport = "annual_report"
	DocRatingReport = "rating_report"
	DocLegalNotice  = "legal_notice"
	DocGSTFiling    = "gst_filing"
	DocBankStmt     = "bank_statement"
	DocUnknown      = "unknown"
)

// DetectDocType infers the document type from the filename.
// Filenames follow the convention used by the frontend upload:
//   annual_report_2024.pdf, rating_report.pdf, gst_filing_q1.pdf, etc.
func DetectDocType(filename string) string {
	lower := strings.ToLower(filename)

	switch {
	case strings.Contains(lower, "annual_report") || strings.Contains(lower, "annual report"):
		return DocAnnualReport
	case strings.Contains(lower, "rating_report") || strings.Contains(lower, "rating report") || strings.Contains(lower, "rating"):
		return DocRatingReport
	case strings.Contains(lower, "legal_notice") || strings.Contains(lower, "legal notice") || strings.Contains(lower, "legal"):
		return DocLegalNotice
	case strings.Contains(lower, "gst") || strings.Contains(lower, "gstr"):
		return DocGSTFiling
	case strings.Contains(lower, "bank") || strings.Contains(lower, "statement"):
		return DocBankStmt
	default:
		return DocUnknown
	}
}
