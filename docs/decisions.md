# Decision Log (ADR)

Format: one entry per decision. Status is Accepted, Proposed, or Superseded. Add new entries at the bottom.

## ADR-001: Single repository, minimal infrastructure
- Status: Accepted (22 Oct 2026)
- Context: 14-day window, about 27 hours. Reviewers value measured results over architecture size.
- Decision: One repo. Local files and a numpy index. No vector DB server, Postgres, Kubernetes, frontend, or LLM API in v0.1.
- Consequences: Faster delivery and easier reproduction. Revisit only if a measured problem requires more.

## ADR-002: Article-level labels, chunk-independent evaluation
- Status: Accepted (22 Oct 2026)
- Context: Chunking is an experimental variable. Chunk-level labels would change with every chunking strategy and make the ablation unfair.
- Decision: Label (doc_id, article) with a grade. Map retrieved chunks to article units via the span table. Deduplicate by article, keep best rank.
- Consequences: Fair comparison across chunkers. Requires reliable article span detection (DI1). Supersedes "chunk or article" wording in FR-EVAL-1 and T-10: label articles only.

## ADR-003: Brute-force dense index with disk cache
- Status: Accepted (22 Oct 2026)
- Context: Expected corpus under 10k chunks.
- Decision: Numpy cosine search. Embeddings cached under `data/cache/`, keyed by model name and chunk file hash.
- Consequences: No index dependency, easy determinism. Revisit if p95 latency exceeds the target in T-27.

## ADR-004: Frozen test split
- Status: Accepted (22 Oct 2026)
- Context: Tuning on all 40 queries would inflate reported results.
- Decision: About 30 dev and about 10 test, stratified by query type, frozen at T-11 with tag `dataset-v1`. Tuning uses dev only. Label fixes after freezing require a version bump and a changelog line.
- Consequences: Smaller dev set, more honest reporting.

## ADR-005: PDF extractor
- Status: Accepted (22 Oct 2026)
- Context: T-04 planned a comparison of pdfplumber and PyMuPDF. PyMuPDF cannot be imported on the development machine: its native library is blocked by an application control policy ("DLL load failed while importing _mupdf", source: scratch/extraction_report.md). Only pdfplumber ran.
- Decision: pdfplumber.
- Consequences: No cross-extractor comparison was run, so T-04's "try 2 extractors" is not satisfied. For the two image-based documents (ADR-009) the result depends on the text layer already in the PDF. Revisit if another extractor can be run (for example on another machine or in CI).

## ADR-006: Embedding models
- Status: Proposed (decide in T-16 and T-17)
- Candidates: BGE-M3, multilingual-e5 (verify current Indonesian benchmarks before choosing).
- Decision: TBD. Record model name and revision hash.

## ADR-007: BM25 library and Indonesian preprocessing
- Status: Proposed (decide in T-13)
- Candidates: rank_bm25, bm25s. Basic tokenizer vs stopwords plus light stemming.
- Decision: TBD.

## ADR-008: Image contents (baked vs mounted model and index)
- Status: Proposed (decide in T-26)
- Criteria: Image size, cold-start latency, reproducibility.
- Decision: TBD.

## ADR-009: Topic
- Status: Accepted (22 Oct 2026)
- Context: T-01 feasibility check. Four official regulations were downloaded by hand into data/raw/ (not committed) and probed with pdfplumber.
- Decision: Personal data protection, widened to electronic systems and transactions. Core document: UU 27/2022. Documents probed: UU 27/2022, PP 71/2019, Permen Kominfo 20/2016, UU 11/2008.
- Text type: Permen Kominfo 20/2016 and UU 11/2008 are native text (embedded fonts, only small images). UU 27/2022 and PP 71/2019 are image-based pages (one full-page image per page) with a text layer in a single generic font; the text layer contains character errors, and whether it came from OCR software is not confirmed (source: scratch/extraction_report.md, image layer findings).
- Segmentation results from the spike (source: scratch/segmentation_v2_report.md, "Coverage before and after", after column; page counts from scratch/extraction_report.md). Not verified against page images:

| Document | Pages | Text type | Articles accepted | N | Missing 1..N | Repair-log entries |
|---|---|---|---|---|---|---|
| UU 27/2022 | 50 | image-based | 76 | 76 | none | 6 |
| PP 71/2019 | 90 | image-based | 104 | 104 | none | 15 |
| Permen Kominfo 20/2016 | 24 | native | 39 | 39 | none | 0 |
| UU 11/2008 | 38 | native | 54 | 54 | none | 0 |

- Consequences: Page-image verification (Tier 1) by Aldi: PENDING. Update before ticking T-01. The two native documents need no repairs; the two image-based ones depend on ADR-010. The requirements assumption of at least 10 text-extractable regulations is not yet tested beyond these four.

## ADR-010: OCR-tolerant article segmentation
- Status: Accepted (22 Oct 2026)
- Context: A strict "Pasal N on its own line" matcher left gaps in both image-based documents because headings are garbled in the text layer (for example "Pasal 6O", "Pasal T2", "Pasa722", or the number on the line before the word "Pasal"), and page stamps and bottom-of-page catchwords sit inside the text (source: scratch/extraction_report.md, "Missing article diagnosis").
- Decision: Segment articles with a sequence-constrained marker decoder. The spike code lives in scratch/ (not committed) and is to be re-implemented under src/indoreg/ingest/ in T-06 and T-07.
  1. Noise filter removes only SK stamp lines, page-bottom catchwords (lines ending in ". ." or ". . ."), and header or footer lines repeated on more than half of the pages (first 6 and last 3 lines of a page).
  2. Candidates: fuzzy "Pasal" (edit distance up to 2) followed by a number token. Confusable characters O to 0, l and I to 1, T to 7, S to 5, B to 8 are allowed in the number, as are an inner space, a leading period, a number on the previous or next line, and a confusable character inside the word itself (glued form such as "Pasa722").
  3. Decoding: clean-digit headings are anchors (longest increasing subsequence, later occurrence wins ties). A confusable reading is accepted only when it equals the expected next number or suffix. gap_fill accepts a single unclaimed heading-like candidate between neighbours N-1 and N+1.
  4. Coverage gate per document: N, missing numbers, duplicates, unresolved candidates.
- Unresolved markers stay unresolved and are never guessed.
- Methods are labeled confusion, catchword_swap (the swap rule; called reversed_swap in the spike report), tiebreak_later and gap_fill, and logged per document. Counts from scratch/segmentation_v2_report.md: PP 71/2019 confusion 12, catchword_swap 1, tiebreak_later 2, gap_fill 0; UU 27/2022 confusion 5, tiebreak_later 1, gap_fill 0; Permen Kominfo 20/2016 and UU 11/2008 no entries.
- Consequences: The rules were developed on the same 4 files, so the coverage numbers are in-sample. Out-of-sample coverage must be measured on documents added later. text_quality (native or ocr) is recorded per document in the manifest; design.md 3.1 and FR-ING-2 do not list that field yet, so add it when T-03 builds the manifest. Segmentation correctness is not verified against page images (see ADR-009).

## ADR-011: Pasal.id API as metadata source only
- Status: Accepted (22 Oct 2026)
- Context: Pasal.id has a token-gated REST API. A probe on 22 Oct 2026 (6 requests, source: scratch/feasibility_report.md) returned metadata (title, number, year, status, verification tier, source_url) and `"content": "not_available_via_api"` for search and for the law detail; the detail had no article nodes. The response note says the text is available on the website or through MCP.
- Decision: Use the API at most to cross-check status and source_url when filling the manifest (T-03). Article text comes from the official PDFs. No scraping of pasal.id pages and no MCP.
- Consequences: Each manifest status still needs its own source note (FR-ING-2). No terms or license field appeared in the API responses; terms were not verified.

## ADR-012: Penjelasan excluded from v0.1
- Status: Accepted (22 Oct 2026)
- Context: UU 11/2008, PP 71/2019 and UU 27/2022 contain a Penjelasan section after the body that repeats article numbers (mostly "Cukup jelas."). Its heading is on page 26, 58 and 35 respectively; Permen Kominfo 20/2016 has none (source: scratch/extraction_report.md).
- Decision: Index and label body articles only. The body ends at the Penjelasan boundary found by OCR-tolerant signals (heading garbled up to a few characters, "PASAL DEMI PASAL", numbering restart).
- Consequences: Explanatory text is not searchable and queries answered only by a Penjelasan cannot be satisfied. State this in the README limitations. Revisit if error analysis shows many such misses.

---

## Template

```
## ADR-XXX: Title
- Status:
- Context:
- Decision:
- Consequences:
```
