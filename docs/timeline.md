# IndoReg-RAG Eval: Timeline

Window: Thu 22 Oct to Wed 4 Nov 2026
Budget: 1.5h weekdays, 3h weekends, about 27h total
Task details: see tasks.md. Requirements: see requirements.md.

## Milestones

| Milestone | Target date | Exit criteria |
|---|---|---|
| M1 Foundation | Sat 24 Oct | Repo public, manifest done, ingestion and chunkers working, CI green |
| M2 Dataset | Mon 26 Oct | 40 labeled queries, test split frozen, metrics tested |
| M3 Baselines | Thu 29 Oct | BM25, dense (2 models), hybrid compared on identical data |
| M4 Analysis | Sat 31 Oct | CIs, chunking ablation, error analysis, tag `v0.1-benchmark` |
| M5 Service | Mon 2 Nov | API, Docker image, latency table, CI builds image |
| M6 Packaging | Wed 4 Nov | README, diagram, case study, demo, resume bullets |

## Daily plan

| Day | Date | Hrs | Focus | Tasks | Artifact |
|---|---|---|---|---|---|
| 1 | Thu 22 Oct | 1.5 | Feasibility and repo | T-01, T-02 | Public repo, requirements in `docs/` |
| 2 | Fri 23 Oct | 1.5 | Sources and manifest | T-03, T-04 | `data/manifest.json`, extraction spike notes |
| 3 | Sat 24 Oct | 3 | Ingestion, chunking, CI | T-05, T-06, T-07, T-08 | Ingest script, green CI |
| 4 | Sun 25 Oct | 3 | Labeling | T-09, T-10 | `eval/dataset.jsonl` v1 (20 queries) |
| 5 | Mon 26 Oct | 1.5 | Dataset and metrics | T-11, T-12 | Frozen dataset, `metrics.py` with tests |
| 6 | Tue 27 Oct | 1.5 | BM25 baseline | T-13, T-14, T-15 | Baseline JSON, CI deterministic eval |
| 7 | Wed 28 Oct | 1.5 | Dense model 1 | T-16 | First BM25 vs dense table |
| 8 | Thu 29 Oct | 1.5 | Model 2 and hybrid | T-17, T-18 | Model comparison table |
| 9 | Fri 30 Oct | 1.5 | Uncertainty and ablation | T-19, T-20 | Results with CIs |
| 10 | Sat 31 Oct | 3 | Error analysis and release | T-21, T-22 (stretch), T-23 | `error_analysis.md`, tag `v0.1-benchmark` |
| 11 | Sun 1 Nov | 3 | API and logging | T-24, T-25 | Working `/search` |
| 12 | Mon 2 Nov | 1.5 | Container and latency | T-26, T-27, T-28 | Image, latency table |
| 13 | Tue 3 Nov | 1.5 | Docs | T-29, T-30, T-31 | README, diagram, case study draft |
| 14 | Wed 4 Nov | 1.5 | Demo and wrap-up | T-32, T-33, T-34 | Demo, resume bullets, next project brief |

## Cut order if behind

Cut from the top, never from the bottom:

1. T-22 reranker
2. 3rd embedding model (T-17 stays at 2 models)
3. T-20 chunking ablation extras (keep the basic article vs fixed comparison)
4. Indonesian-aware BM25 variant (T-13 keeps basic tokenizer only)
5. T-32 demo video (replace with screenshots and curl examples)

Never cut: golden set (T-09 to T-11), bootstrap CIs (T-19), CI (T-08, T-15), error analysis (T-21), confidentiality audit (T-34).

## Checkpoints

| Date | Check | If failing |
|---|---|---|
| Fri 23 Oct | At least 10 usable sources in manifest | Drop the topic or narrow to a single regulation family, decide same day |
| Mon 26 Oct | 40 queries labeled | Cap at 30, note the limit in the case study |
| Thu 29 Oct | Hybrid working | Skip hybrid tuning, report what exists |
| Sat 31 Oct | `v0.1-benchmark` tagged | Use Sun 1 Nov to finish, shift API to Mon, drop the Docker polish |

## Weekly rhythm

- Weekdays: one task cluster per day, stop when the artifact exists, even if early.
- Weekends: harder, longer work (extraction, labeling, error analysis, API).
- End of each day: commit, push, tick the boxes in tasks.md, note blockers in one line.
