// Package parser — section detection for document pages.
// Uses keyword matching to identify named sections in annual reports and
// other financial documents, matching the section keywords the RAG module
// uses for embed-priority assignment.
package parser

import "strings"

// sectionKeyword maps a search term (lowercase) to the canonical section name.
type sectionKeyword struct {
	keyword string
	section string
}

// Keywords ordered from most specific to least specific.
// First match wins — so "Management Discussion and Analysis" beats "Management".
var sectionKeywords = []sectionKeyword{
	// Balance Sheet / Financial Statements
	{"balance sheet", "Balance Sheet"},
	{"profit and loss", "Profit and Loss"},
	{"profit & loss", "Profit and Loss"},
	{"statement of profit", "Profit and Loss"},
	{"income statement", "Profit and Loss"},
	{"cash flow statement", "Cash Flow Statement"},
	{"cash flow", "Cash Flow Statement"},
	{"notes to accounts", "Notes to Accounts"},
	{"notes to financial", "Notes to Accounts"},
	{"significant accounting", "Notes to Accounts"},

	// Management & Governance
	{"management discussion and analysis", "Management Discussion and Analysis"},
	{"management discussion", "Management Discussion and Analysis"},
	{"md&a", "Management Discussion and Analysis"},
	{"director", "Directors Report"},
	{"corporate governance", "Corporate Governance"},

	// Audit
	{"auditor", "Auditor Report"},
	{"audit report", "Auditor Report"},
	{"independent audit", "Auditor Report"},

	// Debt & Borrowings
	{"debt schedule", "Debt Schedule"},
	{"borrowing", "Debt Schedule"},
	{"long term debt", "Debt Schedule"},

	// Financial Highlights
	{"financial highlight", "Financial Highlights"},
	{"financial summary", "Financial Highlights"},
	{"key financial", "Financial Highlights"},

	// Related Party
	{"related party", "Related Party Transactions"},

	// Contingent Liabilities
	{"contingent liab", "Contingent Liabilities"},

	// Covenant / Collateral (legal notices, sanction letters)
	{"covenant", "Covenant Terms"},
	{"collateral", "Collateral"},
	{"sanction", "Sanction Conditions"},
	{"security clause", "Collateral"},

	// Rating
	{"rating rationale", "Rating Rationale"},
	{"rating driver", "Key Rating Drivers"},
	{"outlook", "Outlook"},

	// GST
	{"gstr", "GST Filing"},
	{"goods and services", "GST Filing"},
}

// DetectSection looks at the first ~500 characters of a page's text
// and returns the best matching section name. Returns "" if no match.
func DetectSection(pageText string) string {
	// Use first 500 chars of the page for header detection
	sample := pageText
	if len(sample) > 500 {
		sample = sample[:500]
	}
	lower := strings.ToLower(sample)

	for _, sk := range sectionKeywords {
		if strings.Contains(lower, sk.keyword) {
			return sk.section
		}
	}
	return ""
}
