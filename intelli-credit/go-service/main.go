package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"

	"intelli-credit/go-service/chunker"
	"intelli-credit/go-service/fraud"
	"intelli-credit/go-service/parser"
)

// parseRequest is the JSON body the backend sends to POST /parse.
type parseRequest struct {
	JobID   string `json:"job_id"   binding:"required"`
	TmpPath string `json:"tmp_path" binding:"required"`
}

// fraudRequest is the JSON body the backend sends to POST /fraud.
type fraudRequest struct {
	JobID   string `json:"job_id"   binding:"required"`
	TmpPath string `json:"tmp_path" binding:"required"`
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8081"
	}

	r := gin.Default()

	// ── Health check ─────────────────────────────────────────────────────
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "go-service"})
	})

	// ── POST /parse — PDF parsing + chunking → writes chunks.json ────────
	r.POST("/parse", handleParse)

	// ── POST /fraud — GST-Bank variance analysis → returns fraud features ─
	r.POST("/fraud", handleFraud)

	log.Printf("[go-service] listening on :%s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("failed to start server: %v", err)
	}
}

// handleParse parses all PDFs in the job directory, chunks them, and writes
// /tmp/intelli-credit/{job_id}/chunks.json for the RAG pipeline.
func handleParse(c *gin.Context) {
	var req parseRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate job directory exists
	jobDir := req.TmpPath
	if !isValidJobDir(jobDir) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid or missing job directory"})
		return
	}

	log.Printf("[parse] starting PDF parse for job %s at %s", req.JobID, jobDir)

	// Parse all PDFs in the directory
	pdfResults, err := parser.ParseAllPDFs(jobDir)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": fmt.Sprintf("failed to parse PDFs: %v", err),
		})
		return
	}

	if len(pdfResults) == 0 {
		c.JSON(http.StatusOK, gin.H{
			"job_id":           req.JobID,
			"status":           "success",
			"tables_extracted": 0,
			"scanned_pages":    []int{},
			"text_path":        "",
			"ratios":           map[string]interface{}{},
			"message":          "no PDF files found in job directory",
		})
		return
	}

	// Chunk all parsed documents → chunks.json
	var allChunks []chunker.Chunk
	var allScannedPages []int
	totalTables := 0

	for filename, result := range pdfResults {
		if result.Error != "" {
			log.Printf("[parse] skipping %s: %s", filename, result.Error)
			continue
		}

		docType := parser.DetectDocType(filename)

		// Chunk the document (bank statements are auto-skipped by chunker)
		docChunks := chunker.ChunkDocument(result.Pages, docType, filename)
		allChunks = append(allChunks, docChunks...)

		// Collect scanned pages for OCR stage
		for _, sp := range result.ScannedPages {
			allScannedPages = append(allScannedPages, sp)
		}

		// Count digital pages as "tables extracted" (approximate)
		totalTables += result.DigitalPages
	}

	// Write chunks.json
	if len(allChunks) > 0 {
		if err := chunker.WriteChunksJSON(allChunks, jobDir); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": fmt.Sprintf("failed to write chunks.json: %v", err),
			})
			return
		}
	} else {
		// Write empty array so downstream doesn't fail on missing file
		if err := chunker.WriteChunksJSON([]chunker.Chunk{}, jobDir); err != nil {
			log.Printf("[parse] warning: could not write empty chunks.json: %v", err)
		}
	}

	log.Printf("[parse] job %s complete: %d PDFs → %d chunks, %d scanned pages",
		req.JobID, len(pdfResults), len(allChunks), len(allScannedPages))

	c.JSON(http.StatusOK, gin.H{
		"job_id":           req.JobID,
		"status":           "success",
		"tables_extracted": totalTables,
		"scanned_pages":    allScannedPages,
		"text_path":        filepath.Join(jobDir, "chunks.json"),
		"chunks_produced":  len(allChunks),
		"pdfs_parsed":      len(pdfResults),
		"ratios":           map[string]interface{}{},
	})
}

// handleFraud runs the GST-Bank variance analysis engine and returns fraud features.
func handleFraud(c *gin.Context) {
	var req fraudRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	jobDir := req.TmpPath
	if !isValidJobDir(jobDir) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid or missing job directory"})
		return
	}

	log.Printf("[fraud] starting fraud analysis for job %s at %s", req.JobID, jobDir)

	features := fraud.AnalyzeFraud(req.JobID, jobDir)

	// Write to disk for ML pipeline consumption
	if err := fraud.WriteFraudJSON(features, jobDir); err != nil {
		log.Printf("[fraud] warning: could not write fraud_features.json: %v", err)
	}

	c.JSON(http.StatusOK, features)
}

// isValidJobDir checks that the path exists and is a directory.
// Also guards against path traversal.
func isValidJobDir(dir string) bool {
	if dir == "" {
		return false
	}
	// Reject path traversal attempts
	cleaned := filepath.Clean(dir)
	if strings.Contains(cleaned, "..") {
		return false
	}
	info, err := os.Stat(cleaned)
	if err != nil {
		return false
	}
	return info.IsDir()
}
