# Latency and cost (T-27)

Sources: `reports/results/20261023T084412Z-2c4861a-latency.md` (run 1) and `reports/results/20261023T084535Z-f50375f-latency.md` (run 2), written by `scripts/latency_bench.py`. Both runs used the same code; the commit between them only added run 1's result files. Retrieval-only latency per query is in the eval result files (for example `reports/results/20261023T074949Z-ed9dbfc.md`, p50 and p95 columns).

## Method

- Machine: Windows 11 laptop, 12 logical CPUs, 7.7 GB RAM (heavily used by other programs during the runs), Python 3.12.14, onnxruntime 1.31.0, CPU only. Docker Desktop was stopped for both runs.
- Each retriever runs in a fresh Python process. **Cold** is process start to the first response: imports, loading the chunks, loading the ONNX model and the embedding cache from disk, and the first request. The embedding cache already exists, as it does in the Docker image (ADR-008).
- **Warm** sends the 40 dataset queries 5 times (200 requests) through the FastAPI app in-process with Starlette's TestClient. That includes request validation, retrieval and JSON serialisation, but no network socket. The first 10 requests are discarded. p50 and p95 are nearest-rank percentiles.
- Article chunks (273), `top_k` 5 (the API default).

## Results

| retriever | cold total ms (run 1 / run 2) | warm p50 ms | warm p95 ms | warm max ms |
|---|---|---|---|---|
| bm25-basic | 1392 / 978 | 5.16 / 5.72 | 9.73 / 16.31 | 13.84 / 35.01 |
| bm25-id-title | 1014 / 704 | 4.66 / 4.43 | 7.61 / 12.41 | 10.60 / 18.15 |
| dense-e5-small | 3042 / 3118 | 17.01 / 16.38 | 26.10 / 23.68 | 52.92 / 39.46 |
| dense-e5-base | 3822 / 3865 | 29.89 / 25.48 | 60.26 / 37.76 | 104.10 / 106.78 |
| hybrid (bm25-id-title + dense-e5-small) | 3660 / 3030 | 18.97 / 18.09 | 32.89 / 26.17 | 60.96 / 61.19 |

Reading:
- Warm p50 is fairly stable between runs (within 4.5 ms); p95 and max are not (bm25-basic p95 9.73 vs 16.31 ms). This laptop is a noisy environment, so treat p95 as a rough indication.
- BM25 retrieval itself takes well under 1 ms (dev p50 0.45 ms for bm25-basic and 0.34 ms for bm25-id-title in the eval file), so most of BM25's 4 to 6 ms warm time is request handling. Over BM25, dense-e5-small and hybrid add about 11 to 14 ms per query at p50, which is mostly embedding the query with the ONNX model (not profiled separately); e5-base adds about 20 to 25 ms.
- Cold start is about 1 s for BM25 and about 3 to 4 s with a model, mostly model loading.
- Not measured: the Docker container over a real socket, Vercel (cold starts there also include fetching and unpacking the function bundle; T-35), and network latency to a client.

## Cost (NFR8)

- Cash cost so far: none. Everything ran on Aldi's laptop; models were downloaded from the Hugging Face Hub without charge; no paid API was used. The planned Vercel Hobby deployment (ADR-016) is a free plan.
- Estimated compute, from measured times: embedding all 273 article chunks once takes 35.0 s with e5-small and 60.4 s with e5-base on this laptop (`reports/results/20261023T073208Z-cfff220.md`, cold build). Serving needs about 17 to 19 ms of CPU per dense or hybrid query (warm p50 above). No dollar estimate is given; it would depend on a hosting price not chosen here.
