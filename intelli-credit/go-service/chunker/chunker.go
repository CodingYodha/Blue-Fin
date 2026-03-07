// Package chunker splits parsed PDF text into overlapping, paragraph-aware
// chunks and writes the chunks.json file that the RAG pipeline consumes.
//
// Chunking strategy (matching architecture spec):
//   - Target chunk size: 512–800 words
//   - Overlap: 50–100 words (prevents splitting a figure from its header)
//   - Split on paragraph boundaries — never mid-sentence
//   - Bank statements: do NOT chunk (they go to fraud math only)
package chunker

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"intelli-credit/go-service/parser"
)

// Chunk is a single chunk written to chunks.json.
// Schema matches the GoChunk Pydantic model in ai-service/rag/schemas.py.
type Chunk struct {
	ChunkText   string `json:"chunk_text"`
	PageNum     int    `json:"page_num"`
	SectionName string `json:"section_name"`
	ChunkIndex  int    `json:"chunk_index"`
	DocType     string `json:"doc_type"`
	SourceFile  string `json:"source_file"`
}

// Tuning constants
const (
	targetMinWords = 512
	targetMaxWords = 800
	overlapWords   = 75 // midpoint of 50-100 range
)

// ChunkDocument takes parsed pages for a single PDF, produces Chunk slices.
// Bank statements are skipped entirely (they go to fraud math only).
func ChunkDocument(pages []parser.PageResult, docType, sourceFile string) []Chunk {
	if docType == parser.DocBankStmt {
		// Bank statements: do NOT chunk — they go to fraud math only
		log.Printf("[chunker] skipping bank_statement %s — goes to fraud math only", sourceFile)
		return nil
	}

	// Group pages into section runs. A "section run" is a contiguous set of
	// pages that share the same detected section name (or "").
	type sectionRun struct {
		sectionName string
		pages       []parser.PageResult
	}

	var runs []sectionRun
	for _, page := range pages {
		if page.PageType == parser.PageBlank {
			continue
		}

		section := parser.DetectSection(page.Text)
		// Merge with previous run if same section (or both empty)
		if len(runs) > 0 && runs[len(runs)-1].sectionName == section {
			runs[len(runs)-1].pages = append(runs[len(runs)-1].pages, page)
		} else {
			runs = append(runs, sectionRun{
				sectionName: section,
				pages:       []parser.PageResult{page},
			})
		}
	}

	var chunks []Chunk
	globalIndex := 0

	for _, run := range runs {
		// Combine all text in this section run
		var fullText strings.Builder
		firstPage := run.pages[0].PageNum
		for _, p := range run.pages {
			fullText.WriteString(p.Text)
			fullText.WriteString("\n\n")
		}

		// Split on paragraphs (double newline)
		paragraphs := splitParagraphs(fullText.String())
		if len(paragraphs) == 0 {
			continue
		}

		// Build chunks from paragraphs respecting word limits
		sectionChunks := buildChunks(paragraphs, firstPage, run.sectionName, docType, sourceFile, &globalIndex)
		chunks = append(chunks, sectionChunks...)
	}

	return chunks
}

// splitParagraphs splits text on double-newlines and trims whitespace.
func splitParagraphs(text string) []string {
	raw := strings.Split(text, "\n\n")
	var result []string
	for _, p := range raw {
		trimmed := strings.TrimSpace(p)
		if len(trimmed) > 0 {
			result = append(result, trimmed)
		}
	}
	return result
}

// wordCount returns the number of whitespace-separated tokens.
func wordCount(s string) int {
	return len(strings.Fields(s))
}

// buildChunks assembles paragraphs into chunks respecting target word size
// and overlap. Never splits mid-sentence.
func buildChunks(paragraphs []string, startPage int, sectionName, docType, sourceFile string, globalIndex *int) []Chunk {
	var chunks []Chunk
	var current []string
	currentWords := 0

	flush := func() {
		if len(current) == 0 {
			return
		}
		text := strings.Join(current, "\n\n")
		chunks = append(chunks, Chunk{
			ChunkText:   text,
			PageNum:     startPage,
			SectionName: sectionName,
			ChunkIndex:  *globalIndex,
			DocType:     docType,
			SourceFile:  sourceFile,
		})
		*globalIndex++

		// Keep last N words as overlap for the next chunk
		words := strings.Fields(text)
		if len(words) > overlapWords {
			overlapText := strings.Join(words[len(words)-overlapWords:], " ")
			current = []string{overlapText}
			currentWords = overlapWords
		} else {
			current = nil
			currentWords = 0
		}
	}

	for _, para := range paragraphs {
		paraWords := wordCount(para)

		// If adding this paragraph exceeds max, flush first
		if currentWords+paraWords > targetMaxWords && currentWords >= targetMinWords {
			flush()
		}

		current = append(current, para)
		currentWords += paraWords

		// If we've reached max, flush
		if currentWords >= targetMaxWords {
			flush()
		}
	}

	// Flush remaining
	if len(current) > 0 {
		text := strings.Join(current, "\n\n")
		// Only create a chunk if there's meaningful content
		if wordCount(text) > 10 {
			chunks = append(chunks, Chunk{
				ChunkText:   text,
				PageNum:     startPage,
				SectionName: sectionName,
				ChunkIndex:  *globalIndex,
				DocType:     docType,
				SourceFile:  sourceFile,
			})
			*globalIndex++
		}
	}

	return chunks
}

// WriteChunksJSON writes the combined chunks from all documents to chunks.json.
func WriteChunksJSON(chunks []Chunk, jobDir string) error {
	outPath := filepath.Join(jobDir, "chunks.json")

	data, err := json.MarshalIndent(chunks, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal chunks: %w", err)
	}

	if err := os.WriteFile(outPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write chunks.json: %w", err)
	}

	log.Printf("[chunker] wrote %d chunks to %s", len(chunks), outPath)
	return nil
}
