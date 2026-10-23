# Architecture (T-30)

Offline steps write files; the eval runner and the API build the same retrievers from the same chunk files, so the API serves what was benchmarked (design.md 1).

```mermaid
flowchart TD
    subgraph offline["Offline, deterministic (make ingest)"]
        raw["data/raw/*.pdf<br/>+ data/manifest.json<br/>(source URL, status, SHA-256)"]
        ingest["ingest: pdfplumber text,<br/>noise filter, OCR-tolerant<br/>Pasal segmentation (ADR-010)"]
        processed["data/processed/<br/>doc.txt + doc.articles.json<br/>(article spans)"]
        chunk["chunking:<br/>article | fixed 1200/200"]
        chunks["data/chunks/<br/>article.jsonl, fixed.jsonl"]
        raw --> ingest --> processed --> chunk --> chunks
    end

    subgraph retrieval["Retrievers (one Retriever protocol, built from config)"]
        bm25["BM25<br/>basic | id | id-title<br/>(stdlib, ADR-007)"]
        dense["Dense<br/>multilingual-e5 small | base<br/>int8 ONNX, numpy cosine<br/>(ADR-006, ADR-016)"]
        cache[("data/cache/embeddings<br/>keyed by model + chunk text")]
        hybrid["Hybrid RRF<br/>bm25-id-title + e5-small<br/>k 60, depth 50"]
        dense <--> cache
        bm25 --> hybrid
        dense --> hybrid
    end

    chunks --> bm25
    chunks --> dense

    subgraph evaluation["Evaluation (make eval)"]
        dataset["eval/dataset.jsonl<br/>40 queries, article labels<br/>dev 30 / test 10 (dataset-v1)"]
        runner["eval runner: chunks to articles<br/>via spans, Recall@k, MRR, nDCG@10,<br/>bootstrap CIs, paired win/loss"]
        results["reports/results/<br/>run.json + run.md"]
        dataset --> runner --> results
    end

    subgraph serving["Serving (make serve, Docker, Vercel planned)"]
        api["FastAPI<br/>POST /search, GET /health<br/>request IDs, JSON logs"]
        client["client<br/>(portfolio site)"]
        api -- "results with title, article,<br/>doc_status, source_url, disclaimer" --> client
    end

    bm25 --> runner
    dense --> runner
    hybrid --> runner
    hybrid -- "served retriever (ADR-018)" --> api
```

CI runs lint, type checks and the tests, including a deterministic eval on a fictional fixture corpus with a metric floor (T-15), then builds the Docker image from that fixture and smoke-tests `/health` and `/search` (T-28).
