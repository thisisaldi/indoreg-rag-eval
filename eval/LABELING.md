# Labeling guideline (v1)

Status: DRAFT by Claude for Aldi's review (T-09). Approve or edit before labeling starts (T-10). The labels themselves are written and verified by Aldi only.

## 1. Purpose

Each query in `eval/dataset.jsonl` states one information need of the persona (a compliance analyst who searches by paraphrase and needs the exact article and its source) and lists the articles that answer it. These labels are the ground truth for every metric (Recall@k, MRR, nDCG@10), so they must not depend on any retriever in this repo.

## 2. Unit of relevance

- A label is an **article**: `(doc_id, article)`, for example `("uu-27-2022", "56")` (ADR-002, design.md 4.1). Not a chunk, not a page.
- Only **body** articles count. The Penjelasan is not indexed and cannot be labeled (ADR-012).
- Relevance is judged at article level even when one ayat answers the question. Note the ayat in `source_note` (open item DI2).
- `doc_id` values come from `data/manifest.json`: `uu-27-2022`, `pp-71-2019`, `permen-kominfo-20-2016`, `uu-11-2008`. `article` is a string as printed (`"56"`, or `"5A"` if a suffixed article ever appears).

## 3. Grades

| Grade | Meaning | Typical case |
|---|---|---|
| 2 | Directly answers the question | The obligation, right, prohibition, deadline or sanction asked about |
| 1 | Partially relevant or needed to understand the answer | The prohibition a sanction article refers to; a definition the answer depends on; the general rule when the question is about its exception |
| (not listed) | Not relevant | Same topic but a different question (e.g. domestic transfer for a question about transfer abroad) |

Rules:
1. Every query has at least one grade-2 article.
2. If the answer needs two articles together (for example "what is the obligation and what is the penalty"), both are grade 2.
3. If the same rule is stated in two documents (an Undang-Undang and its implementing regulation), label both; grade each by how directly it answers.
4. Keep at most 5 labeled articles per query. If more seem relevant, the query is too broad: rewrite it.
5. Label by the text as written in the corpus, regardless of amendment status. If you know a provision was amended or revoked, say so in `source_note`; do not drop the label.

## 4. How to find the relevant articles (avoid labeling bias)

1. Write the query first, from the persona's point of view, before looking anything up.
2. Find the answer by reading the regulation itself: the BAB and Bagian headings, then the articles, in the PDF. **Do not use `make search` or any retriever in this repo to find labels**: labels found that way favour that retriever and inflate its score.
3. Verify every label against the official PDF page, not the extracted text (the two image-based documents contain OCR errors). Record the PDF page in `source_note`.
4. Optional, after labeling a query: run `make search` to look for articles you missed. Any article added this way must be marked `found_via_search` in `source_note`, so the bias can be counted later.
5. Do not use an LLM to propose labels.

## 5. Query types and mix (FR-EVAL-2)

| Type | Target share | Count in 40 | Definition |
|---|---|---|---|
| `exact_ref` | about 25% | 10 | Names the article or regulation number explicitly |
| `paraphrase` | about 40% | 16 | Same meaning as the article, in the analyst's own words |
| `terminology` | about 25% | 10 | Uses different terms than the article (colloquial, synonym, newer or older wording) |
| `mixed_id_en` | about 10% | 4 | Indonesian mixed with English terms common in compliance work |

**Near-copy rule:** at most 1 in 4 queries may be a near copy of passage text. A query is a near copy if it shares a run of 5 or more consecutive words with the article. Fixed legal terms such as "Data Pribadi" count as words.

Suggested spread across documents (not a hard rule): about 20 queries on UU 27/2022, 8 on PP 71/2019, 6 on UU 11/2008, 6 on Permen Kominfo 20/2016, with a few queries whose answer spans two documents.

## 6. Writing rules

- One information need per query. 4 to 25 words. Indonesian, except `mixed_id_en`.
- Write how a real analyst would ask, including informal wording. No article numbers except in `exact_ref`.
- Avoid questions whose answer lies only in the Penjelasan or only in a Lampiran.
- Do not write queries by copying a sentence and changing one word (that is a near copy).

## 7. Examples (illustrative only)

These are examples of the format and grading, drafted from the extracted text. They are **not** dataset entries and their grades are a draft judgment: verify against the PDF before reusing any of them.

| Type | Query | Labels (doc_id, article, grade) | Why |
|---|---|---|---|
| exact_ref | Apa isi Pasal 46 UU PDP? | (uu-27-2022, 46, 2) | Names the article |
| exact_ref | Pasal 11 UU ITE tentang tanda tangan elektronik | (uu-11-2008, 11, 2) | Names article and law |
| paraphrase | Bolehkah perusahaan mengirim data pelanggan ke server di luar negeri? | (uu-27-2022, 56, 2) | Pasal 56 covers transfer outside Indonesia. Pasal 55 (transfer within Indonesia) is not labeled |
| paraphrase | Apa hukumannya kalau seseorang memalsukan data pribadi orang lain? | (uu-27-2022, 68, 2), (uu-27-2022, 66, 1) | 68 is the sanction; 66 is the prohibition it refers to |
| terminology | Izin dari pemilik data harus tertulis atau boleh lewat rekaman? | (uu-27-2022, 22, 2) | "izin" and "pemilik data" vs "persetujuan" and "Subjek Data Pribadi" |
| terminology | Apakah tanda tangan digital diakui secara hukum? | (uu-11-2008, 11, 2), (pp-71-2019, 59, 2) | "digital" vs "elektronik"; the same rule is restated in the implementing PP |
| mixed_id_en | Data breach notification wajib dalam berapa jam? | (uu-27-2022, 46, 2) | "data breach" vs "kegagalan Pelindungan Data Pribadi" |
| mixed_id_en | Right to erasure: kapan pengendali wajib menghapus data pribadi? | (uu-27-2022, 43, 2), (uu-27-2022, 8, 1) | 43 lists when deletion is mandatory; 8 is the data subject's right |

## 8. Record format (design.md 3.4)

One JSON object per line in `eval/dataset.jsonl`:

```json
{"query_id": "q-001", "query": "Bolehkah perusahaan mengirim data pelanggan ke server di luar negeri?", "type": "paraphrase", "split": "dev", "relevant": [{"doc_id": "uu-27-2022", "article": "56", "grade": 2}], "source_note": "UU 27/2022 PDF p24, Pasal 56 ayat (1); found by reading the transfer section", "version": 1}
```

- `query_id`: `q-001` to `q-040`, never reused.
- `split`: write `dev` while labeling (T-10). T-11 moves about 10 queries to `test`, stratified by type with a fixed seed, and freezes the file (tag `dataset-v1`). No tuning on `test`.
- `version`: 1. Any label change after freezing bumps the version and adds a changelog line (ADR-004).

## 9. Checklist per query

- [ ] Written before looking up the answer
- [ ] Type assigned; near-copy rule respected
- [ ] At least one grade-2 article; at most 5 labels
- [ ] Every label checked on the PDF page; page in `source_note`
- [ ] Body article only (no Penjelasan)
- [ ] Any label found via search marked `found_via_search`
