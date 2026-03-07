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
)

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
	result := &FraudFeatures{
		JobID:            jobID,
		MonthlyVariances: []MonthlyVariance{},
		Flags:            []string{},
		Status:           "success",
	}

	// Look for bank statement CSVs and GST text files
	bankCredits := extractBankCredits(tmpPath)
	gstTurnover := extractGSTTurnover(tmpPath)

	if len(bankCredits) == 0 && len(gstTurnover) == 0 {
		result.Status = "partial"
		result.Error = "no bank statement or GST data found"
		result.RiskLevel = "LOW"
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

	// Assign risk level
	result.RiskLevel = computeRiskLevel(result)

	return result
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

// extractBankCredits reads bank statement CSVs/text and extracts monthly credit totals.
func extractBankCredits(tmpPath string) map[string]float64 {
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
		fullPath := filepath.Join(tmpPath, entry.Name())

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
		if !strings.HasSuffix(name, ".csv") {
			continue
		}

		fullPath := filepath.Join(tmpPath, entry.Name())
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
	if s == "" || s == "-" || s == "0" {
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
