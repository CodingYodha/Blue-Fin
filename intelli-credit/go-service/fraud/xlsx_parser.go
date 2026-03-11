// Package fraud — XLSX parsing for bank statements and GST filings.
// Uses excelize/v2 to read .xlsx files uploaded by the user.
package fraud

import (
	"log"
	"path/filepath"
	"strings"

	"github.com/xuri/excelize/v2"
)

// parseBankXLSX reads a bank statement XLSX with the standard Indian layout:
//
//	Rows 1-3: merged header / title / note rows  (skipped)
//	Row  4:   column headers — Date | Value Date | Description | Ref/Chq No | Debit | Credit | Balance
//	Row  5+:  data rows
func parseBankXLSX(path string, credits map[string]float64, txns *[]BankTransaction) {
	f, err := excelize.OpenFile(path)
	if err != nil {
		log.Printf("[fraud] cannot open bank XLSX %s: %v", path, err)
		return
	}
	defer f.Close()

	sheetName := f.GetSheetName(0)
	rows, err := f.GetRows(sheetName)
	if err != nil {
		log.Printf("[fraud] cannot read rows from %s sheet %s: %v", path, sheetName, err)
		return
	}

	log.Printf("[fraud] bank XLSX %s: sheet=%s totalRows=%d", path, sheetName, len(rows))

	// Fixed layout constants (0-indexed)
	const headerIdx = 3   // row 4
	const dataStart = 4   // row 5
	const dateCol = 0     // column A  — Txn Date
	const descCol = 2     // column C  — Description
	const debitCol = 4    // column E  — Debit
	const creditCol = 5   // column F  — Credit

	if len(rows) <= dataStart {
		log.Printf("[fraud] bank XLSX %s: only %d rows, need at least %d", path, len(rows), dataStart+1)
		return
	}

	if headerIdx < len(rows) {
		log.Printf("[fraud] bank XLSX header row: %v", rows[headerIdx])
	}

	skipLabels := []string{"opening balance", "closing balance", "circular trade", "fraud"}
	parsed := 0

	for i := dataStart; i < len(rows); i++ {
		row := rows[i]
		dateStr := safeCell(row, dateCol)
		if dateStr == "" {
			continue
		}

		desc := safeCell(row, descCol)
		descLower := strings.ToLower(desc)
		if desc == "" {
			continue
		}

		skip := false
		for _, lbl := range skipLabels {
			if strings.Contains(descLower, lbl) {
				skip = true
				break
			}
		}
		if skip {
			continue
		}

		month := extractMonthFromDate(dateStr)
		if month == "" {
			continue
		}

		creditAmt := parseAmount(safeCell(row, creditCol))
		debitAmt := parseAmount(safeCell(row, debitCol))

		if creditAmt > 0 {
			credits[month] += creditAmt
		}

		if txns != nil && (creditAmt > 0 || debitAmt > 0) {
			*txns = append(*txns, BankTransaction{
				Date:        dateStr,
				Month:       month,
				Description: desc,
				Credit:      creditAmt,
				Debit:       debitAmt,
			})
		}
		parsed++
	}

	log.Printf("[fraud] bank XLSX %s: parsed %d data rows", path, parsed)
}

// parseGSTXLSX reads a GST filing XLSX (potentially multi-sheet) and extracts monthly turnover.
func parseGSTXLSX(path string, turnover map[string]float64) {
	f, err := excelize.OpenFile(path)
	if err != nil {
		log.Printf("[fraud] cannot open GST XLSX %s: %v", path, err)
		return
	}
	defer f.Close()

	sheets := f.GetSheetList()
	for _, sheet := range sheets {
		lowerSheet := strings.ToLower(sheet)
		// Prioritize GSTR-3B Summary sheets for monthly turnover
		if strings.Contains(lowerSheet, "3b") || strings.Contains(lowerSheet, "summary") ||
			strings.Contains(lowerSheet, "gstr") || len(sheets) == 1 {
			parseGSTSheet(f, sheet, turnover)
		}
	}
}

// parseGSTSheet extracts monthly turnover from a single GST sheet.
func parseGSTSheet(f *excelize.File, sheet string, turnover map[string]float64) {
	rows, err := f.GetRows(sheet)
	if err != nil {
		log.Printf("[fraud] cannot read GST sheet %s: %v", sheet, err)
		return
	}

	// Find header row with month/period and turnover/taxable/amount columns
	headerRow := -1
	monthCol, amountCol := -1, -1
	for i, row := range rows {
		for j, cell := range row {
			lower := strings.ToLower(strings.TrimSpace(cell))
			if strings.Contains(lower, "month") || strings.Contains(lower, "period") ||
				strings.Contains(lower, "date") || strings.Contains(lower, "return period") {
				if monthCol == -1 {
					monthCol = j
					headerRow = i
				}
			}
			if strings.Contains(lower, "turnover") || strings.Contains(lower, "taxable") ||
				strings.Contains(lower, "total") || strings.Contains(lower, "amount") ||
				strings.Contains(lower, "value") {
				amountCol = j
			}
		}
		if headerRow >= 0 && amountCol >= 0 {
			break
		}
		if headerRow >= 0 && amountCol < 0 {
			headerRow, monthCol = -1, -1
		}
	}

	if headerRow < 0 || monthCol < 0 || amountCol < 0 {
		log.Printf("[fraud] GST sheet %s: could not identify month+amount columns", sheet)
		return
	}

	for i := headerRow + 1; i < len(rows); i++ {
		row := rows[i]
		if monthCol >= len(row) || amountCol >= len(row) {
			continue
		}

		month := extractMonthFromDate(strings.TrimSpace(row[monthCol]))
		if month == "" {
			continue
		}
		amount := parseAmount(row[amountCol])
		if amount > 0 {
			turnover[month] += amount
		}
	}
}

// parsePartyXLSX reads party concentration data from a bank statement XLSX.
func parsePartyXLSX(path string, totals map[string]float64) {
	f, err := excelize.OpenFile(path)
	if err != nil {
		return
	}
	defer f.Close()

	sheetName := f.GetSheetName(0)
	rows, err := f.GetRows(sheetName)
	if err != nil {
		return
	}

	headerRow := -1
	partyCol, creditCol := -1, -1
	for i, row := range rows {
		for j, cell := range row {
			lower := strings.ToLower(strings.TrimSpace(cell))
			if strings.Contains(lower, "party") || strings.Contains(lower, "narration") ||
				strings.Contains(lower, "description") || strings.Contains(lower, "particular") {
				if partyCol == -1 {
					partyCol = j
					headerRow = i
				}
			}
			if strings.Contains(lower, "credit") || strings.Contains(lower, "deposit") {
				creditCol = j
			}
		}
		if headerRow >= 0 && creditCol >= 0 {
			break
		}
		if headerRow >= 0 && creditCol < 0 {
			headerRow, partyCol = -1, -1
		}
	}

	if headerRow < 0 || partyCol < 0 || creditCol < 0 {
		return
	}

	for i := headerRow + 1; i < len(rows); i++ {
		row := rows[i]
		if partyCol >= len(row) || creditCol >= len(row) {
			continue
		}
		party := strings.TrimSpace(row[partyCol])
		if party == "" {
			continue
		}
		amount := parseAmount(row[creditCol])
		if amount > 0 {
			totals[party] += amount
		}
	}
}

// safeCell returns the cell value at index col, or "" if out of range.
func safeCell(row []string, col int) string {
	if col < 0 || col >= len(row) {
		return ""
	}
	return strings.TrimSpace(row[col])
}

// ─────────────────────────────────────────────────────────────────────────────
// GSTR-3B  (key-value layout on "GSTR-3B Summary" sheet)
// ─────────────────────────────────────────────────────────────────────────────

// parseGSTR3BTurnover extracts monthly turnover from a GSTR-3B Summary sheet.
// Looks for "3.1(a) Outward taxable supplies" / "Taxable Value" row and sums B+C+D.
// If column headers contain month labels, turnover is stored per-month; otherwise
// summed and assigned to a month extracted from the filename (or key "total").
func parseGSTR3BTurnover(path string, turnover map[string]float64) {
	f, err := excelize.OpenFile(path)
	if err != nil {
		log.Printf("[fraud] cannot open GSTR-3B XLSX %s: %v", path, err)
		return
	}
	defer f.Close()

	sheetName := find3BSheet(f)
	rows, err := f.GetRows(sheetName)
	if err != nil {
		log.Printf("[fraud] cannot read GSTR-3B sheet %s: %v", sheetName, err)
		return
	}
	log.Printf("[fraud] GSTR-3B %s: sheet=%s rows=%d", path, sheetName, len(rows))

	// Try to detect month labels in the first few header rows (columns B, C, D)
	type mc struct {
		col   int
		month string
	}
	var monthCols []mc
	for i := 0; i < 5 && i < len(rows); i++ {
		for j := 1; j <= 3 && j < len(rows[i]); j++ {
			cell := strings.TrimSpace(rows[i][j])
			if m := extractMonthFromDate(cell); m != "" {
				monthCols = append(monthCols, mc{j, m})
			} else if m := extractMonthFromName(cell); m != "" {
				monthCols = append(monthCols, mc{j, m})
			}
		}
		if len(monthCols) > 0 {
			break
		}
	}

	// Fallback: derive month from the filename itself
	fallbackMonth := extractMonthFromName(filepath.Base(path))

	for i, row := range rows {
		if len(row) == 0 {
			continue
		}
		label := strings.ToLower(strings.TrimSpace(row[0]))
		if strings.Contains(label, "taxable value") ||
			(strings.Contains(label, "3.1") && strings.Contains(label, "outward")) {

			if len(monthCols) > 0 {
				for _, mc := range monthCols {
					amt := parseAmount(safeCell(row, mc.col))
					if amt > 0 {
						turnover[mc.month] += amt
						log.Printf("[fraud] GSTR-3B row %d: turnover[%s] += %.2f", i+1, mc.month, amt)
					}
				}
			} else {
				total := parseAmount(safeCell(row, 1)) + parseAmount(safeCell(row, 2)) + parseAmount(safeCell(row, 3))
				if total > 0 {
					month := fallbackMonth
					if month == "" {
						month = "total"
					}
					turnover[month] += total
					log.Printf("[fraud] GSTR-3B row %d: turnover[%s] = %.2f (sum B+C+D)", i+1, month, total)
				}
			}
			break
		}
	}
}

// parseGSTR3BClaimedITC extracts the ITC claimed amount from a GSTR-3B Summary.
// Searches for "4(A)(5) All other ITC" row → column B value.
func parseGSTR3BClaimedITC(path string) float64 {
	f, err := excelize.OpenFile(path)
	if err != nil {
		log.Printf("[fraud] cannot open GSTR-3B XLSX for ITC %s: %v", path, err)
		return 0
	}
	defer f.Close()

	sheetName := find3BSheet(f)
	rows, err := f.GetRows(sheetName)
	if err != nil {
		return 0
	}

	for i, row := range rows {
		if len(row) == 0 {
			continue
		}
		label := strings.ToLower(strings.TrimSpace(row[0]))
		if strings.Contains(label, "4(a)(5)") || strings.Contains(label, "all other itc") {
			itc := parseAmount(safeCell(row, 1))
			log.Printf("[fraud] GSTR-3B row %d: claimed ITC = %.2f", i+1, itc)
			return itc
		}
	}
	log.Printf("[fraud] GSTR-3B %s: could not find ITC claimed row (4(A)(5))", path)
	return 0
}

// find3BSheet returns the sheet name matching "3b" or "summary", falling back to the first sheet.
func find3BSheet(f *excelize.File) string {
	for _, s := range f.GetSheetList() {
		lower := strings.ToLower(s)
		if strings.Contains(lower, "3b") || strings.Contains(lower, "summary") {
			return s
		}
	}
	return f.GetSheetName(0)
}

// ─────────────────────────────────────────────────────────────────────────────
// GSTR-2A  (tabular supplier data on a sheet named like "GSTR-2A Oct-2024")
// ─────────────────────────────────────────────────────────────────────────────

// parseGSTR2AITC extracts total ITC (IGST + CGST + SGST) from a GSTR-2A XLSX.
//
//	Layout: 3 merged header rows → row 4 = column headers → data rows.
//	Sums IGST / CGST / SGST columns across data rows until a "TOTAL" or empty row.
func parseGSTR2AITC(path string) float64 {
	f, err := excelize.OpenFile(path)
	if err != nil {
		log.Printf("[fraud] cannot open GSTR-2A XLSX %s: %v", path, err)
		return 0
	}
	defer f.Close()

	// Find a sheet whose name contains "2a"
	var sheetName string
	for _, s := range f.GetSheetList() {
		lower := strings.ToLower(s)
		if strings.Contains(lower, "2a") {
			sheetName = s
			break
		}
	}
	if sheetName == "" {
		sheetName = f.GetSheetName(0)
	}

	rows, err := f.GetRows(sheetName)
	if err != nil {
		log.Printf("[fraud] cannot read GSTR-2A sheet %s: %v", sheetName, err)
		return 0
	}
	log.Printf("[fraud] GSTR-2A %s: sheet=%s rows=%d", path, sheetName, len(rows))

	const headerIdx = 3 // row 4
	const dataStart = 4 // row 5

	if len(rows) <= dataStart {
		log.Printf("[fraud] GSTR-2A %s: too few rows (%d)", path, len(rows))
		return 0
	}

	// Detect IGST / CGST / SGST columns from header row, fallback to fixed 7/8/9
	igstCol, cgstCol, sgstCol := -1, -1, -1
	if headerIdx < len(rows) {
		for j, cell := range rows[headerIdx] {
			lower := strings.ToLower(strings.TrimSpace(cell))
			if strings.Contains(lower, "igst") && igstCol == -1 {
				igstCol = j
			}
			if strings.Contains(lower, "cgst") && cgstCol == -1 {
				cgstCol = j
			}
			if (strings.Contains(lower, "sgst") || strings.Contains(lower, "utgst")) && sgstCol == -1 {
				sgstCol = j
			}
		}
		log.Printf("[fraud] GSTR-2A header: %v", rows[headerIdx])
	}
	if igstCol == -1 {
		igstCol = 7
	}
	if cgstCol == -1 {
		cgstCol = 8
	}
	if sgstCol == -1 {
		sgstCol = 9
	}
	log.Printf("[fraud] GSTR-2A tax columns: IGST=%d CGST=%d SGST=%d", igstCol, cgstCol, sgstCol)

	total := 0.0
	dataRows := 0
	for i := dataStart; i < len(rows); i++ {
		row := rows[i]
		if len(row) == 0 {
			break
		}
		first := strings.ToLower(strings.TrimSpace(row[0]))
		if first == "" || strings.Contains(first, "total") {
			break
		}

		igst := parseDashAmount(safeCell(row, igstCol))
		cgst := parseDashAmount(safeCell(row, cgstCol))
		sgst := parseDashAmount(safeCell(row, sgstCol))
		total += igst + cgst + sgst
		dataRows++
	}

	log.Printf("[fraud] GSTR-2A %s: %d data rows, total ITC = %.2f", path, dataRows, total)
	return total
}

// parseDashAmount handles GSTR-2A amounts: treats "—" / "–" as zero, then delegates to parseAmount.
func parseDashAmount(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "—" || s == "–" {
		return 0
	}
	return parseAmount(s)
}

// ─────────────────────────────────────────────────────────────────────────────
// Month-from-name helper  (e.g. "Oct2024" → "2024-10")
// ─────────────────────────────────────────────────────────────────────────────

// extractMonthFromName parses a month name + 4-digit year from a string like
// "Oct-2024", "GSTR3B_Oct2024.xlsx", "November 2024", etc.
func extractMonthFromName(s string) string {
	s = strings.ToLower(s)
	for _, ext := range []string{".xlsx", ".xls", ".csv", ".pdf"} {
		s = strings.TrimSuffix(s, ext)
	}

	// Longest names first so "january" matches before "jan"
	months := []struct{ name, num string }{
		{"september", "09"}, {"october", "10"}, {"november", "11"}, {"december", "12"},
		{"february", "02"}, {"january", "01"}, {"august", "08"},
		{"march", "03"}, {"april", "04"}, {"july", "07"}, {"june", "06"},
		{"may", "05"},
		{"jan", "01"}, {"feb", "02"}, {"mar", "03"}, {"apr", "04"},
		{"jun", "06"}, {"jul", "07"}, {"aug", "08"}, {"sep", "09"},
		{"oct", "10"}, {"nov", "11"}, {"dec", "12"},
	}

	monthNum := ""
	for _, m := range months {
		if strings.Contains(s, m.name) {
			monthNum = m.num
			break
		}
	}
	if monthNum == "" {
		return ""
	}

	// Look for a 4-digit year anywhere in the string
	for i := 0; i <= len(s)-4; i++ {
		y := s[i : i+4]
		if y >= "2000" && y <= "2099" && isAllDigits(y) {
			return y + "-" + monthNum
		}
	}
	return ""
}

func isAllDigits(s string) bool {
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return len(s) > 0
}
