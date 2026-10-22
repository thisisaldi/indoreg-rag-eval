# IndoReg-RAG Eval: Tasks

Conventions
- Each task links to requirements (BR, FR, NFR in requirements.md) and the day in timeline.md.
- A task is done only when its acceptance criteria pass and the artifact is committed.
- Estimates are in hours. Total about 27h.

Repo layout target

```
indoreg-rag-eval/
  src/indoreg/        ingestion, chunking, retrievers, eval, api, config, logging
  eval/               dataset.jsonl, labeling guideline
  configs/            default.yaml, eval.yaml
  data/               manifest.json, raw/ (gitignored if license requires), processed/
  tests/              unit tests, deterministic fixtures
  reports/            results/, error_analysis.md, case_study.md, architecture diagram
  docs/               requirements.md, timeline.md, tasks.md
  pyproject.toml, Dockerfile, README.md
  .github/workflows/  ci.yml
```

---

## M1 Foundation (Day 1 to 3)

### [ ] T-01 Feasibility check (Day 1, 0.75h)
Links: Assumptions, Risks
- [x] Find 3 to 5 candidate regulations for personal data protection on official sources (4 found and probed, see ADR-009)
- [ ] Download manually, check that text is selectable and copy-paste preserves Pasal structure (text extracts on all 4; Pasal structure recovery pending Aldi's page-image check)
- [x] Note any scanned pages, broken numbering, annex-heavy files (image-based pages with garbled headings in PP 71/2019 and UU 27/2022, see ADR-009 and ADR-010; no annexes found)
- Acceptance: at least 3 documents with clean extractable article structure, or a decision to switch topic recorded in `docs/decisions.md`
- Output: feasibility notes (5 lines per document)

### [ ] T-02 Repository and spec docs (Day 1, 0.75h)
Links: BR5, NFR4, NFR9
- [ ] Create public repo `indoreg-rag-eval`
- [ ] Add requirements.md, timeline.md, tasks.md under `docs/`
- [ ] README stub with problem statement and the "not legal advice" note
- [ ] `.gitignore`, license, pre-commit with ruff and a secret scanner
- Acceptance: repo is public, docs committed, pre-commit runs
- Output: initial commit

### [ ] T-03 Source collection and manifest (Day 2, 1h)
Links: BR2, FR-ING-2
- [ ] Collect 10 to 15 official regulations (UU PDP, PP, Permen, related)
- [ ] Check source terms before any automated download, otherwise manual
- [ ] Build `data/manifest.json` with ID, title, number, year, status, URL, retrieved date, filename, SHA-256
- [ ] Mark status (in force, amended, revoked, unknown) with a source for each claim
- Acceptance: every manifest entry has all fields, hashes match files
- Output: `data/manifest.json`

### [ ] T-04 Extraction spike (Day 2, 0.5h)
Links: FR-ING-1, FR-ING-3
- [ ] Try 2 extractors (for example pdfplumber and PyMuPDF) on 2 documents
- [ ] Compare article marker preservation, header and footer noise, table handling
- [ ] Pick one, record why in `docs/decisions.md`
- Acceptance: chosen extractor recovers Pasal boundaries on both test documents
- Output: decision note

### [x] T-05 Project scaffold (Day 3, 0.5h)
Links: NFR1, NFR2, NFR3, NFR4
- [x] `pyproject.toml` with pinned deps and lockfile (`uv.lock`, Python 3.12 pinned)
- [x] Config module (pydantic settings, YAML plus env), no hardcoded paths
- [x] Logging module (JSON logs)
- [x] mypy or pyright config, pytest config (mypy strict on `src/`)
- Acceptance: `pip install -e .` works in a clean env, `pytest` runs (even if empty)

### [x] T-06 Ingestion pipeline (Day 3, 1h)
Links: FR-ING-1 to FR-ING-4
- [x] Read manifest, extract text per page, normalize whitespace and header and footer noise
- [x] Log extraction failures with document ID and page, continue on error
- [x] Write processed text to `data/processed/` deterministically (byte-identical on rerun; also writes `<doc_id>.articles.json` spans, ADR-010)
- [x] Tests on a small fixture PDF or text sample (synthetic OCR-like page text)
- Acceptance: two runs produce identical output hashes, failures appear in the log not as crashes

### [ ] T-07 Chunkers (Day 3, 1h)
Links: FR-CHK-1 to FR-CHK-3
- [ ] Article-based chunker on Pasal markers, keep chapter (BAB) context (chunker done; BAB context not yet, `chapter` is null)
- [ ] Fixed-size overlapping chunker, size and overlap from config
- [x] Chunk schema: document ID, chunk ID, article number, offsets, source URL, text
- [ ] Tests for edge cases: missing markers, very long articles, ayat sub-items
- Acceptance: every chunk links back to its document and offsets reconstruct the source text span

### [ ] T-08 CI skeleton (Day 3, 0.5h)
Links: BR7, NFR5, NFR6
- [x] GitHub Actions: install, ruff, type check, pytest (`.github/workflows/ci.yml`)
- [x] Cache pip (uv cache via setup-uv, since the project uses uv)
- Not yet verified: CI has not run on GitHub; tick T-08 after the first green run on main.
- Acceptance: CI green on main, badge in README

---

## M2 Dataset (Day 4 to 5)

### [x] T-09 Labeling guideline (Day 4, 0.5h)
Links: FR-EVAL-1, FR-EVAL-2
- [x] Define relevance: which article counts as relevant, how to handle multi-article answers and graded relevance
- [x] Define the four query types with 2 examples each
- [x] Rule: at most 1 in 4 queries may be a near copy of passage text
- Acceptance: guideline in `eval/LABELING.md`, written before labeling starts
- Status: approved by Aldi on 22 Oct 2026, before any labeling.

### [ ] T-10 Label queries 1 to 20 (Day 4, 2.5h)
Links: FR-EVAL-1, FR-EVAL-2
- [ ] Write realistic Indonesian queries from the persona's point of view
- [ ] Label relevant articles (doc ID, article, grade), with the source passage reference
- [ ] Include type tag per query
- Acceptance: 20 queries in JSONL, each label verified against the source PDF by Aldi (LLM-drafted candidates allowed, ADR-014)

### [ ] T-11 Label to 40 and freeze split (Day 5, 1h)
Links: FR-EVAL-1 to FR-EVAL-3
- [ ] Add queries 21 to 40, hit the type mix
- [ ] Assign about 30 dev and about 10 test, stratified by type
- [ ] Freeze the test split: commit, tag `dataset-v1`, do not tune on it
- Acceptance: schema validation script passes, type mix within 5 points of target

### [ ] T-12 Metrics module (Day 5, 0.5h)
Links: FR-EVAL-4
- [ ] Recall@k, MRR, nDCG@10 with graded relevance support
- [ ] Unit tests with hand-computed examples
- Acceptance: tests pass, edge cases covered (no relevant docs, ties, k larger than results)

---

## M3 Baselines (Day 6 to 8)

### [ ] T-13 BM25 baseline (Day 6, 0.75h)
Links: FR-RET-1, FR-RET-6, BR3
- [x] Shared `Retriever` interface (typed)
- [x] BM25 with basic tokenizer (stdlib, no library; ADR-007 still open)
- [ ] Indonesian-aware variant (stopwords, light stemming) if time permits
- Acceptance: BM25 runs on both chunk strategies with identical query set

### [ ] T-14 Eval runner CLI (Day 6, 0.5h)
Links: FR-EVAL-6 to FR-EVAL-8, BR5
- [ ] One command runs configured retrievers on dev and test splits
- [ ] Writes JSON results with config, git SHA, timestamp, latency per query
- [ ] Writes a markdown comparison table
- Acceptance: one command reproduces baseline numbers, output JSON is stable across reruns

### [ ] T-15 CI deterministic eval (Day 6, 0.25h)
Links: BR7, NFR6
- [ ] Small fixture corpus and 5 to 10 query fixture
- [ ] CI runs eval on the fixture and fails if metrics drop below a recorded floor
- Acceptance: a deliberate bug in BM25 makes CI fail

### [ ] T-16 Dense retrieval, model 1 (Day 7, 1.5h)
Links: FR-RET-2, BR3
- [ ] Sentence Transformers retriever, embeddings cached by model name and chunk hash
- [ ] Run on both chunkers, same queries
- [ ] Record embedding time and index size
- Acceptance: first BM25 vs dense table committed

### [ ] T-17 Dense model 2 (and 3 if time) (Day 8, 0.75h)
Links: FR-RET-3
- [ ] Verify current Indonesian embedding benchmarks before choosing
- [ ] Add model via config only, no code change
- Acceptance: model comparison table with latency per model

### [ ] T-18 Hybrid retrieval with RRF (Day 8, 0.75h)
Links: FR-RET-4
- [ ] Reciprocal rank fusion over BM25 and best dense model
- [ ] Tune the single constant on dev only
- Acceptance: hybrid evaluated on dev and test, tuning decisions logged

---

## M4 Analysis (Day 9 to 10)

### [ ] T-19 Bootstrap CIs and win/loss (Day 9, 0.75h)
Links: BR4, FR-EVAL-5
- [ ] Bootstrap 95% CIs for every metric, seeded
- [ ] Per-query win/loss/tie between any two configs
- [ ] Add to the results tables
- Acceptance: every comparison table shows CIs, seed fixed, tests cover the bootstrap function

### [ ] T-20 Chunking ablation (Day 9, 0.75h)
Links: BR3
- [ ] Article-based vs fixed-size, same retriever, same queries
- [ ] Optional extras (overlap sizes) only if ahead
- Acceptance: controlled comparison with CIs and a one-paragraph interpretation

### [ ] T-21 Error analysis (Day 10, 1.5h)
Links: Definition of done
- [ ] List the worst-performing queries for the best config
- [ ] Document at least 5 failures (target 10), each with query, expected, retrieved, and cause tag
- [ ] Cause tags: extraction error, vocabulary gap, chunk boundary, multi-article answer, superseded regulation, label error
- [ ] Fix label errors found (and re-freeze with a version bump, noted in changelog)
- Acceptance: `reports/error_analysis.md` committed

### [ ] T-22 Reranker (stretch) (Day 10, 1h)
Links: FR-RET-5
- [ ] Cross-encoder reranking of top-k, measure gain and latency cost
- Acceptance: results added to the comparison table, or task explicitly skipped and logged

### [ ] T-23 Tag benchmark release (Day 10, 0.5h)
- [ ] Verify clean-clone reproduction of the benchmark table
- [ ] Tag `v0.1-benchmark`
- Acceptance: fresh environment reproduces the committed results within the stated tolerance

---

## M5 Service (Day 11 to 12)

### [ ] T-24 FastAPI service (Day 11, 1.75h)
Links: BR6, FR-API-1 to FR-API-6
- [ ] `POST /search`, `GET /health`
- [ ] Pydantic request and response models, top_k bounds, query length limit
- [ ] Response includes document status and disclaimer
- [ ] Tests: valid request, empty query, over-length, bad top_k, response schema
- Acceptance: all API tests pass, OpenAPI docs render

### [ ] T-25 Structured logging and config validation (Day 11, 1.25h)
Links: NFR2, NFR3
- [ ] Request ID middleware, JSON logs for requests and retrieval timing
- [ ] Fail fast on invalid config at startup
- Acceptance: a log line per request with request ID and latency, bad config exits with a clear error

### [ ] T-26 Dockerfile (Day 12, 0.5h)
Links: BR6
- [ ] Multi-stage or slim image, non-root user, models and index baked in or mounted (decide and document)
- Acceptance: `docker run` serves `/search` locally

### [ ] T-27 Latency benchmark (Day 12, 0.5h)
Links: NFR7, FR-EVAL-8
- [ ] p50 and p95 per configuration, warm and cold start
- [ ] Cost note: cash cost vs estimated compute
- Acceptance: latency table in reports, method described

### [ ] T-28 CI builds image (Day 12, 0.5h)
Links: BR7
- [ ] CI builds the Docker image and runs a smoke test against `/health`
- Acceptance: CI green with the image step

---

## M6 Packaging (Day 13 to 14)

### [ ] T-29 README (Day 13, 0.5h)
Links: BR5, BR8
- [ ] Problem, results table (copied from result files), quickstart, API example, limitations, legal disclaimer
- Acceptance: a stranger can reproduce the benchmark from the README alone

### [ ] T-30 Architecture diagram (Day 13, 0.25h)
- [ ] Ingestion to chunking to indexes to retrievers to eval and API
- Acceptance: diagram in `reports/` and embedded in README

### [ ] T-31 Case study (Day 13, 0.75h)
- [ ] Problem, approach, results with CIs, failure analysis, tradeoffs, what I did not build and why, lessons
- Acceptance: every number traces to a committed result file, no invented claims

### [ ] T-32 Demo (Day 14, 0.5h)
- [ ] 2 minute screen recording or screenshot walkthrough with curl examples
- Acceptance: link in README

### [ ] T-33 Resume bullets and talking points (Day 14, 0.25h)
- [ ] 3 to 5 resume bullets with measured numbers
- [ ] 3 interview talking points (one on a decision, one on a failure, one on a tradeoff)

### [ ] T-34 Confidentiality audit and next-project brief (Day 14, 0.75h)
- [ ] Search repo, history, and docs for any [employer], [internal system], internal names, credentials, or proprietary logic
- [ ] Confirm all data is public and sources are cited
- [ ] Write a one-page brief for the next project (generation layer with faithfulness evals, or a retrieval bias and safety audit)
- Acceptance: audit checklist signed off, brief committed

---

## Progress log

| Date | Done | Blockers | Next |
|---|---|---|---|
| 22 Oct 2026 | T-01 probes: pdfplumber extraction and OCR-tolerant segmentation spike on 4 PDFs, Pasal.id API probe. ADR-005, ADR-009 to ADR-012 recorded. Spec conflict on label granularity fixed (FR-EVAL-1, T-09, T-10). T-02 partly done: .gitignore, pre-commit config, README. | PyMuPDF blocked by application control (no extractor comparison). Page-image check pending (Aldi). License choice and public repo pending (Aldi). | Aldi's page-image check, then tick T-01. T-03 source manifest. |
| 22 Oct 2026 | T-03 partly: data/manifest.json for 4 documents (hashes, titles, text_quality), scripts/check_manifest.py, ADR-013. T-05 done: uv project on Python 3.12, config (YAML + INDOREG_ env) and JSON logging modules, 13 tests, mypy strict and ruff clean, `pip install -e .` verified in a clean venv. | T-03: 13 manifest fields need source URLs, status and retrieval dates from Aldi. | T-06 ingestion pipeline after T-03 fields are filled. |
| 22 Oct 2026 | T-08 workflow written (not yet run on GitHub). T-06 done: pdfplumber extraction, noise filter and OCR-tolerant segmentation ported from the spike, 273 articles from 4 documents with offsets identical to the spike, deterministic outputs. T-07 article chunker and T-13 basic BM25 done; `make search` CLI for a first end-to-end demo. | T-01 page-image check and T-03 manifest fields still open; 3 documents show "not yet recorded" for status and source. | T-07 fixed-size chunker and BAB context; labeling (T-09 to T-11). |
