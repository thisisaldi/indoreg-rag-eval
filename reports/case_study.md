# Case study: measuring retrieval over Indonesian data protection law

Author: Aldi. Built with Claude Code as a coding assistant. Retrieval only, not legal advice.

> Every number below comes from a committed file in `reports/results/`, named next to it. The 40 queries and their labels were drafted and checked by an LLM, not verified by a person (ADR-015), and the test split has 10 queries. Read the results as careful measurements on a small benchmark, not as general claims.

## Problem

A compliance analyst asks "can a company send customer data to a server abroad?" and needs the exact article and its source link. Indonesian regulations do not use those words: the answer sits in "transfer Data Pribadi ke luar wilayah hukum Negara Republik Indonesia" or "Penyelenggara Sistem Elektronik Lingkup Privat". Most retrieval demos show answers without measuring whether the right article was found. The goal here was the measurement: a labeled benchmark, honest uncertainty, and a documented look at the failures, then a small API that serves the configuration that measured best.

## Approach

- **Corpus.** Four official regulations from peraturan.bpk.go.id: UU 27/2022 (personal data protection), PP 71/2019, Permen Kominfo 20/2016 and UU 11/2008, with source URL, status and SHA-256 in `data/manifest.json` (ADR-009, ADR-013). Two are page images with an OCR-like text layer, so article headings arrive garbled ("Pasa722", "Pasal 6O"). A sequence-constrained, OCR-tolerant segmenter recovers all 273 body articles without guessing (ADR-010).
- **Labels at article level.** Each query is labeled with (document, article, grade), not with chunks, so changing the chunking does not change the labels (ADR-002). 40 queries in four types (exact reference, paraphrase, terminology, mixed Indonesian/English), split 30 dev and 10 test, frozen as `dataset-v1`.
- **Retrievers behind one interface.** BM25 (stdlib, three variants), dense retrieval with multilingual-e5 small and base as int8 ONNX models, and reciprocal rank fusion. The eval runner and the API build retrievers from the same config.
- **Statistics.** Recall@5/10, MRR, nDCG@10 with 1000-resample bootstrap CIs, and paired differences with per-query wins and losses. A difference whose CI includes 0 is reported as not established. All tuning used dev only.

## Results

From `reports/results/20261023T074949Z-ed9dbfc.md` (article chunks, dev, 95% CIs):

| retriever | nDCG@10 | MRR |
|---|---|---|
| BM25 baseline (bm25-basic) | 0.566 [0.43, 0.69] | 0.603 [0.45, 0.74] |
| BM25, Indonesian stopwords + title (bm25-id-title) | 0.581 [0.45, 0.71] | 0.629 [0.49, 0.76] |
| dense multilingual-e5-small | 0.542 [0.41, 0.68] | 0.624 [0.47, 0.78] |
| hybrid RRF (bm25-id-title + e5-small) | 0.659 [0.54, 0.77] | 0.713 [0.59, 0.84] |

- Hybrid beats the baseline on dev (nDCG@10 +0.093 [+0.01, +0.19], 14 wins, 6 losses) and on the untouched test split (+0.187 [+0.03, +0.41]).
- Against the stronger BM25 variant the gain is borderline: +0.078 [+0.0003, +0.151], 16 wins, 3 losses. I serve the hybrid (ADR-018) and say plainly that this edge is not robust.
- Dense alone does not beat BM25: every CI includes 0. BM25 and dense miss different queries, which is why fusion works.
- The larger e5-base looked better than e5-small (+0.100 nDCG@10 on dev) but the CI includes 0 ([-0.01, +0.21]); without the CI I would have picked the bigger model for no proven gain.
- Article chunks beat 1200-character windows on MRR and nDCG@10 for every retriever on dev, for example hybrid MRR -0.291 [-0.41, -0.18] with fixed windows.
- The RRF constant and depth were tuned on dev only (`reports/results/20261023T073543Z-a07f39f.md`); no setting beat the default k 60 / depth 50 with a CI excluding 0, so the default stayed.
- Serving latency at p50: about 5 ms for BM25 and 18 ms for the hybrid, warm, on a laptop CPU (`reports/results/20261023T084535Z-f50375f-latency.md`).

## Failure analysis

`reports/error_analysis.md` documents the 10 worst dev queries of the hybrid (`reports/results/20261023T073624Z-a0d608d.worst-dev.txt`). Vocabulary gaps dominate (7 of 10): users say "izin", "data sensitif", "hak untuk dilupakan"; the law says "persetujuan", "bersifat spesifik", "right to delisting". In that run terminology queries averaged nDCG@10 0.366, against 0.677 to 0.898 for the other types. Other causes: answers spread over several articles (4), OCR damage to the key term (2), penalty articles that cite the prohibition only by number ("Pasal 31 ayat (1)"), and a law number colliding with an article number.

The analysis also found a data bug: 76 of 273 article spans ended with the heading of the next section. I fixed it (ADR-017) and measured before and after (`reports/results/20261023T074949Z-ed9dbfc.vs-a0d608d.md`): no change on dev (hybrid nDCG@10 -0.002 [-0.03, +0.02]) and a small drop on test (-0.022 [-0.049, -0.004]). I kept the fix because it corrects the data, and reported that it did not improve the numbers. Two checks that might have explained failures did not: scanned documents were not retrieved worse, and the 512-token model limit affected one labeled article, which was found anyway.

## Tradeoffs and constraints

- **Torch could not run.** Windows Application Control blocked PyTorch's DLLs on the development machine, and torch is too large for the planned free Vercel deployment (500 MB bundle, 2 GB memory). The dense models run on onnxruntime with the authors' int8 exports instead (ADR-016). That ruled out BGE-M3, which scored highest for Indonesian in the published MIRACL results I found (ADR-006), and limited the choice to models with a small ONNX export.
- **Same model in eval and serving.** The benchmark measures the exact int8 file the API loads, so the reported numbers describe what is deployed. The cost of int8 against full precision was not measured.
- **Small, LLM-labeled benchmark.** Writing and checking 40 queries by hand was the largest planned cost; the owner chose LLM drafting and checking instead (ADR-014, ADR-015). The README and every results table say so.

## What I did not build, and why

- No vector database, Postgres or frontend: 273 articles fit in a numpy matrix, and brute-force search takes milliseconds (ADR-001, ADR-003).
- No answer generation with an LLM: the project measures retrieval; generation would need its own faithfulness evaluation.
- No reranker: no small multilingual ONNX cross-encoder fit the deployment, and 30 dev queries can barely separate the systems already (T-22, skipped).
- No stemmer, synonym list or weighted fusion: each is a plausible fix from the error analysis, but each would be tuned on the same 30 dev queries it was designed from.

## Reproducibility

A fresh clone from GitHub, with the PDFs downloaded from the manifest URLs and a locked install, reproduced the committed results exactly: identical rankings and metrics for all 480 query rows, with embeddings recomputed from scratch (`reports/results/20261023T080406Z-a67e1de.md`). This was checked on one Windows machine; other platforms are untested.

## Lessons

1. Confidence intervals changed decisions, not just tables. Two "improvements" (e5-base, the heading fix) looked real as point estimates and were not.
2. Error analysis is worth doing even when the fix does not move the metric: it found a real data bug and showed where the remaining errors live (vocabulary, not OCR).
3. Deployment constraints are part of model selection. The best model on paper could not run where the service will live, so the benchmark measured what can be deployed.
4. The weakest part of this benchmark is the labels. A human spot-check of the test split is the most valuable next step before any public claim (ADR-015).
