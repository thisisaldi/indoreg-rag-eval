# IndoReg-RAG Eval

An evaluation-first retrieval benchmark over Indonesian regulations. It compares BM25, dense, and hybrid retrieval on a manually labeled query set and serves the best configuration through a cited search API.

Status: in development (target 4 Nov 2026).

> **Not legal advice.** This project retrieves regulation passages for information purposes. It does not model every amendment or revocation. Always verify status and text at the official source.

## Problem

Compliance and policy analysts search regulations by paraphrase, not by article number. Keyword search misses terminology variants, and plain "chat with your docs" demos rarely measure whether the right passage was found. This project measures retrieval quality with a labeled benchmark, reports uncertainty, and documents failures.

## What is in here

- Ingestion and two chunking strategies (article-based, fixed overlap)
- BM25, dense (multiple embedding models), and hybrid (reciprocal rank fusion) retrieval
- A 40-query labeled dataset with a frozen test split
- Metrics: Recall@5, Recall@10, MRR, nDCG@10, latency p50 and p95, with bootstrap confidence intervals
- A FastAPI `/search` endpoint with source citations, Docker image, and CI

## Results

To be filled from files in `reports/results/` after the benchmark runs. No numbers are stated here until they exist.

## Quickstart

To be completed after T-05 and T-14.

```
make install
make ingest
make eval
make serve
```

## Repository layout

See [docs/design.md](docs/design.md).

## Documentation

- [docs/requirements.md](docs/requirements.md): goals, business and functional requirements
- [docs/design.md](docs/design.md): architecture, schemas, decisions
- [docs/tasks.md](docs/tasks.md): task breakdown with acceptance criteria
- [docs/timeline.md](docs/timeline.md): schedule and milestones
- [docs/decisions.md](docs/decisions.md): decision log

## Data and licensing

All sources are public official regulations. Each source URL, retrieval date, and status is recorded in `data/manifest.json`. Raw regulation text (the downloaded PDFs) is not redistributed: `data/raw/` is gitignored, so download the files from the source URLs in the manifest. Check the source terms before redistributing any raw file.

## Limitations

To be completed with measured findings and known failure modes.
