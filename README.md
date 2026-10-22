# IndoReg-RAG Eval

[![CI](https://github.com/thisisaldi/indoreg-rag-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/thisisaldi/indoreg-rag-eval/actions/workflows/ci.yml)

An evaluation-first retrieval benchmark over Indonesian regulations. It compares BM25, dense, and hybrid retrieval on a manually labeled query set and serves the best configuration through a cited search API.

Status: in development (target 4 Nov 2026).

> **Not legal advice.** This project retrieves regulation passages for information purposes. It does not model every amendment or revocation. Always verify status and text at the official source.

## Problem

Compliance and policy analysts search regulations by paraphrase, not by article number. Keyword search misses terminology variants, and plain "chat with your docs" demos rarely measure whether the right passage was found. This project measures retrieval quality with a labeled benchmark, reports uncertainty, and documents failures.

## What is in here

- Ingestion and two chunking strategies (article-based, fixed overlap)
- BM25, dense (multiple embedding models), and hybrid (reciprocal rank fusion) retrieval
- A 40-query labeled dataset with a frozen test split (queries and labels drafted by an LLM, every label verified by the author against the official PDF; see `docs/decisions.md` ADR-014)
- Metrics: Recall@5, Recall@10, MRR, nDCG@10, latency p50 and p95, with bootstrap confidence intervals
- A FastAPI `/search` endpoint with source citations, Docker image, and CI

## Results

To be filled from files in `reports/results/` after the benchmark runs. No numbers are stated here until they exist.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned in `.python-version`; uv installs it if missing.

```
make install     # uv sync
make lint        # uv run ruff check . && uv run ruff format --check .
make typecheck   # uv run mypy
make test        # uv run pytest
```

Try it (needs the source PDFs in `data/raw/`, see `data/manifest.json`; they are not in the repo):

```
make ingest                                  # uv run python -m indoreg.ingest.pipeline
make search Q="transfer data pribadi ke luar negeri"
                                             # uv run python -m indoreg.search "..."
```

`make ingest` turns each PDF into cleaned text and article spans under `data/processed/` and one chunk per article in `data/chunks/article.jsonl` (both gitignored, as they contain regulation text). `make search` ranks articles with BM25 and prints the article, document, status and source link. The search is a demo of the pipeline, not a benchmarked result.

Without `make` (for example on Windows), run the command after each `#`. `pip install -e .` also works in any Python 3.11+ environment. `make eval` and `make serve` arrive with T-14 and T-24.

Configuration lives in `configs/default.yaml`; any key can be overridden with an `INDOREG_` environment variable, nested keys joined by `__` (for example `INDOREG_CHUNKING__FIXED__SIZE_CHARS=800`).

## Repository layout

See [docs/design.md](docs/design.md).

## Documentation

- [docs/requirements.md](docs/requirements.md): goals, business and functional requirements
- [docs/design.md](docs/design.md): architecture, schemas, decisions
- [docs/tasks.md](docs/tasks.md): task breakdown with acceptance criteria
- [docs/timeline.md](docs/timeline.md): schedule and milestones
- [docs/decisions.md](docs/decisions.md): decision log

## Data and licensing

The code in this repository is released under the [MIT License](LICENSE). The license does not cover the regulation texts or any third-party models, which have their own terms.

All sources are public official regulations. Each source URL, retrieval date, and status is recorded in `data/manifest.json`. Raw regulation text (the downloaded PDFs) is not redistributed: `data/raw/` is gitignored, so download the files from the source URLs in the manifest. Check the source terms before redistributing any raw file.

## Limitations

To be completed with measured findings and known failure modes.
