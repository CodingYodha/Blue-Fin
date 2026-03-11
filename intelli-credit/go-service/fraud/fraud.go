// Package fraud implements the fast GST-Bank statement variance analysis engine.
//
// It reads two file types from the job directory:
//  1. Bank statements (CSV/PDF text) — extracts monthly credit totals
//  2. GST filings (PDF text) — extracts declared monthly turnover
//
// Core computations:
//   - Monthly GST-Bank variance ratio = |GST_turnover - Bank_credits| / Bank_credits
//   - Rolling 3-month moving average of variance
//   - Concentration risk: single-party payment > 40% of total credits
//   - Circular transaction detection: same amount in & out within 3 days
//
// Output: fraud_features.json written to /tmp/intelli-credit/{job_id}/
// This file is read by the ML scoring pipeline (Layer 2 behaviour model).
package fraud

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/xuri/excelize/v2"
)

// BankTransaction represents a single bank statement line item for round-trip detection.
type BankTransaction struct {
	Date        string
	Month       string
	Description string
	Credit      float64
	Debit       float64
}

// FraudFeatures is the output written to fraud_features.json.
type FraudFeatures struct {
	JobID                   string             `json:"job_id"`
	GSTBankVariance         float64            `json:"gst_bank_variance"`           // Average monthly variance ratio
	MaxMonthlyVariance      float64            `json:"max_monthly_variance"`        // Worst single-month variance
	VarianceMonths          int                `json:"variance_months"`             // Months where variance > 20%
	MonthlyVariances        []MonthlyVariance  `json:"monthly_variances"`           // Per-month detail
	ConcentrationRisk       float64            `json:"concentration_risk"`          // Highest single-party share
	ConcentrationParty      string             `json:"concentration_party"`         // Name of highest-share party
	CircularTxnCount        int                `json:"circular_txn_count"`          // Suspected circular transactions
	CircularTxnAmount       float64            `json:"circular_txn_amount"`         // Total amount of circular txns
	TotalBankCredits        float64            `json:"total_bank_credits"`          // Sum of all bank credits
	TotalGSTTurnover        float64            `json:"total_gst_turnover"`          // Sum of all GST declared turnover
	RiskLevel               string             `json:"risk_level"`                  // LOW / MEDIUM / HIGH / CRITICAL
	Flags                   []string           `json:"flags"`                       // Human-readable fraud flags
	Status                  string             `json:"status"`                      // "success" or "partial" or "failed"
	Error                   string             `json:"error,omitempty"`

	// ── Frontend-ready fields ──────────────────────────────────────────────
	GSTBankVariancePct      float64            `json:"gst_bank_variance_pct"`
	GSTBankFlag             string             `json:"gst_bank_flag"`
	GSTBankConfidence       string             `json:"gst_bank_confidence"`
	GSTRMismatchPct         float64            `json:"gstr_mismatch_pct"`
	GSTRFlag                string             `json:"gstr_flag"`
	GSTRConfidence          string             `json:"gstr_confidence"`
	RoundTripCount          int                `json:"round_trip_count"`
	RoundTripFlag           string             `json:"round_trip_flag"`
	RoundTripConfidence     string             `json:"round_trip_confidence"`
	CashDepositRatio        float64            `json:"cash_deposit_ratio"`
	CashFlag                string             `json:"cash_flag"`
	CashConfidence          string             `json:"cash_confidence"`

	// ── Skip flags & coverage ──────────────────────────────────────────────
	ITCMismatchSkipped      bool               `json:"itc_mismatch_skipped"`
	HSNAnomalySkipped       bool               `json:"hsn_anomaly_skipped"`
	FraudCoverage           int                `json:"fraud_coverage"`              // 20/50/85/100

	// ── Python ML pipeline aliases (written to fraud_features.json) ────────
	GSTVsBankVariancePct        float64        `json:"gst_vs_bank_variance_pct"`
	GSTR2A3BITCMismatchPct      float64        `json:"gstr_2a_3b_itc_mismatch_pct"`
	RoundTripTransactionCount   int            `json:"round_trip_transaction_count"`
}

// MonthlyVariance holds the per-month GST vs Bank comparison.
type MonthlyVariance struct {
	Month        string  `json:"month"`         // "2024-01", "2024-02", etc.
	GSTTurnover  float64 `json:"gst_turnover"`
	BankCredits  float64 `json:"bank_credits"`
	VarianceRatio float64 `json:"variance_ratio"` // |GST - Bank| / Bank
}

// AnalyzeFraud runs the complete fraud math engine for a job.
func AnalyzeFraud(jobID, tmpPath string) *FraudFeatures {
	log.Printf("[fraud] AnalyzeFraud START: jobID=%s tmpPath=%s", jobID, tmpPath)

	// List files in tmpPath for debugging
	if dirEntries, err := os.ReadDir(tmpPath); err == nil {
		var names []string
		for _, e := range dirEntries {
			names = append(names, e.Name())
		}
		log.Printf("[fraud] files in tmpPath: %v", names)
	}

	result := &FraudFeatures{
		JobID:            jobID,
		MonthlyVariances: []MonthlyVariance{},
		Flags:            []string{},
		Status:           "success",
	}

	// Detect which GST files are present by upload slot name
	has3B, has2A, has1 := detectGSTFiles(tmpPath)
	log.Printf("[fraud] detected GST files: 3B=%v 2A=%v 1=%v", has3B, has2A, has1)

	// Compute fraud coverage
	switch {
	case has3B && has2A && has1:
		result.FraudCoverage = 100
	case has3B && has2A:
		result.FraudCoverage = 85
	case has3B:
		result.FraudCoverage = 50
	default:
		result.FraudCoverage = 20
	}

	result.ITCMismatchSkipped = !has2A
	result.HSNAnomalySkipped = !has1

	// Look for bank statement CSVs and GST text files
	var allTxns []BankTransaction
	bankCredits := extractBankCredits(tmpPath, &allTxns)
	gstTurnover := extractGSTTurnover(tmpPath)

	log.Printf("[fraud] bankCredits: %d months, data=%v", len(bankCredits), bankCredits)
	log.Printf("[fraud] gstTurnover: %d months, data=%v", len(gstTurnover), gstTurnover)
	log.Printf("[fraud] allTxns: %d transactions", len(allTxns))

	// If GST turnover uses a single 'total' key, distribute across bank months
	if _, hasTotal := gstTurnover["total"]; hasTotal && len(gstTurnover) == 1 {
		totalGST := gstTurnover["total"]
		delete(gstTurnover, "total")
		nMonths := len(bankCredits)
		if nMonths > 0 {
			perMonth := totalGST / float64(nMonths)
			for month := range bankCredits {
				gstTurnover[month] = perMonth
			}
			log.Printf("[fraud] distributed GST total %.2f across %d bank months", totalGST, nMonths)
		}
	}

	if len(bankCredits) == 0 && len(gstTurnover) == 0 {
		result.Status = "partial"
		result.Error = "no bank statement or GST data found"
		result.RiskLevel = "LOW"
		populateFrontendFlags(result)
		return result
	}

	// Compute monthly variances
	allMonths := mergeMonthKeys(bankCredits, gstTurnover)
	var totalVariance float64
	varianceCount := 0

	for _, month := range allMonths {
		bank := bankCredits[month]
		gst := gstTurnover[month]
		result.TotalBankCredits += bank
		result.TotalGSTTurnover += gst

		var ratio float64
		if bank > 0 {
			ratio = math.Abs(gst-bank) / bank
		} else if gst > 0 {
			ratio = 1.0 // GST declared but no bank credits = suspicious
		}

		mv := MonthlyVariance{
			Month:        month,
			GSTTurnover:  gst,
			BankCredits:  bank,
			VarianceRatio: ratio,
		}
		result.MonthlyVariances = append(result.MonthlyVariances, mv)

		totalVariance += ratio
		varianceCount++

		if ratio > result.MaxMonthlyVariance {
			result.MaxMonthlyVariance = ratio
		}
		if ratio > 0.20 {
			result.VarianceMonths++
		}
	}

	if varianceCount > 0 {
		result.GSTBankVariance = totalVariance / float64(varianceCount)
	}

	// Concentration risk from bank statement data
	partyTotals := extractPartyTotals(tmpPath)
	if result.TotalBankCredits > 0 {
		for party, amount := range partyTotals {
			share := amount / result.TotalBankCredits
			if share > result.ConcentrationRisk {
				result.ConcentrationRisk = share
				result.ConcentrationParty = party
			}
		}
	}

	// Generate flags
	if result.GSTBankVariance > 0.30 {
		result.Flags = append(result.Flags, fmt.Sprintf(
			"HIGH GST-Bank variance: %.1f%% average mismatch", result.GSTBankVariance*100))
	}
	if result.MaxMonthlyVariance > 0.50 {
		result.Flags = append(result.Flags, fmt.Sprintf(
			"Single month variance spike: %.1f%%", result.MaxMonthlyVariance*100))
	}
	if result.ConcentrationRisk > 0.40 {
		result.Flags = append(result.Flags, fmt.Sprintf(
			"Payment concentration: %.1f%% to %s", result.ConcentrationRisk*100, result.ConcentrationParty))
	}
	if result.VarianceMonths > 3 {
		result.Flags = append(result.Flags, fmt.Sprintf(
			"%d months with >20%% GST-Bank mismatch", result.VarianceMonths))
	}

	// Round-trip (circular) transaction detection
	circularCount, circularAmount := detectRoundTrips(allTxns)
	result.CircularTxnCount = circularCount
	result.CircularTxnAmount = circularAmount
	if circularCount > 0 {
		result.Flags = append(result.Flags, fmt.Sprintf(
			"Circular transactions detected: %d transactions totalling ₹%.0f",
			circularCount, circularAmount))
	}

	// ITC mismatch: compare GSTR-3B claimed ITC vs GSTR-2A available ITC
	if has2A {
		itc3B := extractITCFromGST(tmpPath, "gst_3b")
		itc2A := extractITCFromGST(tmpPath, "gst_2a")
		log.Printf("[fraud] ITC comparison: 3B claimed=%.2f, 2A available=%.2f", itc3B, itc2A)
		if itc3B > 0 && itc2A > 0 {
			mismatch := math.Abs(itc3B-itc2A) / itc2A * 100
			result.GSTRMismatchPct = math.Round(mismatch*10) / 10
			if mismatch > 25 {
				result.Flags = append(result.Flags, fmt.Sprintf(
					"ITC mismatch: GSTR-3B claims ₹%.0f vs GSTR-2A available ₹%.0f (%.1f%%)", itc3B, itc2A, mismatch))
			}
		}
	}

	// Cash deposit ratio from bank transactions
	totalCash := 0.0
	for _, txn := range allTxns {
		desc := strings.ToLower(txn.Description)
		if txn.Credit > 0 && (strings.Contains(desc, "cash") || strings.Contains(desc, "csh dep") || strings.Contains(desc, "self")) {
			totalCash += txn.Credit
		}
	}
	if result.TotalBankCredits > 0 {
		result.CashDepositRatio = math.Round(totalCash/result.TotalBankCredits*1000) / 10
	}

	// Assign risk level
	result.RiskLevel = computeRiskLevel(result)

	// Populate frontend-ready fields
	populateFrontendFlags(result)

	log.Printf("[fraud] RESULT: variance=%.4f (%.1f%%), itcMismatch=%.1f%%, roundTrips=%d, cashRatio=%.1f%%, risk=%s",
		result.GSTBankVariance, result.GSTBankVariancePct,
		result.GSTRMismatchPct, result.CircularTxnCount,
		result.CashDepositRatio, result.RiskLevel)

	return result
}

// populateFrontendFlags maps internal fraud data to frontend-expected field names.
func populateFrontendFlags(f *FraudFeatures) {
	// GST-Bank variance
	f.GSTBankVariancePct = math.Round(f.GSTBankVariance * 1000) / 10
	switch {
	case f.GSTBankVariance > 0.40:
		f.GSTBankFlag = "CRITICAL"
	case f.GSTBankVariance > 0.25:
		f.GSTBankFlag = "HIGH"
	case f.GSTBankVariance > 0.15:
		f.GSTBankFlag = "MEDIUM"
	default:
		f.GSTBankFlag = "CLEAN"
	}
	f.GSTBankConfidence = "HIGH"

	// GSTR mismatch
	if f.ITCMismatchSkipped {
		f.GSTRFlag = "NOT_CHECKED"
		f.GSTRConfidence = "SKIPPED"
	} else {
		switch {
		case f.GSTRMismatchPct > 25:
			f.GSTRFlag = "HIGH"
		case f.GSTRMismatchPct > 15:
			f.GSTRFlag = "MEDIUM"
		default:
			f.GSTRFlag = "CLEAN"
		}
		f.GSTRConfidence = "HIGH"
	}

	// Round-trip
	f.RoundTripCount = f.CircularTxnCount
	switch {
	case f.CircularTxnCount >= 3:
		f.RoundTripFlag = "HIGH"
	case f.CircularTxnCount >= 1:
		f.RoundTripFlag = "MEDIUM"
	default:
		f.RoundTripFlag = "CLEAN"
	}
	f.RoundTripConfidence = "HIGH"

	// Cash deposit ratio
	switch {
	case f.CashDepositRatio > 50:
		f.CashFlag = "HIGH"
	case f.CashDepositRatio > 30:
		f.CashFlag = "MEDIUM"
	default:
		f.CashFlag = "CLEAN"
	}
	f.CashConfidence = "HIGH"

	// Python ML pipeline aliases — fractions (not percentages) to match training data
	f.GSTVsBankVariancePct = f.GSTBankVariance           // 0.188 for 18.8%
	f.GSTR2A3BITCMismatchPct = f.GSTRMismatchPct / 100   // 0.098 for 9.8%
	f.RoundTripTransactionCount = f.CircularTxnCount
}

// detectGSTFiles checks for GSTR-3B, GSTR-2A, GSTR-1 uploads by slot name prefix.
func detectGSTFiles(tmpPath string) (has3B, has2A, has1 bool) {
	entries, err := os.ReadDir(tmpPath)
	if err != nil {
		return
	}
	for _, entry := range entries {
		name := strings.ToLower(entry.Name())
		// Files are saved as "{slot}__{original_name}" by the backend
		if strings.HasPrefix(name, "gst_3b__") || strings.Contains(name, "gstr-3b") || strings.Contains(name, "gstr3b") {
			has3B = true
		}
		if strings.HasPrefix(name, "gst_2a__") || strings.Contains(name, "gstr-2a") || strings.Contains(name, "gstr2a") {
			has2A = true
		}
		if strings.HasPrefix(name, "gst_1__") || strings.Contains(name, "gstr-1") || strings.Contains(name, "gstr1") {
			has1 = true
		}
		// Backward compat: old single gst_filing counts as 3B
		if strings.HasPrefix(name, "gst_filing__") || strings.HasPrefix(name, "gst_filing.") {
			has3B = true
		}
	}
	return
}

// extractITCFromGST extracts total ITC amount from a specific GST return type.
// slotPrefix is "gst_3b" or "gst_2a" — files are saved as "{slot}__{original_name}".
func extractITCFromGST(tmpPath, slotPrefix string) float64 {
	total := 0.0
	entries, err := os.ReadDir(tmpPath)
	if err != nil {
		return 0
	}
	for _, entry := range entries {
		name := strings.ToLower(entry.Name())
		if !strings.HasPrefix(name, slotPrefix+"__") {
			// Backward compat: gst_filing counts as gst_3b
			if slotPrefix == "gst_3b" && strings.HasPrefix(name, "gst_filing__") {
				// fall through
			} else {
				continue
			}
		}
		fullPath := filepath.Join(tmpPath, entry.Name())
		if strings.HasSuffix(name, ".xlsx") || strings.HasSuffix(name, ".xls") {
			switch slotPrefix {
			case "gst_3b":
				total += parseGSTR3BClaimedITC(fullPath)
			case "gst_2a":
				total += parseGSTR2AITC(fullPath)
			default:
				total += extractITCFromXLSX(fullPath)
			}
		}
		if strings.HasSuffix(name, ".csv") {
			total += extractITCFromCSV(fullPath)
		}
	}
	return total
}

// extractITCFromXLSX reads ITC amount from an XLSX file.
func extractITCFromXLSX(path string) float64 {
	f, err := excelize.OpenFile(path)
	if err != nil {
		return 0
	}
	defer f.Close()

	total := 0.0
	for _, sheet := range f.GetSheetList() {
		rows, err := f.GetRows(sheet)
		if err != nil {
			continue
		}
		headerRow := -1
		itcCol := -1
		for i, row := range rows {
			for j, cell := range row {
				lower := strings.ToLower(strings.TrimSpace(cell))
				if strings.Contains(lower, "itc") || strings.Contains(lower, "input tax") ||
					strings.Contains(lower, "tax credit") || strings.Contains(lower, "igst") ||
					strings.Contains(lower, "cgst") || strings.Contains(lower, "sgst") {
					itcCol = j
					headerRow = i
				}
			}
			if headerRow >= 0 && itcCol >= 0 {
				break
			}
		}
		if headerRow < 0 || itcCol < 0 {
			continue
		}
		for i := headerRow + 1; i < len(rows); i++ {
			if itcCol < len(rows[i]) {
				total += parseAmount(rows[i][itcCol])
			}
		}
	}
	return total
}

// extractITCFromCSV reads ITC amount from a CSV file.
func extractITCFromCSV(path string) float64 {
	f, err := os.Open(path)
	if err != nil {
		return 0
	}
	defer f.Close()

	reader := csv.NewReader(f)
	reader.LazyQuotes = true
	reader.FieldsPerRecord = -1

	header, err := reader.Read()
	if err != nil {
		return 0
	}

	itcCol := -1
	for i, h := range header {
		lower := strings.ToLower(strings.TrimSpace(h))
		if strings.Contains(lower, "itc") || strings.Contains(lower, "input tax") ||
			strings.Contains(lower, "tax credit") {
			itcCol = i
		}
	}
	if itcCol < 0 {
		return 0
	}

	total := 0.0
	for {
		row, err := reader.Read()
		if err != nil {
			break
		}
		if itcCol < len(row) {
			total += parseAmount(row[itcCol])
		}
	}
	return total
}

// computeRiskLevel determines fraud risk from the computed features.
func computeRiskLevel(f *FraudFeatures) string {
	score := 0
	if f.GSTBankVariance > 0.40 {
		score += 3
	} else if f.GSTBankVariance > 0.25 {
		score += 2
	} else if f.GSTBankVariance > 0.15 {
		score += 1
	}

	if f.MaxMonthlyVariance > 0.60 {
		score += 2
	}
	if f.ConcentrationRisk > 0.50 {
		score += 2
	} else if f.ConcentrationRisk > 0.40 {
		score += 1
	}
	if f.VarianceMonths > 4 {
		score += 2
	}
	if f.CircularTxnCount > 0 {
		score += 3
	}
	if f.GSTRMismatchPct > 25 {
		score += 3
	} else if f.GSTRMismatchPct > 15 {
		score += 1
	}
	if f.CashDepositRatio > 50 {
		score += 2
	} else if f.CashDepositRatio > 30 {
		score += 1
	}

	switch {
	case score >= 7:
		return "CRITICAL"
	case score >= 4:
		return "HIGH"
	case score >= 2:
		return "MEDIUM"
	default:
		return "LOW"
	}
}

// WriteFraudJSON writes results to fraud_features.json.
func WriteFraudJSON(features *FraudFeatures, jobDir string) error {
	outPath := filepath.Join(jobDir, "fraud_features.json")
	data, err := json.MarshalIndent(features, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal fraud features: %w", err)
	}
	if err := os.WriteFile(outPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write fraud_features.json: %w", err)
	}
	log.Printf("[fraud] wrote fraud_features.json to %s", outPath)
	return nil
}

// =============================================================================
// Data extraction helpers
// =============================================================================

// amountRegex matches Indian currency amounts like "1,23,456.78" or "123456"
var amountRegex = regexp.MustCompile(`[\d,]+\.?\d*`)

// monthRegex matches YYYY-MM patterns
var monthRegex = regexp.MustCompile(`\d{4}-\d{2}`)

// extractBankCredits reads bank statement CSVs/XLSX/text and extracts monthly credit totals.
func extractBankCredits(tmpPath string, txns *[]BankTransaction) map[string]float64 {
	credits := make(map[string]float64)

	entries, err := os.ReadDir(tmpPath)
	if err != nil {
		return credits
	}

	for _, entry := range entries {
		name := strings.ToLower(entry.Name())
		if !strings.Contains(name, "bank") && !strings.Contains(name, "statement") {
			continue
		}

		fullPath := filepath.Join(tmpPath, entry.Name())

		if strings.HasSuffix(name, ".xlsx") || strings.HasSuffix(name, ".xls") {
			parseBankXLSX(fullPath, credits, txns)
		}
		if strings.HasSuffix(name, ".csv") {
			parseBankCSV(fullPath, credits)
		}
		// For text files that might have been pre-extracted
		if strings.HasSuffix(name, ".txt") || strings.HasSuffix(name, ".json") {
			parseBankText(fullPath, credits)
		}
	}

	return credits
}

func parseBankCSV(path string, credits map[string]float64) {
	f, err := os.Open(path)
	if err != nil {
		log.Printf("[fraud] cannot open bank CSV %s: %v", path, err)
		return
	}
	defer f.Close()

	reader := csv.NewReader(f)
	reader.LazyQuotes = true
	reader.FieldsPerRecord = -1

	header, err := reader.Read()
	if err != nil {
		return
	}

	// Find date and credit columns
	dateCol, creditCol := -1, -1
	for i, h := range header {
		lower := strings.ToLower(strings.TrimSpace(h))
		if strings.Contains(lower, "date") || strings.Contains(lower, "txn") {
			if dateCol == -1 {
				dateCol = i
			}
		}
		if strings.Contains(lower, "credit") || strings.Contains(lower, "deposit") {
			creditCol = i
		}
	}

	if dateCol == -1 || creditCol == -1 {
		log.Printf("[fraud] bank CSV %s: could not identify date/credit columns", path)
		return
	}

	for {
		row, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			continue
		}
		if creditCol >= len(row) || dateCol >= len(row) {
			continue
		}

		month := extractMonthFromDate(row[dateCol])
		if month == "" {
			continue
		}
		amount := parseAmount(row[creditCol])
		if amount > 0 {
			credits[month] += amount
		}
	}
}

func parseBankText(path string, credits map[string]float64) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	// Try JSON format first
	var records []map[string]interface{}
	if json.Unmarshal(data, &records) == nil {
		for _, rec := range records {
			month := ""
			credit := 0.0
			for k, v := range rec {
				lower := strings.ToLower(k)
				if strings.Contains(lower, "date") || strings.Contains(lower, "month") {
					month = extractMonthFromDate(fmt.Sprintf("%v", v))
				}
				if strings.Contains(lower, "credit") || strings.Contains(lower, "deposit") {
					credit = parseAmount(fmt.Sprintf("%v", v))
				}
			}
			if month != "" && credit > 0 {
				credits[month] += credit
			}
		}
	}
}

// extractGSTTurnover reads GST filing text/CSV and extracts monthly declared turnover.
// Matches files with "gst" in the name (gst_3b, gst_filing, gstr-3b, etc.)
// Skips GSTR-2A files — they contain supplier ITC data, not turnover.
func extractGSTTurnover(tmpPath string) map[string]float64 {
	turnover := make(map[string]float64)

	entries, err := os.ReadDir(tmpPath)
	if err != nil {
		return turnover
	}

	for _, entry := range entries {
		name := strings.ToLower(entry.Name())
		if !strings.Contains(name, "gst") {
			continue
		}
		// Skip GSTR-2A files — no turnover data
		if strings.HasPrefix(name, "gst_2a__") || strings.Contains(name, "2a") {
			continue
		}
		fullPath := filepath.Join(tmpPath, entry.Name())

		if strings.HasSuffix(name, ".xlsx") || strings.HasSuffix(name, ".xls") {
			// Use GSTR-3B key-value parser for 3B files
			if strings.HasPrefix(name, "gst_3b__") || strings.HasPrefix(name, "gst_filing__") ||
				strings.Contains(name, "3b") {
				parseGSTR3BTurnover(fullPath, turnover)
				if len(turnover) > 0 {
					continue
				}
			}
			// Fall back to generic column-scanning parser
			parseGSTXLSX(fullPath, turnover)
		}
		if strings.HasSuffix(name, ".csv") {
			parseGSTCSV(fullPath, turnover)
		}
		if strings.HasSuffix(name, ".json") {
			parseGSTJSON(fullPath, turnover)
		}
	}

	return turnover
}

func parseGSTCSV(path string, turnover map[string]float64) {
	f, err := os.Open(path)
	if err != nil {
		return
	}
	defer f.Close()

	reader := csv.NewReader(f)
	reader.LazyQuotes = true
	reader.FieldsPerRecord = -1

	header, err := reader.Read()
	if err != nil {
		return
	}

	monthCol, amountCol := -1, -1
	for i, h := range header {
		lower := strings.ToLower(strings.TrimSpace(h))
		if strings.Contains(lower, "month") || strings.Contains(lower, "period") || strings.Contains(lower, "date") {
			if monthCol == -1 {
				monthCol = i
			}
		}
		if strings.Contains(lower, "turnover") || strings.Contains(lower, "taxable") || strings.Contains(lower, "total") || strings.Contains(lower, "amount") {
			amountCol = i
		}
	}

	if monthCol == -1 || amountCol == -1 {
		return
	}

	for {
		row, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			continue
		}
		if monthCol >= len(row) || amountCol >= len(row) {
			continue
		}

		month := extractMonthFromDate(row[monthCol])
		if month == "" {
			continue
		}
		amount := parseAmount(row[amountCol])
		if amount > 0 {
			turnover[month] += amount
		}
	}
}

func parseGSTJSON(path string, turnover map[string]float64) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var records []map[string]interface{}
	if json.Unmarshal(data, &records) == nil {
		for _, rec := range records {
			month := ""
			amount := 0.0
			for k, v := range rec {
				lower := strings.ToLower(k)
				if strings.Contains(lower, "month") || strings.Contains(lower, "period") {
					month = extractMonthFromDate(fmt.Sprintf("%v", v))
				}
				if strings.Contains(lower, "turnover") || strings.Contains(lower, "taxable") {
					amount = parseAmount(fmt.Sprintf("%v", v))
				}
			}
			if month != "" && amount > 0 {
				turnover[month] += amount
			}
		}
	}
}

// extractPartyTotals reads bank statements for payer/payee concentration analysis.
func extractPartyTotals(tmpPath string) map[string]float64 {
	totals := make(map[string]float64)

	entries, err := os.ReadDir(tmpPath)
	if err != nil {
		return totals
	}

	for _, entry := range entries {
		name := strings.ToLower(entry.Name())
		if !strings.Contains(name, "bank") && !strings.Contains(name, "statement") {
			continue
		}

		fullPath := filepath.Join(tmpPath, entry.Name())

		if strings.HasSuffix(name, ".xlsx") || strings.HasSuffix(name, ".xls") {
			parsePartyXLSX(fullPath, totals)
			continue
		}
		if !strings.HasSuffix(name, ".csv") {
			continue
		}

		f, err := os.Open(fullPath)
		if err != nil {
			continue
		}
		defer f.Close()

		reader := csv.NewReader(f)
		reader.LazyQuotes = true
		reader.FieldsPerRecord = -1

		header, err := reader.Read()
		if err != nil {
			continue
		}

		partyCol, creditCol := -1, -1
		for i, h := range header {
			lower := strings.ToLower(strings.TrimSpace(h))
			if strings.Contains(lower, "party") || strings.Contains(lower, "narration") ||
				strings.Contains(lower, "description") || strings.Contains(lower, "particular") || strings.Contains(lower, "payee") {
				if partyCol == -1 {
					partyCol = i
				}
			}
			if strings.Contains(lower, "credit") || strings.Contains(lower, "deposit") {
				creditCol = i
			}
		}

		if partyCol == -1 || creditCol == -1 {
			continue
		}

		for {
			row, err := reader.Read()
			if err != nil {
				break
			}
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

	return totals
}

// =============================================================================
// Utility helpers
// =============================================================================

// parseAmount converts an Indian-format number string to float64.
func parseAmount(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" || s == "0" || s == "—" || s == "–" {
		return 0
	}
	// Remove commas (Indian: 1,23,456.78 or Western: 123,456.78)
	s = strings.ReplaceAll(s, ",", "")
	// Remove currency symbols
	s = strings.ReplaceAll(s, "₹", "")
	s = strings.ReplaceAll(s, "Rs", "")
	s = strings.ReplaceAll(s, "INR", "")
	s = strings.TrimSpace(s)

	val, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0
	}
	return val
}

// extractMonthFromDate tries to pull a YYYY-MM from a date string.
func extractMonthFromDate(dateStr string) string {
	dateStr = strings.TrimSpace(dateStr)
	// Try YYYY-MM direct match
	if m := monthRegex.FindString(dateStr); m != "" {
		return m
	}

	// Try DD/MM/YYYY or DD-MM-YYYY (Indian format)
	parts := regexp.MustCompile(`[/\-.]`).Split(dateStr, -1)
	if len(parts) >= 3 {
		// Could be DD/MM/YYYY or YYYY/MM/DD
		p0, p2 := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[2])
		p1 := strings.TrimSpace(parts[1])
		if len(p0) == 4 {
			// YYYY-MM-DD
			return p0 + "-" + padTwo(p1)
		}
		if len(p2) == 4 {
			// DD-MM-YYYY or MM-DD-YYYY (assume Indian DD-MM-YYYY)
			return p2 + "-" + padTwo(p1)
		}
		if len(p2) == 2 {
			// DD-MM-YY
			year := "20" + p2
			return year + "-" + padTwo(p1)
		}
	}
	return ""
}

func padTwo(s string) string {
	if len(s) == 1 {
		return "0" + s
	}
	return s
}

// mergeMonthKeys returns sorted unique month keys from two maps.
func mergeMonthKeys(a, b map[string]float64) []string {
	seen := make(map[string]bool)
	for k := range a {
		seen[k] = true
	}
	for k := range b {
		seen[k] = true
	}
	keys := make([]string, 0, len(seen))
	for k := range seen {
		keys = append(keys, k)
	}
	// Sort chronologically (YYYY-MM sorts lexicographically)
	for i := 0; i < len(keys); i++ {
		for j := i + 1; j < len(keys); j++ {
			if keys[j] < keys[i] {
				keys[i], keys[j] = keys[j], keys[i]
			}
		}
	}
	return keys
}

// detectRoundTrips looks for circular transactions: a credit followed by a matching
// debit (or split debits) within 72 hours, with 2% amount tolerance, minimum ₹10 lakh.
func detectRoundTrips(txns []BankTransaction) (int, float64) {
	const (
		windowHours    = 72
		tolerance      = 0.02
		minAmountLakhs = 1000000.0 // ₹10 lakh
	)

	if len(txns) == 0 {
		return 0, 0
	}

	// Separate credits and debits
	type timedTxn struct {
		amount float64
		date   time.Time
		desc   string
	}

	var credits, debits []timedTxn
	for _, t := range txns {
		parsed := parseDate(t.Date)
		if parsed.IsZero() {
			continue
		}
		if t.Credit >= minAmountLakhs {
			credits = append(credits, timedTxn{amount: t.Credit, date: parsed, desc: t.Description})
		}
		if t.Debit >= minAmountLakhs {
			debits = append(debits, timedTxn{amount: t.Debit, date: parsed, desc: t.Description})
		}
	}

	count := 0
	totalAmount := 0.0
	usedDebits := make(map[int]bool)

	for _, cr := range credits {
		// Look for matching debits within 72h window
		remainingAmount := cr.amount
		for j, db := range debits {
			if usedDebits[j] {
				continue
			}
			// Check time window: debit must be after credit and within 72h
			diff := db.date.Sub(cr.date)
			if diff < 0 || diff > time.Duration(windowHours)*time.Hour {
				continue
			}
			// Check amount tolerance (exact or split)
			if db.amount > remainingAmount*(1+tolerance) {
				continue
			}
			if db.amount >= remainingAmount*(1-tolerance) {
				// Full match
				usedDebits[j] = true
				count++
				totalAmount += cr.amount
				remainingAmount = 0
				break
			}
			// Split match: debit is part of the credit
			if db.amount >= minAmountLakhs {
				usedDebits[j] = true
				remainingAmount -= db.amount
				if remainingAmount <= cr.amount*tolerance {
					// Close enough — split matched
					count++
					totalAmount += cr.amount
					break
				}
			}
		}
	}

	return count, totalAmount
}

// parseDate attempts to parse common Indian date formats.
func parseDate(s string) time.Time {
	s = strings.TrimSpace(s)
	formats := []string{
		"2006-01-02",
		"02/01/2006",
		"02-01-2006",
		"02.01.2006",
		"2006/01/02",
		"02-Jan-2006",
		"02 Jan 2006",
		"01/02/2006",
	}
	for _, f := range formats {
		if t, err := time.Parse(f, s); err == nil {
			return t
		}
	}
	return time.Time{}
}
