# CLAUDE.md: IndoReg-RAG Eval

Evaluation-first retrieval benchmark over Indonesian regulations (personal data protection topic, pending T-01). Portfolio project owned by Aldi. Retrieval only, not legal advice.

## Source of truth

Read these before any task, in this order:
1. `docs/requirements.md` (what and why, BR/FR/NFR IDs)
2. `docs/design.md` (how: schemas, interfaces, decisions)
3. `docs/tasks.md` (what to do now, acceptance criteria)
4. `docs/decisions.md` (ADR log)

If code and spec disagree, stop and say so. Do not silently change the spec. Propose the change and wait.

## Workflow rules

- Work on exactly one task ID at a time (T-xx). Do not start the next task unprompted.
- Start non-trivial tasks with a short plan: files to touch, tests to write, risks. Wait for approval.
- Tests first where practical. A task is done only when its acceptance criteria in `docs/tasks.md` pass.
- When done: tick the checkboxes in `docs/tasks.md`, add a line to its progress log, summarize what changed and what you did not verify.
- One task per branch (`t-xx-short-name`), small commits, conventional commit messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Record any design decision not already covered as a new ADR in `docs/decisions.md`.

## Commands (created in T-05, keep in sync)

```
make install     # editable install with dev deps
make lint        # ruff
make typecheck   # mypy or pyright on src/
make test        # pytest
make ingest      # manifest -> processed text -> chunks
make eval        # run configured retrievers, write reports/results/
make serve       # run the API locally
```

## Code standards

- Python 3.11+, full type hints on `src/`, pydantic models for all data crossing a boundary.
- No hardcoded paths, model names, or magic numbers: use `configs/*.yaml` and `config.py`.
- Structured logging via `indoreg.logging`, never `print` in `src/`.
- Deterministic by default: seeds, sorted iteration, stable tie-breaks.
- Catch specific exceptions, log with context, never swallow errors silently.
- Prefer small pure functions. Retrievers implement the `Retriever` protocol in `retrieval/base.py`.

## Hard rules (do not violate)

1. **Never edit `eval/dataset.jsonl` labels or the test split.** Labels are verified by Aldi. Claude may draft candidate queries and labels only in `eval/drafts/` (ADR-014). Propose changes in a note instead. Read-only.
2. **Never tune on the test split.** Hyperparameters are chosen on dev only. Report both.
3. **Never invent or estimate metrics.** Every number in the README, reports, or case study must come from a file in `reports/results/`. If a result does not exist, say so.
4. **Confidentiality.** Public data only. No [employer], [internal system], employer names, internal systems, credentials, or proprietary logic anywhere in code, comments, commits, or docs. If you see any, stop and flag it.
5. **No new dependencies, services, or infrastructure without asking.** The design deliberately excludes a vector DB server, Postgres, a frontend, and an LLM API. Justify any addition with a measured problem.
6. **No scraping without checking the source's terms.** Default to the manual download plus manifest workflow.
7. **Do not weaken tests or CI floors to make a build pass.** Fix the cause or raise it.
8. **Legal data handling.** Always carry document status and source URL through the pipeline. Never present output as legal advice.

## Evaluation conventions

- Labels are article-level (`doc_id`, `article`). Chunks map to articles via the span table (design.md 4.1).
- Metrics: Recall@5, Recall@10, MRR, nDCG@10, plus p50 and p95 latency.
- Every comparison reports bootstrap 95% CIs or per-query win/loss. Do not call a difference real without it.
- If a result looks too good, suspect leakage or a label bug first and investigate before reporting.

## When blocked or unsure

Ask a specific question with the options you see. Do not guess on data semantics, label meaning, or legal document status.
