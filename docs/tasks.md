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

### [x] T-01 Feasibility check (Day 1, 0.75h)
Links: Assumptions, Risks
- [x] Find 3 to 5 candidate regulations for personal data protection on official sources (4 found and probed, see ADR-009)
- [x] Download manually, check that text is selectable and copy-paste preserves Pasal structure (text extracts on all 4; Pasal structure recovered by the OCR-tolerant segmentation, ADR-010; Aldi's full page-image check skipped by Aldi on 23 Oct 2026, see ADR-009)
- [x] Note any scanned pages, broken numbering, annex-heavy files (image-based pages with garbled headings in PP 71/2019 and UU 27/2022, see ADR-009 and ADR-010; no annexes found)
- Acceptance: at least 3 documents with clean extractable article structure, or a decision to switch topic recorded in `docs/decisions.md`
- Output: feasibility notes: ADR-009 table and `scratch/` reports (local, not committed)

### [x] T-02 Repository and spec docs (Day 1, 0.75h)
Links: BR5, NFR4, NFR9
- [x] Create public repo `indoreg-rag-eval`
- [x] Add requirements.md, timeline.md, tasks.md under `docs/` (plus design.md and decisions.md)
- [x] README stub with problem statement and the "not legal advice" note
- [x] `.gitignore`, license (MIT), pre-commit with ruff and a secret scanner (gitleaks)
- Acceptance: repo is public, docs committed, pre-commit runs (public confirmed 23 Oct 2026 via the GitHub API: visibility public, license MIT, default branch main)
- Output: initial commit

### [x] T-03 Source collection and manifest (Day 2, 1h)
Links: BR2, FR-ING-2
- [x] Collect 10 to 15 official regulations (UU PDP, PP, Permen, related) (4 by decision, ADR-013)
- [x] Check source terms before any automated download, otherwise manual (all 4 downloaded manually by Aldi)
- [x] Build `data/manifest.json` with ID, title, number, year, status, URL, retrieved date, filename, SHA-256
- [x] Mark status (in force, amended, revoked, unknown) with a source for each claim
- Acceptance: every manifest entry has all fields, hashes match files
- Status 23 Oct 2026: done. All 4 entries complete (`scripts/check_manifest.py --strict` passes): PDFs retrieved by Aldi 2026-10-22 from peraturan.bpk.go.id; statuses read from the BPK detail pages (UU 27/2022 and Permen 20/2016 in_force; PP 71/2019 in_force per Aldi; UU 11/2008 `amended`: BPK lists UU 19/2016 and UU 1/2024 as amendments and a partial revocation by UU 1/2023 (KUHP); the corpus text is the original 2008 text). BPK shows no amendment data ("Belum Tersedia") for UU 27/2022 and the Permen, which is not proof there are none.
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

### [x] T-07 Chunkers (Day 3, 1h)
Links: FR-CHK-1 to FR-CHK-3
- [x] Article-based chunker on Pasal markers, keep chapter (BAB) context (OCR-tolerant BAB detection; chapter sequences are contiguous in all 4 documents)
- [x] Fixed-size overlapping chunker, size and overlap from config (1200/200 chars over the body only; 188 chunks; each lists every overlapped article)
- [x] Chunk schema: document ID, chunk ID, article number, offsets, source URL, text
- [x] Tests for edge cases: missing markers, very long articles, ayat sub-items (`tests/test_chunking.py`, `tests/test_articles.py`)
- Also fixed: the noise filter dropped all header/footer-zone lines of a 1-page text; a running header now has to repeat on at least 2 pages (no change on the 4 real documents).
- Acceptance: every chunk links back to its document and offsets reconstruct the source text span

### [x] T-08 CI skeleton (Day 3, 0.5h)
Links: BR7, NFR5, NFR6
- [x] GitHub Actions: install, ruff, type check, pytest (`.github/workflows/ci.yml`)
- [x] Cache pip (uv cache via setup-uv, since the project uses uv)
- Acceptance: CI green on main (Aldi confirmed green on 23 Oct 2026), badge in README

---

## M2 Dataset (Day 4 to 5)

### [x] T-09 Labeling guideline (Day 4, 0.5h)
Links: FR-EVAL-1, FR-EVAL-2
- [x] Define relevance: which article counts as relevant, how to handle multi-article answers and graded relevance
- [x] Define the four query types with 2 examples each
- [x] Rule: at most 1 in 4 queries may be a near copy of passage text
- Acceptance: guideline in `eval/LABELING.md`, written before labeling starts
- Status: approved by Aldi on 22 Oct 2026, before any labeling.

### [x] T-10 Label queries 1 to 20 (Day 4, 2.5h)
Links: FR-EVAL-1, FR-EVAL-2
- [x] Write realistic Indonesian queries from the persona's point of view
- [x] Label relevant articles (doc ID, article, grade), with the source passage reference
- [x] Include type tag per query
- Acceptance: 20 queries in JSONL, each label verified against the source PDF (LLM-drafted candidates allowed, ADR-014)
- Status: done under ADR-015 at Aldi's request: labels drafted and checked by Claude against the PDF page images (scanned documents) and embedded text (native documents), not human-verified. Check record: `eval/drafts/CHECK_NOTES.md`.

### [x] T-11 Label to 40 and freeze split (Day 5, 1h)
Links: FR-EVAL-1 to FR-EVAL-3
- [x] Add queries 21 to 40, hit the type mix (10/16/10/4 = 25/40/25/10%, exactly on target)
- [x] Assign about 30 dev and about 10 test, stratified by type (seed 42; 25% per type rounded down, leftover slot by largest remainder, ties alphabetical: 3/4/2/1 test)
- [x] Freeze the test split: commit, tag `dataset-v1`, do not tune on it
- Acceptance: schema validation script passes, type mix within 5 points of target (`indoreg.eval.dataset.load_dataset` validates all 40 queries, 75 labels)

### [x] T-12 Metrics module (Day 5, 0.5h)
Links: FR-EVAL-4
- [x] Recall@k, MRR, nDCG@10 with graded relevance support (`src/indoreg/eval/metrics.py`; per-query reciprocal rank, averaged into MRR by the runner)
- [x] Unit tests with hand-computed examples (no relevant units raise an error; duplicate units count once at their best rank)
- Acceptance: tests pass, edge cases covered (no relevant docs, ties, k larger than results)

---

## M3 Baselines (Day 6 to 8)

### [x] T-13 BM25 baseline (Day 6, 0.75h)
Links: FR-RET-1, FR-RET-6, BR3
- [x] Shared `Retriever` interface (typed)
- [x] BM25 with basic tokenizer (stdlib, no library; ADR-007)
- [x] Indonesian-aware variant (stopwords, light stemming) if time permits (`bm25-id`: stopwords plus -nya/-kah stripping; also `bm25-id-title`, which indexes the law's title)
- Verified: all three variants run on both chunk strategies with the same 40 queries. Committed numbers with CIs come with T-19.
- Acceptance: BM25 runs on both chunk strategies with identical query set

### [x] T-14 Eval runner CLI (Day 6, 0.5h)
Links: FR-EVAL-6 to FR-EVAL-8, BR5
- [x] One command runs configured retrievers on dev and test splits (`make eval`)
- [x] Writes JSON results with config, git SHA, timestamp, latency per query
- [x] Writes a markdown comparison table
- Acceptance: one command reproduces baseline numbers, output JSON is stable across reruns
- Status: done. First baseline on dataset-v1: `reports/results/20261022T105714Z-05b2e36.json` (clean commit; same metrics as an earlier run, only latency differs). Labels are LLM-checked, not human-verified (ADR-015); the table says so. `make eval-drafts` still runs on the drafts (marked UNVERIFIED, gitignored).
- Finding from the draft run (not a result): chunk text carries no document title, so queries naming the law ("UU 27 Tahun 2022") cannot match it. Candidate experiment: index the title with the article text, measured on dev only.

### [x] T-15 CI deterministic eval (Day 6, 0.25h)
Links: BR7, NFR6
- [x] Small fixture corpus and 5 to 10 query fixture (`tests/fixtures/ci_eval/`: 2 fictional regulations, 12 articles, 8 queries; no real legal text)
- [x] CI runs eval on the fixture and fails if metrics drop below a recorded floor (`tests/test_ci_eval.py`, floor in `floor.json`, runs with pytest in CI)
- Acceptance: a deliberate bug in BM25 makes CI fail (verified 23 Oct 2026: reversing the BM25 sort order dropped dev recall@1 from 0.90 to 0.00 and the test failed; reverted)

### [x] T-16 Dense retrieval, model 1 (Day 7, 1.5h)
Links: FR-RET-2, BR3
- [x] Dense retriever (onnxruntime, ADR-016; `retrieval/dense.py`), embeddings cached by model identity plus chunk ids and texts
- [x] Run on both chunkers, same queries (`dense-e5-small`, ADR-006)
- [x] Record embedding time and index size (in the result JSON and table)
- Acceptance: first BM25 vs dense table committed: `reports/results/20261023T072143Z-28cc2a8.md`
- Dev reading (test not used for choices): `dense-e5-small/article` vs `bm25-basic/article` shows no established difference on any metric (all CIs include 0; nDCG@10 -0.012 [-0.12, +0.10], 9/9/12). Fixed chunks lose to article chunks for dense too (MRR -0.223 [-0.31, -0.14]). A cached rerun reproduced every per-query metric. Labels are LLM-checked, not human-verified (ADR-015).

### [x] T-17 Dense model 2 (and 3 if time) (Day 8, 0.75h)
Links: FR-RET-3
- [x] Verify current Indonesian embedding benchmarks before choosing (ADR-006)
- [x] Add model via config only, no code change (`dense-e5-base`; the runner also gained `eval.pairs` for a direct paired model comparison, which is an eval feature, not a model change)
- Acceptance: model comparison table with latency per model: `reports/results/20261023T073208Z-cfff220.md` (rows, latency, index size, cold embedding time, and the paired `dense-e5-base/article vs dense-e5-small/article` table)
- Dev reading: no established difference between the two models or between either model and `bm25-basic/article` (all CIs include 0). e5-small is the hybrid member (ADR-006). Model 3 skipped: BGE-M3 does not fit this machine's memory (ADR-016).

### [x] T-18 Hybrid retrieval with RRF (Day 8, 0.75h)
Links: FR-RET-4
- [x] Reciprocal rank fusion over BM25 and best dense model (`retrieval/hybrid.py`; members `bm25-id-title`, the BM25 variant with the best dev nDCG@10, and `dense-e5-small`, ADR-006)
- [x] Tune the single constant on dev only (grid `rrf_k` 10/30/60 x `depth` 20/50 with `configs/tune-hybrid.yaml`, which runs the dev split only: `reports/results/20261023T073543Z-a07f39f`)
- Tuning log: against the design default k 60 / depth 50, no grid point differs on dev nDCG@10 with a CI excluding 0 (largest: k10-d20 +0.009 [-0.03, +0.05]; k30-d20 -0.013 [-0.04, +0.00]). Default kept; the test split was not read during tuning.
- Acceptance: hybrid evaluated on dev and test, tuning decisions logged: `reports/results/20261023T073624Z-a0d608d.md`
- Dev reading: `hybrid/article` beats `bm25-basic/article` on recall@10 (+0.102 [+0.01, +0.20]), MRR (+0.124 [+0.02, +0.25]) and nDCG@10 (+0.103 [+0.02, +0.20], 13/7/10), and beats `dense-e5-small/article` on recall@10, MRR and nDCG@10 (+0.114 [+0.02, +0.21]). Against its BM25 member `bm25-id-title/article` the gain is not established (nDCG@10 +0.065 [-0.01, +0.14], 15/4/11). Hybrid p50 latency on dev is 12.09 ms vs 0.50 ms for bm25-id-title. Labels are LLM-checked, not human-verified (ADR-015).
- Open for Aldi (serving choice, ADR-016): ADR-016 serves BM25 unless hybrid beats BM25 with a CI excluding 0. Hybrid clears that bar against the baseline `bm25-basic` but not against the best BM25 variant `bm25-id-title`. Decide which comparison counts before T-24/T-35; `search.retriever` is unchanged (`bm25-basic`).

---

## M4 Analysis (Day 9 to 10)

### [x] T-19 Bootstrap CIs and win/loss (Day 9, 0.75h)
Links: BR4, FR-EVAL-5
- [x] Bootstrap 95% CIs for every metric, seeded (1000 resamples of queries, seed 42, from config)
- [x] Per-query win/loss/tie between any two configs (paired against `eval.baseline`, with a CI on the difference)
- [x] Add to the results tables (`reports/results/20261023T025613Z-a20cbfe.md`: 3 BM25 variants x 2 chunk strategies)
- Dev reading of that file (test split not used for choices): `bm25-id/article` improves Recall@10 over `bm25-basic/article` (+0.065, CI +0.01 to +0.14, 6/1/23); `bm25-id-title/article` gains on MRR and nDCG@10 are not established (CIs include 0); fixed chunks lose to article chunks on MRR and nDCG@10 for all three variants (CIs exclude 0). Labels are LLM-checked, not human-verified (ADR-015).
- Acceptance: every comparison table shows CIs, seed fixed, tests cover the bootstrap function

### [x] T-20 Chunking ablation (Day 9, 0.75h)
Links: BR3
- [x] Article-based vs fixed-size, same retriever, same queries (the runner now pairs each retriever's fixed run with its own article run; `reports/chunking_ablation.md`, from `reports/results/20261023T065417Z-0cb8d5c`)
- [ ] Optional extras (overlap sizes) only if ahead (skipped: not ahead; an overlap sweep would be tuning, dev only)
- Acceptance: controlled comparison with CIs and a one-paragraph interpretation

### [x] T-21 Error analysis (Day 10, 1.5h)
Links: Definition of done
- [x] List the worst-performing queries for the best config (`scripts/worst_queries.py`; output `reports/results/20261023T073624Z-a0d608d.worst-dev.txt`; dev only, see the report for why)
- [x] Document at least 5 failures (target 10), each with query, expected, retrieved, and cause tag (10 in `reports/error_analysis.md`)
- [x] Cause tags: extraction error, vocabulary gap, chunk boundary, multi-article answer, superseded regulation, label error (plus "other" for fusion and number collision)
- [ ] Fix label errors found (and re-freeze with a version bump, noted in changelog): none found; one low-confidence missing label and the q-022/q-033 decision are proposed in `eval/LABEL_ISSUES.md` for Aldi (Claude does not edit the frozen dataset)
- Known input: dataset-v1 labels UU 11/2008 articles BPK lists as partly revoked by UU 1/2023: q-022 (test; Pasal 46 grade 2, Pasal 30 grade 1) and q-033 (dev; Pasal 31 and 47, both grade 2). Their source_note already says the labels follow the corpus text. Decide here whether to keep, mark `superseded regulation`, or replace them (version bump per ADR-004); Claude does not edit the dataset.
- Acceptance: `reports/error_analysis.md` committed

### [x] T-36 Section headings out of article spans (added 23 Oct 2026, from T-21)
Links: FR-CHK-1, ADR-017
- [x] End each article span at the next section heading line; test in `tests/test_articles.py`
- [x] Re-ingest (still 273 articles, 0 spans with a heading) and rerun the eval: `reports/results/20261023T074949Z-ed9dbfc`
- [x] Paired before/after comparison across result files (`scripts/compare_runs.py`): `reports/results/20261023T074949Z-ed9dbfc.vs-a0d608d.md`
- Acceptance: dev comparison with CIs. Dev: no change established for any configuration (hybrid/article nDCG@10 -0.002 [-0.03, +0.02]). Test (reported only): hybrid/article nDCG@10 -0.022 [-0.049, -0.004], 0/3/7. Kept as a data correction (ADR-017).
- Effect on the T-18 reading, from `reports/results/20261023T074949Z-ed9dbfc`: dev hybrid/article vs bm25-id-title/article nDCG@10 is now +0.078 [+0.0003, +0.151] (16/3/11) and recall@10 +0.090 [0.000, +0.183]. A lower bound this close to 0 is borderline, not a robust difference; the serving decision is still open.

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

### [ ] T-35 Vercel deployment (added 23 Oct 2026, ADR-016)
Links: BR6, ADR-016
- [ ] Deploy the API as a Vercel Hobby Python function serving the retriever chosen on dev
- [ ] Measure bundle size (limit 500 MB uncompressed), memory, cold-start and warm latency; confirm CPU architecture
- [ ] CORS allowlist for the portfolio site's origin, from config (origin: https://naufaldi.vercel.app, given by Aldi 23 Oct 2026)
- Acceptance: deployed `/health` and `/search` answer requests from the portfolio origin, measurements recorded

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
- [ ] Search repo, history, and docs for any employer or internal-system names, credentials, or proprietary logic
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
| 23 Oct 2026 | T-15 CI eval with floor; T-07 fixed chunker, chapter context, multi-article chunk mapping; T-13 Indonesian and title-indexing BM25 variants (ADR-007); T-19 bootstrap CIs and paired win/loss, dataset hash made line-ending independent. Results: `reports/results/20261023T025613Z-a20cbfe`. | Dense retrieval (T-16) needs sentence-transformers and torch; Windows Application Control may block their native libraries. T-01 page check and T-03 manifest fields still with Aldi. | T-20 chunking ablation write-up, then T-16. |
| 23 Oct 2026 | T-20: per-retriever paired fixed-vs-article comparison in the runner (1 test), rerun on clean commit 0cb8d5c (metrics identical to the a20cbfe file, whose commit is no longer in history; that file is superseded by 20261023T065417Z-0cb8d5c), write-up in `reports/chunking_ablation.md`. | None. | T-16 dense retrieval: ask Aldi about sentence-transformers and torch first. |
| 23 Oct 2026 | T-16: torch blocked by Application Control and too big for Vercel Hobby, so dense runs on onnxruntime (ADR-016, approved by Aldi); model 1 multilingual-e5-small int8 ONNX (ADR-006). Results `reports/results/20261023T072143Z-28cc2a8`. Added T-35 (Vercel deploy). | Portfolio origin for CORS needed by T-35. BGE-M3 does not fit this machine's memory. | T-17 second model. |
| 23 Oct 2026 | T-17: `dense-e5-base` added by config; `eval.pairs` for direct paired comparisons (1 test). Clean cold run `reports/results/20261023T073208Z-cfff220` (embedding from scratch reproduced the cached metrics exactly). e5-small chosen for hybrid on dev (ADR-006). | None. | T-18 hybrid RRF, k and depth tuned on dev only. |
| 23 Oct 2026 | T-18: hybrid RRF retriever (6 tests); dev-only grid `reports/results/20261023T073543Z-a07f39f` kept k 60 / depth 50; full run `reports/results/20261023T073624Z-a0d608d`. Hybrid beats bm25-basic and dense-e5-small on dev, not established against bm25-id-title. | Serving choice (bm25-id-title vs hybrid) needs Aldi, see T-18. | T-20 is done; next T-21 error analysis. |
| 23 Oct 2026 | T-21: error analysis of hybrid/article on dev (10 failures; vocabulary gap 7, multi-article 4, chunk boundary 2, extraction 2, superseded 1, label error 0). Found section headings at the end of 76 of 273 article spans. `eval/LABEL_ISSUES.md` proposals. | Aldi: q-022/q-033 decision and the q-021 label proposal; serving choice from T-18. | T-22 reranker (stretch) or skip; heading fix as a dev experiment if wanted. |
| 23 Oct 2026 | T-36 (from T-21): section headings no longer end up in article spans (ADR-017); `scripts/compare_runs.py`; results `reports/results/20261023T074949Z-ed9dbfc`, before/after `reports/results/20261023T074949Z-ed9dbfc.vs-a0d608d.md`. Neutral on dev; small drop on test for hybrid (reported, not used to decide). | Serving choice still open (hybrid vs bm25-id-title now borderline on dev). | T-22 reranker or skip, then T-23. |
