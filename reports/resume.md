# Resume bullets and talking points (T-33)

Every number traces to a committed file; sources are listed under each bullet. Keep the qualifiers: the labels were drafted and checked by an LLM, not by a person (ADR-015), and the test split has 10 queries.

## Resume bullets

Pick 3 to 5. Short versions first, longer versions after.

1. **Built an evaluation-first retrieval benchmark** over Indonesian personal data protection law (4 regulations, 273 articles, 40 LLM-drafted queries with a frozen test split), comparing BM25, multilingual-e5 dense retrieval and hybrid fusion with bootstrap 95% confidence intervals and paired win/loss counts.
   - Source: `reports/results/20261023T074949Z-ed9dbfc.md`, `docs/decisions.md` (ADR-013, ADR-015).

2. **Raised ranking quality with hybrid retrieval**: nDCG@10 from 0.566 to 0.659 on dev (+0.093, 95% CI +0.01 to +0.19) and from 0.423 to 0.610 on the held-out test split, with hyperparameters tuned on dev only.
   - Source: `reports/results/20261023T074949Z-ed9dbfc.md` (hybrid/article vs bm25-basic/article), `reports/results/20261023T073543Z-a07f39f.md` (dev-only tuning grid).

3. **Shipped the search API to a serverless free tier** (FastAPI on Vercel) by running int8 ONNX embeddings without PyTorch; about 10 ms server-side retrieval at p50, with request IDs, structured logs, CORS, a non-root Docker image and a CI image smoke test.
   - Source: `reports/results/20261023T092147Z-25c0f58-remote.md` (server p50 9.9 ms), ADR-016, ADR-008, `.github/workflows/ci.yml`.

4. **Recovered article structure from scanned legal PDFs** with an OCR-tolerant, sequence-constrained segmenter: all 273 body articles across 4 documents, including headings garbled as "Pasa722" or "Pasal 6O", with no guessed markers.
   - Source: ADR-009 and ADR-010 (`docs/decisions.md`), ingest log (`make ingest`).

5. **Ran error analysis and reported null results honestly**: vocabulary mismatch caused 7 of the 10 worst failures; found a span bug affecting 76 of 273 articles, fixed it, and reported that the fix did not change dev metrics. A fresh clone reproduced all 480 per-query results exactly.
   - Source: `reports/error_analysis.md`, `reports/results/20261023T074949Z-ed9dbfc.vs-a0d608d.md`, `reports/results/20261023T080406Z-a67e1de.md`.

One-line version for a project list:

> IndoReg-RAG Eval: retrieval benchmark and live search API over Indonesian data protection law; hybrid BM25 + multilingual-e5 retrieval, nDCG@10 0.566 to 0.659 on dev with 95% CIs, served from Vercel with int8 ONNX.

## Talking points

**A decision: the model is chosen by where it has to run.** The published Indonesian results I found favoured BGE-M3, but PyTorch was blocked on my machine by Windows Application Control and is too large for Vercel's free tier (500 MB bundle, 2 GB memory). I moved dense retrieval to onnxruntime with the authors' int8 exports and benchmarked the exact file the API serves, so the reported numbers describe what is deployed. Cost: a smaller model, and an unmeasured int8 quality loss. (ADR-006, ADR-016)

**A failure: two improvements that were not.** The larger e5-base looked 0.10 nDCG@10 better than e5-small, but the 95% CI was -0.01 to +0.21, so I did not claim it and kept the smaller model that fits the deployment. Later, error analysis found that 76 of 273 article spans carried the next section's heading; I fixed it, expecting a gain, and the paired comparison showed none on dev and a small drop on test. I kept the fix as a data correction and reported the null result. (README, `reports/error_analysis.md`, ADR-017)

**A tradeoff: what to serve.** Hybrid beats the BM25 baseline with a CI excluding 0, but against the best BM25 variant the lower bound is +0.0003, effectively zero, with 16 wins and 3 losses. Hybrid costs about 18 ms per query and a 118 MB model, against about 5 ms and no model for BM25 (warm, local). I served hybrid because both latencies are invisible to a user and it wins far more queries than it loses, documented that the edge is borderline, and kept a one-line config fallback to BM25. (ADR-018, `reports/latency.md`)

**If asked about the labels.** The 40 queries and labels were drafted and checked by an LLM against the official PDFs, not verified by a person. That is the weakest part of the benchmark, and it is disclosed in the README and every results table. The next step would be a human spot-check of the test split. (ADR-014, ADR-015)
