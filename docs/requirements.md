# IndoReg-RAG Eval: Requirements

Status: Draft v0.1 (22 Oct 2026)
Owner: Aldi
Project window: 22 Oct to 4 Nov 2026

## 1. Overview

IndoReg-RAG Eval is an evaluation-first retrieval system over Indonesian regulations. It benchmarks BM25, dense, and hybrid retrieval on a manually labeled query set, and exposes the best configuration through a cited search API.

Working topic: personal data protection (UU PDP and implementing regulations). Subject to the feasibility check in T-01. If the sources fail the check, switch topic before any other work.

Primary persona: a compliance analyst who needs the exact article and its source link, fast, and who searches by paraphrase rather than by article number.

## 2. Goals and non-goals

### Goals
- G1: Produce a credible, reproducible retrieval benchmark with a baseline and measured improvements.
- G2: Show end-to-end ownership: ingestion, evaluation, API, container, CI, write-up.
- G3: Report results honestly, including uncertainty and failures.

### Non-goals
- LLM answer generation (Week 3 to 4 extension)
- Frontend or UI
- Vector database server, Postgres, Kubernetes
- Fine-tuning
- Authoritative legal advice

## 3. Business requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| BR1 | Retrieve relevant regulation passages for Indonesian natural-language queries | Recall@5, Recall@10, MRR, nDCG@10 reported on the labeled set |
| BR2 | Every result is traceable to its source | Each result has document ID, title, article number (when available), source URL |
| BR3 | Strategies are compared fairly | BM25, dense (2 to 3 models), and hybrid run on identical chunks, queries, and metrics |
| BR4 | Differences are statistically honest | Every comparison table has bootstrap 95% CIs or per-query win/loss counts |
| BR5 | Results are reproducible | One command reruns the benchmark; a clean clone installs and passes tests |
| BR6 | System is usable | `/search` API with validation, typed responses, runnable Docker image |
| BR7 | Regressions are caught | CI runs unit tests and a small deterministic eval on every PR |
| BR8 | Limits are stated | README states this is retrieval, not legal advice, and that amendment and revocation status is only partly modeled |

## 4. Functional requirements

### Ingestion (FR-ING)
- FR-ING-1: The system reads source PDFs listed in `data/manifest.json` and extracts text.
- FR-ING-2: The manifest records for each source: document ID, title, regulation number and year, status (in force, amended, revoked, unknown), source URL, retrieved date, local filename, SHA-256 hash.
- FR-ING-3: Extraction failures and low-quality pages are logged with document ID and page, and do not crash the run.
- FR-ING-4: Ingestion is deterministic: the same inputs produce byte-identical chunk files.

### Chunking (FR-CHK)
- FR-CHK-1: Article-based chunker splits on article markers (Pasal) and preserves article number and parent chapter when present.
- FR-CHK-2: Fixed-size overlapping chunker with configurable size and overlap.
- FR-CHK-3: Every chunk carries document ID, chunk ID, article number (nullable), character offsets, and source URL.

### Retrieval (FR-RET)
- FR-RET-1: BM25 retriever with a basic tokenizer and an Indonesian-aware preprocessing variant.
- FR-RET-2: Dense retriever using Sentence Transformers, with embeddings cached on disk keyed by model name and chunk file hash.
- FR-RET-3: At least 2 embedding models compared (3 if time allows).
- FR-RET-4: Hybrid retriever using reciprocal rank fusion over BM25 and the best dense model.
- FR-RET-5 (stretch): Cross-encoder reranker over top-k candidates.
- FR-RET-6: All retrievers implement one shared interface so the eval runner is retriever-agnostic.

### Evaluation (FR-EVAL)
- FR-EVAL-1: Golden dataset in `eval/dataset.jsonl`, 40 queries, each with query text, query type, relevant article labels (doc ID, article, grade), source reference, and split (dev or test).
- FR-EVAL-2: Query type mix of about 25% exact reference, 40% paraphrase, 25% terminology variation, 10% mixed ID/EN.
- FR-EVAL-3: About 30 dev queries and about 10 frozen test queries. Tuning uses dev only. Both are reported.
- FR-EVAL-4: Metrics module implements Recall@k, MRR, nDCG@10, with unit tests against hand-computed examples.
- FR-EVAL-5: Bootstrap 95% CIs and per-query win/loss between any two configurations.
- FR-EVAL-6: Results are written as machine-readable JSON under `reports/results/`, with config, git SHA, and timestamp.
- FR-EVAL-7: A single CLI command runs all configured retrievers and writes the comparison table.
- FR-EVAL-8: Latency (p50, p95) is recorded per configuration.

### API (FR-API)
- FR-API-1: `POST /search` accepts a query and optional `top_k` (default 5, max 20).
- FR-API-2: Response returns ranked passages with score, text, document ID, title, article number, source URL, and document status.
- FR-API-3: Empty or whitespace queries return a 422 with a clear error. Over-length queries are rejected.
- FR-API-4: `GET /health` returns service and index status.
- FR-API-5: OpenAPI docs are generated and sample requests are in the README.
- FR-API-6: Responses carry a disclaimer field stating the output is not legal advice.

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | Typed Python, mypy or pyright clean on `src/` |
| NFR2 | Config via YAML and environment variables, no hardcoded paths or model names in code |
| NFR3 | Structured JSON logs with request ID |
| NFR4 | Dependencies pinned with a lockfile |
| NFR5 | pytest coverage on metrics, chunkers, retrievers (deterministic), and API |
| NFR6 | CI completes in under 10 minutes using a small deterministic fixture, not the full model download |
| NFR7 | Retrieval p95 latency measured and reported for each configuration |
| NFR8 | Cost reporting separates actual cash cost from estimated compute cost |
| NFR9 | No secrets in the repo, pre-commit secret scan enabled |

## 6. Constraints and confidentiality

- Public data only. No [employer] or [internal system] data, names, schemas, or logic anywhere in the repo, commits, or write-ups.
- Respect source terms. Check JDIH terms before any automated download. Default to manual download with URLs recorded in the manifest.
- Time budget: about 27 hours (1.5h weekdays, 3h weekends).
- Single repository, no extra infrastructure unless a measured problem requires it.

## 7. Assumptions

- At least 10 text-extractable official regulations exist for the chosen topic.
- A CPU-only machine is enough for embedding a corpus of this size.
- Sentence Transformers models for Indonesian can be downloaded and cached locally.

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PDFs are scanned or have messy structure | High | High | T-01 feasibility check, prefer text-based sources, drop and log problem documents |
| Labeling takes longer than planned | High | High | Guideline first, start Day 4, 40 query cap |
| Scraping terms issue | Medium | Medium | Manual download, URLs in manifest |
| Dense model loses to BM25 | Medium | Low | Report it with an explanation, this is a valid result |
| Weekday time slips | High | Medium | Weekend buffer on Day 10, defined cut order in timeline.md |
| Corpus contains amended or revoked rules | Medium | Medium | Store status metadata, show it in API output, document in README |
| 40 queries too few for strong claims | Certain | Medium | Bootstrap CIs, state the limit in the case study |

## 9. Definition of done

- A reviewer can read the README, run one command to reproduce the benchmark table, open the error analysis, call `/search` in Docker, and see CI green.
- Every number in the case study comes from a committed result file.
- At least 5 documented failure cases (target 10), each with a cause.
- Confidentiality audit passed (T-34).

## 10. Open decisions

- OD1: Confirm topic (personal data protection) after T-01.
- OD2: Embedding models to compare. Starting candidates: BGE-M3, multilingual-e5. Verify current Indonesian benchmarks before committing.
- OD3: Whether to run the reranker, decided on Day 10 based on schedule.
