// Package parser extracts text from PDF files using ledongthuc/pdf (pure-Go).
// It classifies each page as DIGITAL / SCANNED / PARTIAL / BLANK and returns
// structured per-page text that the chunker package consumes.
package parser

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"

	pdf "github.com/ledongthuc/pdf"
)

// PageType classifies a single PDF page by text density.
const (
	PageDigital = "digital"  // >200 chars — born-digital text
	PageScanned = "scanned"  // <50 chars — image-based, needs OCR
	PagePartial = "partial"  // 50-200 chars — may have garbled OCR
	PageBlank   = "blank"    // 0 chars
)

// PageResult holds extracted text and classification for a single page.
type PageResult struct {
	PageNum  int    `json:"page_num"`  // 1-indexed page number
	Text     string `json:"text"`      // Raw extracted text
	PageType string `json:"page_type"` // digital / scanned / partial / blank
	CharLen  int    `json:"char_len"`  // Number of UTF-8 characters
}

// PDFResult is the complete extraction result for one PDF file.
type PDFResult struct {
	SourceFile    string       `json:"source_file"`
	TotalPages    int          `json:"total_pages"`
	DigitalPages  int          `json:"digital_pages"`
	ScannedPages  []int        `json:"scanned_pages"` // 1-indexed scanned page numbers → sent to AI OCR
	Pages         []PageResult `json:"pages"`
	Error         string       `json:"error,omitempty"`
}

// ParsePDF opens a PDF file and extracts text from every page.
func ParsePDF(pdfPath string) (*PDFResult, error) {
	filename := filepath.Base(pdfPath)

	f, reader, err := pdf.Open(pdfPath)
	if err != nil {
		return &PDFResult{
			SourceFile: filename,
			Error:      fmt.Sprintf("failed to open PDF: %v", err),
		}, err
	}
	defer f.Close()

	totalPages := reader.NumPage()

	result := &PDFResult{
		SourceFile:   filename,
		TotalPages:   totalPages,
		ScannedPages: []int{},
		Pages:        make([]PageResult, 0, totalPages),
	}

	for i := 1; i <= totalPages; i++ {
		page := reader.Page(i)
		if page.V.IsNull() {
			result.Pages = append(result.Pages, PageResult{
				PageNum:  i,
				Text:     "",
				PageType: PageBlank,
				CharLen:  0,
			})
			continue
		}

		text, err := page.GetPlainText(nil)
		if err != nil {
			log.Printf("[parser] page %d text extraction error: %v", i, err)
			text = ""
		}
		text = strings.TrimSpace(text)
		charLen := utf8.RuneCountInString(text)

		pageType := classifyPage(charLen)

		result.Pages = append(result.Pages, PageResult{
			PageNum:  i,
			Text:     text,
			PageType: pageType,
			CharLen:  charLen,
		})

		if pageType == PageDigital {
			result.DigitalPages++
		}
		if pageType == PageScanned || pageType == PagePartial {
			result.ScannedPages = append(result.ScannedPages, i)
		}
	}

	return result, nil
}

// classifyPage mirrors the Python page_classifier thresholds.
func classifyPage(charLen int) string {
	switch {
	case charLen > 200:
		return PageDigital
	case charLen >= 50:
		return PagePartial
	case charLen > 0:
		return PageScanned
	default:
		return PageBlank
	}
}

// ParseAllPDFs parses every PDF in a directory. Returns results keyed by filename.
func ParseAllPDFs(dirPath string) (map[string]*PDFResult, error) {
	entries, err := os.ReadDir(dirPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory %s: %w", dirPath, err)
	}

	results := make(map[string]*PDFResult)
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasSuffix(strings.ToLower(name), ".pdf") {
			continue
		}
		fullPath := filepath.Join(dirPath, name)
		res, err := ParsePDF(fullPath)
		if err != nil {
			log.Printf("[parser] error parsing %s: %v", name, err)
			results[name] = &PDFResult{
				SourceFile: name,
				Error:      err.Error(),
			}
			continue
		}
		results[name] = res
	}

	return results, nil
}
