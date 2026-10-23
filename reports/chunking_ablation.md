# Chunking ablation: article vs fixed-size (T-20)

Source: `reports/results/20261023T065417Z-0cb8d5c.{json,md}` (clean commit 0cb8d5c, dataset `dataset-v1`, sha256 b22ca6abf960). Every number below is copied from that file.

> Labels were drafted and checked by an LLM, not human-verified (ADR-015). The corpus is 4 documents (ADR-013).

## Setup

- Variable: chunking strategy only. `article` = one chunk per body article (273 chunks). `fixed` = 1200-character windows with 200-character overlap over the body text (188 chunks).
- Held constant: retriever (each of the three BM25 variants, ADR-007), queries (30 dev, 10 test), metrics, depth.
- Labels are article-level. A fixed chunk counts for every article whose span it overlaps, and each article keeps its best rank (ADR-002), so the labels do not change with chunking.
- Each cell is the mean paired difference `fixed minus article` for the same retriever, with a 95% bootstrap CI (1000 resamples, seed 42) and per-query wins/losses/ties of fixed vs article. A CI that includes 0 does not establish a difference.

## Dev (30 queries)

| retriever | recall@5 | recall@10 | MRR | ndcg@10 |
|---|---|---|---|---|
| bm25-basic | -0.118 [-0.25, +0.00] 4/8/18 | -0.085 [-0.23, +0.06] 4/6/20 | -0.203 [-0.34, -0.06] 5/19/6 | -0.159 [-0.26, -0.04] 5/19/6 |
| bm25-id | -0.115 [-0.27, +0.03] 4/9/17 | -0.107 [-0.20, -0.02] 1/8/21 | -0.207 [-0.34, -0.08] 6/19/5 | -0.163 [-0.26, -0.07] 6/20/4 |
| bm25-id-title | -0.023 [-0.17, +0.11] 5/7/18 | -0.065 [-0.17, +0.03] 3/7/20 | -0.248 [-0.38, -0.12] 6/20/4 | -0.155 [-0.25, -0.06] 8/18/4 |

The upper bound shown as +0.00 for bm25-basic recall@5 is +0.004 in the JSON, so that CI includes 0.

## Test (10 queries, reported, not used for any choice)

| retriever | recall@5 | recall@10 | MRR | ndcg@10 |
|---|---|---|---|---|
| bm25-basic | -0.233 [-0.45, -0.05] 0/4/6 | -0.050 [-0.15, +0.00] 0/1/9 | -0.318 [-0.54, -0.10] 1/6/3 | -0.161 [-0.31, -0.03] 1/5/4 |
| bm25-id | -0.067 [-0.25, +0.10] 1/2/7 | -0.050 [-0.15, +0.00] 0/1/9 | -0.221 [-0.43, -0.02] 2/5/3 | -0.134 [-0.28, -0.00] 1/7/2 |
| bm25-id-title | -0.117 [-0.27, +0.00] 0/2/8 | -0.050 [-0.15, +0.00] 0/1/9 | -0.243 [-0.45, -0.05] 1/6/3 | -0.148 [-0.29, -0.01] 1/7/2 |

## Interpretation

On dev, fixed-size chunks rank the first relevant article lower than article chunks for all three BM25 variants: MRR drops by 0.20 to 0.25 and nDCG@10 by about 0.16, with every CI excluding 0 and fixed losing on 18 to 20 of 30 queries. Recall is a different picture. Only bm25-id loses recall@10 with a CI that excludes 0 (-0.107); the other recall@5 and recall@10 differences have CIs that include 0. So fixed chunks mostly still put the right articles somewhere in the top 10, but lower down. A likely cause, not tested here: a 1200-character window mixes the end of one article with the start of the next, which dilutes the BM25 match, and its overlap credit then goes to every article it touches, not only the one that matched. The test split points the same way on MRR and nDCG@10, but with 10 queries its CIs are wide and some upper bounds sit at 0, so it is not separate evidence. This supports keeping article chunks as the serving default (`search.strategy: article`); fixed chunks stay in the eval runs as the comparison, so the dense runs (T-16, T-17) get the same check. Limits: one fixed size and overlap was tested (no overlap sweep), the retriever is lexical only, and the labels are LLM-checked, not human-verified.
