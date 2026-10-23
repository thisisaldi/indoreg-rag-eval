# Portfolio brief: IndoReg-RAG Eval

Handoff for whoever adds this project to the portfolio site (https://naufaldi.vercel.app). It has the copy, the facts that must not change, and the API contract for a live search demo. Facts and numbers come from the repository; do not round them differently or add new ones.

## Links

- Repository: https://github.com/thisisaldi/indoreg-rag-eval
- Live API: https://indoreg-rag-eval.vercel.app (OpenAPI docs at `/docs`, health at `/health`)
- Case study: https://github.com/thisisaldi/indoreg-rag-eval/blob/main/reports/case_study.md
- Benchmark release: tag `v0.1-benchmark`

## Copy

**Title:** IndoReg-RAG Eval

**One-liner:** A retrieval benchmark and live search API for Indonesian personal data protection law: it finds the right article for a plain-language question and measures how often it gets it right.

**Short description (about 60 words):** Analysts search regulations by paraphrase, not by article number. I built a labeled benchmark over four Indonesian regulations (273 articles), compared keyword, embedding and hybrid retrieval with 95% confidence intervals, and deployed the best configuration as a cited search API on Vercel. Hybrid retrieval raised nDCG@10 from 0.566 to 0.659 on the dev set.

**Tags:** Python, FastAPI, information retrieval, BM25, multilingual-e5, ONNX Runtime, evaluation, bootstrap statistics, Docker, GitHub Actions, Vercel

**Key results (use these exact numbers):**

| What | Value | Note |
|---|---|---|
| nDCG@10, dev (30 queries) | 0.566 to 0.659 | BM25 baseline to hybrid; difference +0.093, 95% CI +0.01 to +0.19 |
| nDCG@10, test (10 queries) | 0.423 to 0.610 | frozen split, never used for tuning |
| Server retrieval latency | about 10 ms at p50 | measured on the live deployment |
| Corpus | 4 regulations, 273 articles | 2 of the 4 PDFs are scanned |
| Reproducibility | exact | fresh clone reproduced all 480 per-query results |

**Required caveats (must appear on the page, plain wording is fine):**
1. "Retrieval only. Not legal advice."
2. "The 40 test queries and their labels were drafted and checked by an AI model, not verified by a person."
3. "Small benchmark: 4 regulations, 40 queries; confidence intervals are wide."

Do not describe it as a chatbot, as legal advice, or as covering all Indonesian law. It returns articles; it does not generate answers.

## Live demo: API contract

`POST https://indoreg-rag-eval.vercel.app/search`

Request body (JSON):

```ts
type SearchRequest = {
  query: string;   // 1 to 500 characters after trimming; Indonesian works best
  top_k?: number;  // 1 to 20, default 5
};
```

Response (200):

```ts
type SearchHit = {
  rank: number;
  score: number;            // fusion score, only meaningful for ordering
  text: string;             // article text from the PDF text layer; may contain OCR errors
  doc_id: string;           // e.g. "uu-27-2022"
  title: string;            // e.g. "Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi"
  article: string | null;   // article (Pasal) number
  articles: string[];
  doc_status: "in_force" | "amended" | "revoked" | "unknown" | null;
  source_url: string | null; // official page on peraturan.bpk.go.id
};

type SearchResponse = {
  request_id: string;
  query: string;
  retriever: string;        // "hybrid"
  results: SearchHit[];
  latency_ms: number;       // server-side retrieval time
  disclaimer: string;       // show this to the user
};
```

Errors:
- 422: invalid input (empty or whitespace query, over 500 characters, `top_k` out of range). Body follows FastAPI's `{"detail": [{"loc": [...], "msg": "..."}]}`.
- 500: `{"detail": "internal server error", "request_id": "..."}`.

CORS: only `https://naufaldi.vercel.app` is allowed. Calls from `localhost` or preview URLs are blocked by the browser. To allow another origin, add it to `search.cors_origins` in `configs/default.yaml` in the API repository and redeploy; do not proxy around it.

Cold start: the API runs on Vercel's free tier. The first request after a quiet period can take several seconds; later requests take well under a second. Show a loading state and use a timeout of about 20 seconds.

Example (browser, TypeScript):

```ts
const API = "https://indoreg-rag-eval.vercel.app";

export async function searchRegulations(query: string, topK = 5): Promise<SearchResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20_000);
  try {
    const res = await fetch(`${API}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query.trim(), top_k: topK }),
      signal: controller.signal,
    });
    if (res.status === 422) throw new Error("Please enter a question of 1 to 500 characters.");
    if (!res.ok) throw new Error("Search is unavailable right now. Please try again.");
    return (await res.json()) as SearchResponse;
  } finally {
    clearTimeout(timer);
  }
}
```

## Demo UI guidance

- One text input with a submit button, plus 3 clickable example queries. Each was checked on the live API on 23 Oct 2026 and returns the answering article first (UU 27/2022 Pasal 4, Pasal 46 and Pasal 8):
  - "Apakah data biometrik termasuk data pribadi yang bersifat spesifik?"
  - "Berapa lama batas waktu pemberitahuan kebocoran data pribadi?"
  - "Hak untuk menghapus data pribadi"
- Results are not always this good: questions in everyday wording that the law phrases differently are the weak spot (see the case study). Do not pick examples that make it look better than it is.
- For each result show: rank, the regulation title, "Pasal {article}", a status badge from `doc_status` (in force / amended / revoked / unknown), the first 300 or so characters of `text` with an expand option, and a "View source" link to `source_url` (open in a new tab, `rel="noopener noreferrer"`).
- Render `text` as plain text, never as HTML. Keep its line breaks (`white-space: pre-line`).
- Always show the response's `disclaimer` near the results.
- States: idle, loading (with a note that the first search can take a few seconds), results, no results, error with retry.
- Accessibility: label the input, make example queries real buttons, announce results with `aria-live="polite"`, keep keyboard focus visible.
- Do not log or store users' queries on the portfolio side.

## Suggested page structure

1. Title, one-liner, links (repository, case study, live API docs).
2. The problem in two sentences.
3. Live demo (above).
4. Results table (key results above) with the caveats.
5. How it works: ingestion of official PDFs, OCR-tolerant article segmentation, BM25 + multilingual-e5 hybrid retrieval, evaluation with bootstrap confidence intervals, FastAPI on Vercel with int8 ONNX. The architecture diagram (Mermaid) is in `reports/architecture.md` if the site can render it.
6. What I learned (from the case study's "Lessons"): confidence intervals changed decisions; error analysis found a real data bug even though fixing it did not move the metric; deployment limits shaped the model choice; the labels are the weakest part.
