# Decision Log (ADR)

Format: one entry per decision. Status is Accepted, Proposed, or Superseded. Add new entries at the bottom.

## ADR-001: Single repository, minimal infrastructure
- Status: Accepted (22 Oct 2026)
- Context: 14-day window, about 27 hours. Reviewers value measured results over architecture size.
- Decision: One repo. Local files and a numpy index. No vector DB server, Postgres, Kubernetes, frontend, or LLM API in v0.1.
- Consequences: Faster delivery and easier reproduction. Revisit only if a measured problem requires more.

## ADR-002: Article-level labels, chunk-independent evaluation
- Status: Accepted (22 Oct 2026)
- Context: Chunking is an experimental variable. Chunk-level labels would change with every chunking strategy and make the ablation unfair.
- Decision: Label (doc_id, article) with a grade. Map retrieved chunks to article units via the span table. Deduplicate by article, keep best rank.
- Consequences: Fair comparison across chunkers. Requires reliable article span detection (DI1). Supersedes "chunk or article" wording in FR-EVAL-1 and T-10: label articles only.

## ADR-003: Brute-force dense index with disk cache
- Status: Accepted (22 Oct 2026)
- Context: Expected corpus under 10k chunks.
- Decision: Numpy cosine search. Embeddings cached under `data/cache/`, keyed by model name and chunk file hash.
- Consequences: No index dependency, easy determinism. Revisit if p95 latency exceeds the target in T-27.

## ADR-004: Frozen test split
- Status: Accepted (22 Oct 2026)
- Context: Tuning on all 40 queries would inflate reported results.
- Decision: About 30 dev and about 10 test, stratified by query type, frozen at T-11 with tag `dataset-v1`. Tuning uses dev only. Label fixes after freezing require a version bump and a changelog line.
- Consequences: Smaller dev set, more honest reporting.

## ADR-005: PDF extractor
- Status: Accepted (22 Oct 2026)
- Context: T-04 planned a comparison of pdfplumber and PyMuPDF. PyMuPDF cannot be imported on the development machine: its native library is blocked by an application control policy ("DLL load failed while importing _mupdf", source: scratch/extraction_report.md). Only pdfplumber ran.
- Decision: pdfplumber.
- Consequences: No cross-extractor comparison was run, so T-04's "try 2 extractors" is not satisfied. For the two image-based documents (ADR-009) the result depends on the text layer already in the PDF. Revisit if another extractor can be run (for example on another machine or in CI).

## ADR-006: Embedding models
- Status: Accepted (23 Oct 2026; model 1 in T-16, model 2 and the hybrid member in T-17).
- Context: No Indonesian-specific embedding leaderboard was found (searched 23 Oct 2026). The closest evidence is the Indonesian column of MIRACL dev nDCG@10 in the BGE-M3 paper (arXiv 2402.03216, Table 1, read through a fetched summary, not checked against the PDF): BM25 29.7, mE5-large 52.9, BGE-M3 dense 56.1. MMTEB (arXiv 2502.13595) reports multilingual-e5-large-instruct as the best public model overall, not per language. The served model must also fit a Vercel Hobby function (ADR-016), which rules out torch and BGE-M3 (about 2.3 GB of weights against a 2 GB memory cap).
- Decision: Model 1 is `intfloat/multilingual-e5-small`, the authors' int8 ONNX export (`onnx/model_qint8_avx512_vnni.onnx`, 118 MB), revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, prefixes "query: " and "passage: ", mean pooling, max 512 tokens. The eval measures this exact int8 file, the one that would be served. Model 2 candidates for T-17: `multilingual-e5-base` int8 (279 MB, bundle fit to be measured); BGE-M3 only as an eval-only reference marked not deployable, if it can run on the dev machine at all.
- Consequences: 512 tokens truncate the longest articles (9 article chunks exceed 2000 characters); check them in error analysis (T-21). int8 may cost quality against the full-precision model; that cost is not measured. First result: `reports/results/20261023T072143Z-28cc2a8`.
- Model 2 (T-17): `intfloat/multilingual-e5-base`, int8 ONNX `onnx/model_qint8_avx512_vnni.onnx` (279 MB), revision `d128750597153bb5987e10b1c3493a34e5a4502a`, same prefixes and pooling. BGE-M3 was not run (memory, ADR-016).
- Hybrid member (T-18), chosen on dev from `reports/results/20261023T073208Z-cfff220`: e5-base vs e5-small on article chunks shows no established difference (nDCG@10 +0.042 [-0.06, +0.15], 11/10/9; MRR +0.059 [-0.04, +0.18]), while e5-base has a 2.4x larger model file (279 vs 118 MB), a slower dev p50 (15.11 vs 8.79 ms) and a cold article-chunk embedding time of 60.4 s vs 35.0 s. T-18 fuses BM25 with e5-small. Revisit if a larger dev set or label fixes (T-21) separate the two models.

## ADR-007: BM25 library and Indonesian preprocessing
- Status: Accepted (23 Oct 2026, T-13)
- Context: Candidates were rank_bm25, bm25s, or a stdlib implementation; basic tokenizer vs stopwords plus light stemming. The corpus is 273 article chunks (188 fixed chunks), so scoring every chunk per query takes well under a millisecond.
- Decision: Stdlib Okapi BM25 (`retrieval/bm25.py`, k1 1.5, b 0.75 from config), no new dependency. Three configured variants: `bm25-basic` (lowercase word tokens), `bm25-id` (Indonesian function words removed, enclitic -nya and particle -kah stripped when at least 4 letters remain), `bm25-id-title` (as bm25-id, with the document title indexed with each chunk, to let queries that name the law match it). No stemmer library (DI3): affix stripping on legal terms such as "pengendali" or "pemrosesan" risks merging distinct concepts, and Sastrawi would be a new dependency without a measured need.
- Consequences: Variant choice is made on the dev split only, by nDCG@10 with bootstrap CIs (T-19); the test split is reported but not used to choose. A library can replace the implementation later if a measured latency problem appears.

## ADR-008: Image contents (baked vs mounted model and index)
- Status: Accepted (23 Oct 2026, T-26, Aldi chose baked)
- Criteria: Image size, cold-start latency, reproducibility.
- Decision: Bake everything the configured serving retriever needs. The build copies `data/chunks/` (not the PDFs), runs `build_index` once, which downloads the model at its pinned revision into `HF_HOME` and fills the embedding cache, and the runtime sets `HF_HUB_OFFLINE=1`. Two-stage build on `python:3.12.12-slim-bookworm` with uv 0.13.5, non-root user. `--build-arg CONFIG=configs/<file>.yaml` selects another config.
- Consequences: `docker run` needs no network or mounts (checked: the hybrid image builds its index and searches with `--network none`). Image sizes on 23 Oct 2026: 546 MB for the default config (bm25-basic) and 767 MB with `hybrid` as the serving retriever; the image must be rebuilt after `make ingest` or a config change. The build needs `data/chunks/`, which is generated locally and gitignored, so CI (T-28) must produce it first.

## ADR-009: Topic
- Status: Accepted (22 Oct 2026)
- Context: T-01 feasibility check. Four official regulations were downloaded by hand into data/raw/ (not committed) and probed with pdfplumber.
- Decision: Personal data protection, widened to electronic systems and transactions. Core document: UU 27/2022. Documents probed: UU 27/2022, PP 71/2019, Permen Kominfo 20/2016, UU 11/2008.
- Text type: Permen Kominfo 20/2016 and UU 11/2008 are native text (embedded fonts, only small images). UU 27/2022 and PP 71/2019 are image-based pages (one full-page image per page) with a text layer in a single generic font; the text layer contains character errors, and whether it came from OCR software is not confirmed (source: scratch/extraction_report.md, image layer findings).
- Segmentation results from the spike (source: scratch/segmentation_v2_report.md, "Coverage before and after", after column; page counts from scratch/extraction_report.md). Not verified against page images:

| Document | Pages | Text type | Articles accepted | N | Missing 1..N | Repair-log entries |
|---|---|---|---|---|---|---|
| UU 27/2022 | 50 | image-based | 76 | 76 | none | 6 |
| PP 71/2019 | 90 | image-based | 104 | 104 | none | 15 |
| Permen Kominfo 20/2016 | 24 | native | 39 | 39 | none | 0 |
| UU 11/2008 | 38 | native | 54 | 54 | none | 0 |

- Consequences: Page-image verification (Tier 1) by Aldi: SKIPPED by Aldi on 23 Oct 2026. Instead, Claude checked the 39 labeled articles of the two image-based documents against their rendered page images (31 pages, `eval/drafts/CHECK_NOTES.md`); the segmentation of the other articles, and the span ends, were not compared with page images by anyone. The two native documents need no repairs; the two image-based ones depend on ADR-010. The requirements assumption of at least 10 text-extractable regulations is not yet tested beyond these four.

## ADR-010: OCR-tolerant article segmentation
- Status: Accepted (22 Oct 2026)
- Context: A strict "Pasal N on its own line" matcher left gaps in both image-based documents because headings are garbled in the text layer (for example "Pasal 6O", "Pasal T2", "Pasa722", or the number on the line before the word "Pasal"), and page stamps and bottom-of-page catchwords sit inside the text (source: scratch/extraction_report.md, "Missing article diagnosis").
- Decision: Segment articles with a sequence-constrained marker decoder. The spike code lives in scratch/ (not committed) and is to be re-implemented under src/indoreg/ingest/ in T-06 and T-07.
  1. Noise filter removes only SK stamp lines, page-bottom catchwords (lines ending in ". ." or ". . ."), and header or footer lines repeated on more than half of the pages (first 6 and last 3 lines of a page).
  2. Candidates: fuzzy "Pasal" (edit distance up to 2) followed by a number token. Confusable characters O to 0, l and I to 1, T to 7, S to 5, B to 8 are allowed in the number, as are an inner space, a leading period, a number on the previous or next line, and a confusable character inside the word itself (glued form such as "Pasa722").
  3. Decoding: clean-digit headings are anchors (longest increasing subsequence, later occurrence wins ties). A confusable reading is accepted only when it equals the expected next number or suffix. gap_fill accepts a single unclaimed heading-like candidate between neighbours N-1 and N+1.
  4. Coverage gate per document: N, missing numbers, duplicates, unresolved candidates.
- Unresolved markers stay unresolved and are never guessed.
- Methods are labeled confusion, catchword_swap (the swap rule; called reversed_swap in the spike report), tiebreak_later and gap_fill, and logged per document. Counts from scratch/segmentation_v2_report.md: PP 71/2019 confusion 12, catchword_swap 1, tiebreak_later 2, gap_fill 0; UU 27/2022 confusion 5, tiebreak_later 1, gap_fill 0; Permen Kominfo 20/2016 and UU 11/2008 no entries.
- Consequences: The rules were developed on the same 4 files, so the coverage numbers are in-sample. Out-of-sample coverage must be measured on documents added later. text_quality (native or image_text_layer; "image_text_layer" because OCR origin is not confirmed, see ADR-009) is recorded per document in data/manifest.json; design.md 3.1 and FR-ING-2 do not list that field yet. Segmentation correctness is not verified against page images (see ADR-009).

## ADR-011: Pasal.id API as metadata source only
- Status: Accepted (22 Oct 2026)
- Context: Pasal.id has a token-gated REST API. A probe on 22 Oct 2026 (6 requests, source: scratch/feasibility_report.md) returned metadata (title, number, year, status, verification tier, source_url) and `"content": "not_available_via_api"` for search and for the law detail; the detail had no article nodes. The response note says the text is available on the website or through MCP.
- Decision: Use the API at most to cross-check status and source_url when filling the manifest (T-03). Article text comes from the official PDFs. No scraping of pasal.id pages and no MCP.
- Consequences: Each manifest status still needs its own source note (FR-ING-2). No terms or license field appeared in the API responses; terms were not verified.

## ADR-012: Penjelasan excluded from v0.1
- Status: Accepted (22 Oct 2026)
- Context: UU 11/2008, PP 71/2019 and UU 27/2022 contain a Penjelasan section after the body that repeats article numbers (mostly "Cukup jelas."). Its heading is on page 26, 58 and 35 respectively; Permen Kominfo 20/2016 has none (source: scratch/extraction_report.md).
- Decision: Index and label body articles only. The body ends at the Penjelasan boundary found by OCR-tolerant signals (heading garbled up to a few characters, "PASAL DEMI PASAL", numbering restart).
- Consequences: Explanatory text is not searchable and queries answered only by a Penjelasan cannot be satisfied. State this in the README limitations. Revisit if error analysis shows many such misses.

## ADR-013: Four-document corpus for v0.1
- Status: Accepted (22 Oct 2026)
- Context: T-03 asks for 10 to 15 regulations and the requirements assume at least 10 text-extractable ones. Four are in hand (ADR-009); together they hold 273 body articles by the segmentation spike (76 + 104 + 39 + 54, source: scratch/segmentation_v2_report.md, not verified against page images).
- Decision: Build v0.1 on these 4 documents. Add more only if labeling (T-09 to T-11) or error analysis (T-21) shows a coverage gap, and measure segmentation coverage on any added document separately (ADR-010).
- Consequences: T-03's "10 to 15" sub-task stays open by decision, not by omission. Results describe a 4-document corpus; the README and case study must say so. The requirements assumption "at least 10 text-extractable regulations" is not met.
- See also ADR-014 and ADR-015 for how the labels are produced.

## ADR-014: LLM-drafted, author-verified labels
- Status: Superseded by ADR-015 for the verification step (22 Oct 2026); the drafting rules still apply. Originally accepted 22 Oct 2026. Supersedes the "do not use an LLM to propose labels" rule in eval/LABELING.md and the "not LLM-generated" wording in T-10.
- Context: Writing and labeling 40 queries from scratch takes about 3.5 hours of the author's time, the largest remaining cost in the plan.
- Decision: Claude drafts the 40 queries and candidate labels in `eval/drafts/` (never in `eval/dataset.jsonl`), by reading the regulation text, not by running any retriever in this repo, with the PDF page for each label. Aldi checks every label of every query against the PDF page and edits, removes or adds labels. Only verified queries are copied into `eval/dataset.jsonl`, with `source_note` saying "drafted by Claude, verified by Aldi". Claude does not edit `eval/dataset.jsonl`.
- Consequences: The README and case study must disclose that queries and labels were LLM-drafted and author-verified. Drafts were written by a model that also read the extracted (OCR) text, so wording may lean towards that text; the near-copy rule still applies and is checked during verification. Label completeness (missed relevant articles) depends on the verification step; any article added by Aldi during verification is noted in `source_note`.

## ADR-015: LLM-checked labels without human verification
- Status: Accepted (22 Oct 2026), at Aldi's explicit request; CLAUDE.md hard rule 1 amended by Aldi. Supersedes the verification step of ADR-014.
- Context: Aldi asked Claude to do the label verification itself instead of checking every label by hand.
- Decision: Claude checks every drafted label against the PDF (rendered page images for the two scanned documents, embedded text for the two native ones), records the check in `eval/drafts/CHECK_NOTES.md`, and writes `eval/dataset.jsonl` from the checked drafts with a seeded, type-stratified dev/test split (T-11). The file is then frozen (tag `dataset-v1`); after that, Claude does not edit labels or the test split.
- Consequences: Labels are drafted and checked by the same model: a self-check, not independent verification. Everything that reports results (README, case study, result tables) must say "labels drafted and checked by an LLM, not human-verified". Label errors found later (for example in error analysis, T-21) are fixed with a version bump and a changelog line (ADR-004). A human spot-check of the test split is recommended before any public claim.

## ADR-016: Vercel Hobby deployment target, ONNX instead of torch
- Status: Accepted (23 Oct 2026), at Aldi's request: the API will be deployed on Vercel's free tier and called from Aldi's portfolio site.
- Context: Vercel Hobby Python functions are limited to 500 MB uncompressed bundle and 2 GB memory (vercel.com/docs/functions/limitations, read 23 Oct 2026; a 5 GB bundle beta exists but Hobby eligibility is unconfirmed). CPU torch alone takes most of that bundle. Torch is also blocked by Windows Application Control on the dev machine (WinError 4551 loading torch_python.dll), while onnxruntime loads.
- Decision: Dense models run with onnxruntime, tokenizers and huggingface-hub (base dependencies; no torch, no sentence-transformers). Model files come from the Hugging Face Hub at a pinned revision. The eval and the API use the same encoder (`retrieval/dense.py`). The served retriever is chosen on dev results; if dense or hybrid does not beat BM25 with a CI excluding 0, BM25 is served. The Docker image (T-26) stays for local reproduction (BR6); Vercel deployment is a separate task (T-35).
- Consequences: Model choice is limited to models with an ONNX export that fits the bundle. Bundle size, cold-start latency and CPU architecture on Vercel are not measured yet (T-35). Replaces "Sentence Transformers" as the library named in FR-RET-2; the models are still sentence-embedding models.

## ADR-017: Section headings are not part of any article span
- Status: Accepted (23 Oct 2026, T-36)
- Context: T-21 found that 76 of 273 article spans ended with the heading and title of the next BAB, Bagian or Paragraf (for example UU 27/2022 Pasal 55 ending in "Bagian Kedua Transfer Data Pribadi ke Luar Wilayah Hukum Negara Republik Indonesia"), so an article could match queries about the section after it.
- Decision: An article span ends at the first whole-line heading after its Pasal marker (`SECTION` in `ingest/articles.py`: "BAB <roman>", bare "BAB", "Bagian Ke...", including the OCR form "Baqian", and "Paragraf <n>"). The heading and its title lines belong to no article; the chapter stays recorded per span (design.md 3.2). Section titles are not added to the next article (possible later experiment).
- Consequences: Same 273 articles; 0 spans contain a heading. Measured in `reports/results/20261023T074949Z-ed9dbfc.vs-a0d608d.md`: on dev no configuration changes with a CI excluding 0 (hybrid/article nDCG@10 -0.002 [-0.03, +0.02], 6/5/19). On test, hybrid/article nDCG@10 drops by 0.022 [-0.049, -0.004] (0/3/7); the test split is reported, not used to decide. The fix is kept because it is a data correction and is neutral on dev.

## ADR-018: Serve the hybrid retriever
- Status: Accepted (23 Oct 2026, Aldi)
- Context: ADR-016 serves BM25 unless dense or hybrid beats BM25 with a CI excluding 0. On dev (`reports/results/20261023T074949Z-ed9dbfc`), hybrid/article beats bm25-basic/article on nDCG@10 (+0.093 [+0.01, +0.19]) and beats the stronger bm25-id-title/article by +0.078 [+0.0003, +0.151] (16/3/11), a lower bound only just above 0. Warm p50 serving latency is about 18 ms for hybrid vs about 5 ms for bm25-id-title (`reports/latency.md`), both well below what a user notices.
- Decision: `search.retriever: hybrid` (RRF over bm25-id-title and dense-e5-small, k 60, depth 50) on article chunks.
- Consequences: The served index needs the e5-small ONNX model (118 MB) and its embedding cache, which the Docker image bakes in (ADR-008). If the Vercel bundle, memory or cold start measured in T-35 do not fit the Hobby limits, switch to `bm25-id-title`, a config-only change, and record it here. The CI image keeps serving BM25 from the fixture corpus (`configs/ci-image.yaml`).

## ADR-019: Commit the article chunks; plain-file model directory
- Status: Accepted (23 Oct 2026, Aldi chose this option for T-35)
- Context: Vercel builds the API from the Git repository, but the searchable text (`data/chunks/article.jsonl`) is derived from the PDFs and was gitignored, and a build step must not download the PDFs automatically while the source's terms are unchecked (CLAUDE.md rule 6). The alternative, deploying from Aldi's laptop with the Vercel CLI, would give up deploy-on-push.
- Decision: Commit `data/chunks/article.jsonl` (290 KB: the body articles of the 4 regulations as extracted, with document ID, title, article number, status and source URL). The PDFs, processed text and fixed-size chunks stay out of Git. Model files are downloaded into `paths.models` (`data/models/<repo>@<revision>/`) as plain files instead of the Hugging Face cache, which uses symlinks that a bundler may not keep. The Vercel build step (`scripts/vercel_build.py`) builds the serving index once, so the model and the embedding cache ship inside the function and it runs with `HF_HUB_OFFLINE=1`.
- Consequences: The repository now redistributes the extracted text of public Indonesian statutes. Claude's understanding is that Indonesian copyright law (UU 28/2014, Pasal 42) gives no copyright protection to statutes and regulations; this was not checked by a lawyer, and the terms of peraturan.bpk.go.id were not checked. The text carries OCR errors from two image-based PDFs and is not an authoritative copy. `article.jsonl` must be regenerated and committed whenever ingestion changes. Embedding cache keys are unchanged, so existing result files stay valid.

## ADR-020: Big-corpus stress test from an external article dump
- Status: Accepted (24 Oct 2026, Aldi approved the dataset and the national-level subset; T-37)
- Context: Aldi asked to use all Indonesian regulations. No source offers full text through an API: the Pasal.id API returns metadata only (ADR-011; bulk text needs a written agreement), peraturan.go.id has no API or bulk export, and peraturan.bpk.go.id was down for maintenance when checked (24 Oct 2026). Aldi approved the Hugging Face dump `Azzindani/ID_REG_DB_2511` (CC-BY-4.0, revision d53cafcef612b5ad563c6f36d2a237e8aad95a38, `id_regulations.db`, 11,008,479,232 bytes, sha256 6c9c314b...2fd08). Profiled on 24 Oct 2026: 748,558 article-level rows from about 44k regulations; coverage effectively ends in 2017 (13 regulations from 2018, almost none later), so UU 27/2022, PP 71/2019 and UU 1/2024 are absent; about 70% of rows are regional regulations; the provenance and extraction method are undocumented; there is no status and no per-document URL; metadata has OCR and parsing errors (`NOMOR I1 TAHUN 2OO8`, numbers recorded as "TAHUN"); 3,615 rows are cut at 32,767 characters. e5-small embeds about 19 chunks/s on the development laptop, so all rows would take about 11 hours.
- Decision: Add only national-level body articles (UU, UUD, Perpu, PP, Perpres, Keppres, Inpres, Permen; rows whose article is "Pasal N", at least 30 characters) to the 4 PDF documents as a separate corpus, `configs/full.yaml` (`make ingest-full`, `make eval-full`): 95,173 chunks from 7,727 documents plus the 273 PDF articles. Dump documents that are in the manifest are skipped (UU 11/2008), so the labeled text stays the PDF text. External chunks carry `doc_status: "unknown"` and the pinned dataset URL (rule 8). The default corpus, the frozen labels, the deployed API and the Docker image are unchanged; the big corpus is local only (about 150 MB of embeddings and a 100 MB chunk file do not fit Vercel Hobby).
- Consequences: The big corpus measures robustness to distractors, not coverage of current law; it adds no regulation newer than 2017. Labels cover only the 4 PDF documents, so a relevant article from the dump (for example UU 19/2016 Pasal 26, which amends the labeled UU 11/2008 Pasal 26) counts as a miss. Result `reports/results/20261024T094427Z-5415577` (git 5415577; the working tree differed only in the Makefile and a line-ending change, which do not affect results) against the 4-doc run `20261023T074949Z-ed9dbfc`: every retriever drops, for example dev hybrid/article nDCG@10 -0.174 [-0.28, -0.07] (4/16/10) and dev bm25-id-title/article -0.183 [-0.30, -0.08] (`...5415577.vs-ed9dbfc.md`). In the 21 queries where hybrid got worse, dump chunks took 127 top-10 slots: 1 is a near-duplicate of a labeled article (word Jaccard at least 0.5: PP 82/2012 Pasal 53, the repealed predecessor of PP 71/2019 Pasal 59), 8 are similar (0.3 to 0.5), 118 are unrelated (`...5415577.displacement.txt`; a word-overlap heuristic, not a relevance judgment). Most of the drop is therefore distractor competition, not missing labels; exact-reference queries suffer most because every regulation has a "Pasal 17". BM25 now uses an inverted index with compact postings and dense encoding is resumable and length-sorted; rankings on the 4-doc corpus are unchanged (checked against the previous BM25 on all 40 queries).

---

## Template

```
## ADR-XXX: Title
- Status:
- Context:
- Decision:
- Consequences:
```
