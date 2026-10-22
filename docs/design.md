# IndoReg-RAG Eval: Design

Status: Draft v0.1 (22 Oct 2026). Items marked PROVISIONAL depend on T-01 and T-04 outcomes.
Traceability: requirements.md (BR, FR, NFR), tasks.md (T-xx).

## 1. Architecture

```
data/raw PDFs + manifest.json
        |
        v
  [ingest]  extract text, normalize, log failures        (FR-ING)
        |
        v
  data/processed/<doc_id>.txt + <doc_id>.articles.json   (article spans)
        |
        v
  [chunk]   article chunker | fixed-overlap chunker      (FR-CHK)
        |
        v
  data/chunks/<strategy>.jsonl
        |
        +--------------------+--------------------+
        v                    v                    v
   [BM25 index]        [dense index]         [hybrid RRF]   (FR-RET)
        \                    |                    /
         +-------- Retriever interface -----------+
                   |                    |
                   v                    v
            [eval runner]          [FastAPI /search]
        metrics, CIs, latency         (FR-API)
                   |
                   v
       reports/results/*.json + tables (FR-EVAL)
```

Principle: ingestion and chunking are offline, deterministic, and write files. Retrievers build from chunk files. The eval runner and the API both consume the same Retriever interface, so the API serves exactly what was benchmarked.

## 2. Module layout

```
src/indoreg/
  config.py          pydantic settings, YAML + env, validation at startup
  logging.py         JSON logging, request ID context
  schemas.py         Manifest, Chunk, Query, Result models (pydantic)
  ingest/
    extract.py       PDF to text (extractor chosen in T-04)
    normalize.py     whitespace, header/footer noise removal
    articles.py      detect Pasal/BAB boundaries, emit article spans
    pipeline.py      orchestrates, logs failures, writes processed files
  chunking/
    article.py
    fixed.py
  retrieval/
    base.py          Retriever protocol, RetrievalResult
    bm25.py
    dense.py
    hybrid.py        reciprocal rank fusion
    rerank.py        stretch (T-22)
    registry.py      build retriever from config name
  eval/
    dataset.py       load and validate dataset.jsonl
    metrics.py       recall_at_k, mrr, ndcg_at_k
    bootstrap.py     seeded bootstrap CIs, win/loss
    runner.py        CLI entry: run configs, write results
    report.py        markdown tables from result JSON
  api/
    app.py           FastAPI app factory
    models.py        request/response models
    deps.py          retriever loading, lifespan
configs/
  default.yaml       paths, chunking params, retriever configs
  eval.yaml          which retrievers and splits to run
```

## 3. Data schemas

### 3.1 Manifest entry (`data/manifest.json`)
```json
{
  "doc_id": "uu-27-2022",
  "title": "Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi",
  "reg_type": "UU",
  "number": "27",
  "year": 2022,
  "status": "in_force | amended | revoked | unknown",
  "status_source": "URL or note",
  "source_url": "https://...",
  "retrieved_on": "2026-10-23",
  "filename": "uu-27-2022.pdf",
  "sha256": "..."
}
```
The example entry is illustrative. Verify each real entry against its source before committing.

### 3.2 Article span (`data/processed/<doc_id>.articles.json`)
```json
{"doc_id": "...", "article": "26", "chapter": "BAB IV", "char_start": 10234, "char_end": 11876}
```
Offsets index into `<doc_id>.txt`. This is the single source of truth linking text to articles, and it is what makes labels chunking-independent.

### 3.3 Chunk (`data/chunks/<strategy>.jsonl`)
```json
{
  "chunk_id": "uu-27-2022:article:26",
  "doc_id": "uu-27-2022",
  "strategy": "article | fixed",
  "article": "26",
  "chapter": "BAB IV",
  "char_start": 10234,
  "char_end": 11876,
  "text": "...",
  "source_url": "https://...",
  "doc_status": "in_force"
}
```
For the fixed strategy, `article` may be null or multi-valued when a chunk spans a boundary. Store the list of overlapping article numbers in `articles`.

### 3.4 Query (`eval/dataset.jsonl`)
```json
{
  "query_id": "q-014",
  "query": "...",
  "type": "exact_ref | paraphrase | terminology | mixed_id_en",
  "split": "dev | test",
  "relevant": [{"doc_id": "uu-27-2022", "article": "26", "grade": 2}],
  "source_note": "where the label was verified",
  "version": 1
}
```
Grades: 2 = directly answers, 1 = partially relevant or supporting. Document the rule in `eval/LABELING.md` (T-09).

### 3.5 Result file (`reports/results/<run_id>.json`)
Contains: run ID, git SHA, timestamp, config snapshot, dataset version, per-query ranked outputs, per-query metrics, aggregate metrics with CIs, latency p50 and p95, embedding time and index size where relevant.

## 4. Key design decisions

### 4.1 Labels are article-level, not chunk-level
Labels reference (doc_id, article). A retrieved chunk is mapped to article units through the span table: article chunks map directly, fixed chunks map to every article whose span they overlap. Metrics are computed over deduplicated article units, keeping the best rank per unit. This keeps the chunking ablation fair, because labels do not change when chunking changes. This supersedes the "chunk or article" wording in FR-EVAL-1 and T-10 (recorded as ADR-002).

### 4.2 Local index, no vector database
Corpus is small (expected under 10k chunks). Dense search is brute-force cosine over a numpy matrix. Embeddings are cached under `data/cache/` keyed by `sha256(model_name + chunk file hash)`. Revisit only if a measured latency problem appears.

### 4.3 Single Retriever interface
```python
class RetrievalResult(BaseModel):
    chunk_id: str
    score: float
    rank: int

class Retriever(Protocol):
    name: str
    def build(self, chunks: Sequence[Chunk]) -> None: ...
    def search(self, query: str, top_k: int) -> list[RetrievalResult]: ...
```
Retrievers are constructed from config by `registry.py`. Adding a model or variant is a config change.

### 4.4 Hybrid fusion
Reciprocal rank fusion: `score(d) = sum over retrievers r of 1 / (k + rank_r(d))`, default `k = 60`. Candidate depth per retriever is a config value (default 50). Tune `k` and depth on dev only.

### 4.5 Metrics
- Recall@k: fraction of relevant article units found in top k.
- MRR: reciprocal rank of the first relevant unit (0 if none in the retrieved list).
- nDCG@10: graded gain `2^grade - 1`, standard log2 discount, normalized by ideal ranking.
- Bootstrap: resample queries with replacement, 1000 iterations, fixed seed, percentile 95% CI. Paired bootstrap for differences between two configs.

### 4.6 Determinism
Fixed seeds, sorted file iteration, stable tie-breaking on `chunk_id`, pinned dependencies. Dense retrieval on CPU with fixed model revision recorded in the result file. Results must reproduce within a small float tolerance, stated in the README.

### 4.7 Error handling
- Ingestion: per-document and per-page try/except, log with doc ID and page, continue, emit a summary of failures at the end.
- Eval: a retriever failure on one query is recorded as an error row, not silently dropped. The runner fails the run if more than a configured fraction of queries error.
- API: validation errors return 422 with a structured body, unexpected errors return 500 with a request ID and no stack trace in the body.

## 5. API design

### `POST /search`
Request:
```json
{"query": "string, 1 to 500 chars after strip", "top_k": 5}
```
Response:
```json
{
  "request_id": "...",
  "query": "...",
  "retriever": "hybrid-bge-m3",
  "results": [
    {
      "rank": 1,
      "score": 0.0,
      "text": "...",
      "doc_id": "...",
      "title": "...",
      "article": "26",
      "doc_status": "in_force",
      "source_url": "https://..."
    }
  ],
  "latency_ms": 0,
  "disclaimer": "Retrieval only. Not legal advice. Check amendment and revocation status at the source."
}
```
`top_k` default 5, range 1 to 20. Whitespace-only queries return 422.

### `GET /health`
Returns service status, loaded retriever name, chunk count, index build timestamp.

The retriever is loaded once in the app lifespan and shared read-only across requests.

## 6. Configuration

`configs/default.yaml` (illustrative keys):
```yaml
paths: {raw: data/raw, processed: data/processed, chunks: data/chunks, cache: data/cache, results: reports/results}
chunking:
  article: {}
  fixed: {size_chars: 1200, overlap_chars: 200}
retrievers:
  bm25-basic: {type: bm25, preprocess: basic}
  dense-model-a: {type: dense, model: TBD, revision: TBD}
  hybrid: {type: hybrid, members: [bm25-basic, dense-model-a], rrf_k: 60, depth: 50}
serving: {retriever: hybrid, strategy: article}
```
Environment variables override YAML via a `INDOREG_` prefix. Chunk size values and model names are starting points, not decisions.

## 7. Testing strategy

| Layer | Tests | Notes |
|---|---|---|
| Metrics, bootstrap | Hand-computed fixtures | No models needed |
| Article detection, chunkers | Small text fixtures with edge cases | Missing markers, long articles, ayat |
| Retrievers | Tiny synthetic corpus, deterministic | Dense uses a stub embedder in unit tests |
| Eval runner | Fixture corpus and 5 to 10 queries | This is the CI eval (T-15) |
| API | FastAPI TestClient with stub retriever | Valid, empty, over-length, bad top_k, schema |
| Smoke | Docker image answers `/health` | Run in CI (T-28) |

Real-model runs happen locally and are never required in CI (NFR6). The CI eval has a recorded metric floor so regressions fail the build.

## 8. CI/CD

Workflow `ci.yml`: install with cached pip, ruff, type check, pytest, fixture eval with floor check, then Docker build and `/health` smoke test. Triggered on push and pull request.

## 9. Deployment

Dockerfile with slim base, non-root user, pinned lockfile install. PROVISIONAL: whether the model and prebuilt index are baked into the image or mounted as a volume. Decide at T-26 based on image size and cold-start latency, record in decisions.md.

## 10. Observability

JSON logs with request ID, query length (not query text by default), retriever name, top_k, latency. Query text logging is off by default and controlled by config, since real deployments may log sensitive queries.

## 11. Security and privacy

- Public data only, no secrets in the repo, pre-commit secret scan.
- No query text in logs by default.
- Input length limits on the API.
- Disclaimer in every API response and in the README.

## 12. Open design items

- DI1: Extractor choice and article regex robustness (T-04). PROVISIONAL until tested on real documents.
- DI2: Handling of ayat-level relevance. Default is article-level only, revisit if error analysis shows many near-misses within long articles.
- DI3: Whether the Indonesian-aware BM25 variant uses a stemmer library, and which. Decide at T-13.
- DI4: Embedding models and revisions (OD2 in requirements.md).
