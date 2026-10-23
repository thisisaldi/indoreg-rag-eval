# Error analysis (T-21)

Config analysed: `hybrid/article` (RRF over `bm25-id-title` and `dense-e5-small`, k 60, depth 50), the best dev configuration in `reports/results/20261023T073624Z-a0d608d`. Per-query numbers, member ranks and the summary counts come from `reports/results/20261023T073624Z-a0d608d.worst-dev.txt`, written by `scripts/worst_queries.py` from that result file and the processed corpus.

> Labels were drafted and checked by an LLM, not human-verified (ADR-015). The same model wrote this analysis, so it may lean towards calling a miss a retrieval error rather than a label error. Every label judgement below quotes the article text so it can be checked.

Scope: dev queries only, worst nDCG@10 first. The test split is not analysed for causes, because T-22 (reranker) is still to be tuned on dev and test failures would inform it. The exception is the known q-022 label status, discussed without looking at its retrieval results.

Member ranks: the result file stores each run's top 20 (eval depth), while the hybrid fuses each member's top 50. A "-" in a member column means "not in that member's top 20", not "not retrieved".

## Summary (dev, 30 queries)

| Check | Result | Reading |
|---|---|---|
| Mean nDCG@10 by query type | exact_ref 0.898 (n=7), paraphrase 0.715 (n=12), mixed_id_en 0.677 (n=3), terminology 0.366 (n=8) | Terminology queries, which use everyday words for statutory terms, are the weak spot. |
| Labelled (query, article) pairs in top 10, by document | uu-27-2022 17/22, pp-71-2019 9/12 (both scanned, OCR text layer); uu-11-2008 7/9, permen-kominfo-20-2016 8/14 (both native text) | No sign that the scanned documents are retrieved worse. |
| Labelled articles over the 512-token limit of e5 | 1 (pp-71-2019:14, 589 tokens), and it is found | Truncation does not explain any dev miss. |
| Article spans that contain a section heading | 76 of 273 | Headings such as "Bagian Kedua Transfer Data Pribadi ke Luar Wilayah Hukum ..." sit at the end of the previous article's span (see q-026, q-011). |

## Failures

Ranks are given as hybrid / bm25-id-title / dense-e5-small. Cause tags are from T-21; "other" is explained in the row.

| # | Query (type) | nDCG@10 | Expected (grade): ranks | Retrieved instead (top 3) | Cause tags | Evidence |
|---|---|---|---|---|---|---|
| 1 | q-027 "Izin dari pemilik data harus tertulis atau boleh lewat rekaman?" (terminology) | 0.000 | uu-27-2022:22 (2): - / - / - | permen-kominfo-20-2016:28, pp-71-2019:14, permen-kominfo-20-2016:2 | vocabulary gap; extraction error | The article says "Persetujuan pemrosesan Data Pribadi dilakukan melalui persetujuan tertulis atau terekam": izin vs persetujuan, rekaman vs terekam. The OCR text also garbles the key term in 5 of its 7 occurrences ("Persetqiuan", "Persetqjuan", "persetqluan"), so even a query using "persetujuan" would match it poorly. |
| 2 | q-031 "Bagaimana aturan hak untuk dilupakan dari hasil pencarian Google?" (terminology) | 0.000 | pp-71-2019:17 (2): - / - / -; pp-71-2019:15 (1): - / - / - | uu-11-2008:30, uu-11-2008:32, uu-11-2008:27 | vocabulary gap; extraction error | The regulation calls it "pengeluaran dari daftar mesin pencari (right to delisting)"; the query says "hak untuk dilupakan" and "Google". The English term is OCR-garbled in both articles ("rigru to delistingl", "deli.stingl"). |
| 3 | q-025 "Bagaimana cara pemilik data mengadukan kebocoran datanya ke Kementerian Kominfo?" (paraphrase) | 0.161 | permen-kominfo-20-2016:29 (2): 10 / 10 / -; :31 (2): - / - / -; :30 (1): - / - / - | pp-71-2019:14, pp-71-2019:18, pp-71-2019:97 | vocabulary gap; multi-article answer | Pasal 29: "dapat mengajukan pengaduan kepada Menteri atas kegagalan perlindungan kerahasiaan Data Pribadi": kebocoran vs kegagalan perlindungan kerahasiaan, Kominfo vs Menteri, mengadukan vs pengaduan (no stemming, ADR-007). The procedure is spread over Pasal 29 to 31. |
| 4 | q-030 "Apakah konsumen bisa minta datanya dihapus dari aplikasi?" (terminology) | 0.277 | uu-27-2022:8 (2): - / - / -; uu-27-2022:43 (2): 7 / - / -; pp-71-2019:15 (2): - / - / -; pp-71-2019:16 (1): 1 / 3 / 9; permen-kominfo-20-2016:20 (1): - / - / 3 | pp-71-2019:16, pp-71-2019:14, uu-11-2008:28 | multi-article answer; vocabulary gap | Five labelled articles in three regulations. The law says "Subjek Data Pribadi berhak ... menghapus" (UU 27/2022 Pasal 8) and "menghapus ... atas permintaan orang yang bersangkutan" (PP 71/2019 Pasal 15), not "konsumen ... dihapus". |
| 5 | q-026 "Apakah UU Pelindungan Data Pribadi juga berlaku bagi perusahaan di luar Indonesia?" (paraphrase) | 0.301 | uu-27-2022:2 (2): 9 / 1 / - | uu-27-2022:55, uu-27-2022:60, uu-27-2022:52 | chunk boundary; other (fusion buries a BM25 hit) | Pasal 2 ("berlaku untuk Setiap Orang ... di luar wilayah hukum Negara Republik Indonesia") is rank 1 for the BM25 member but not in the dense top 20, so fusion drops it to 9. The new rank 1, Pasal 55, is about domestic transfers but its span ends with the next section's heading "Bagian Kedua Transfer Data Pribadi ke Luar Wilayah Hukum Negara Republik Indonesia". |
| 6 | q-034 "Apakah rekam medis dan sidik jari termasuk data sensitif?" (terminology) | 0.301 | uu-27-2022:4 (2): 9 / - / - | pp-71-2019:99, pp-71-2019:22, uu-11-2008:40 | vocabulary gap | The article lists "data dan informasi kesehatan; data biometrik" under "Data Pribadi yang bersifat spesifik": rekam medis vs kesehatan, sidik jari vs biometrik, sensitif vs spesifik. The top hit pp-71-2019:99 contains "rekam cadang elektronik" (backup) and "sektor kesehatan", which probably explains its rank (not verified per member). |
| 7 | q-036 "Siapa regulator yang mengawasi pelindungan data pribadi?" (terminology) | 0.304 | uu-27-2022:58 (2): - / - / -; uu-27-2022:59 (1): 5 / 7 / -; uu-27-2022:60 (1): 1 / 1 / 2; permen-kominfo-20-2016:35 (1): - / - / - | uu-27-2022:60, uu-27-2022:49, uu-27-2022:53 | vocabulary gap; multi-article answer | The grade-2 article (Pasal 58) names the body ("dilaksanakan oleh lembaga ... ditetapkan oleh Presiden") but never says "mengawasi" or "regulator"; the oversight wording is in Pasal 59 and 60, which are found. |
| 8 | q-033 "Apakah menyadap percakapan elektronik orang lain bisa dipidana?" (terminology) | 0.387 | uu-11-2008:31 (2): 2 / - / 4; uu-11-2008:47 (2): - / 8 / - | uu-11-2008:32, uu-11-2008:31, uu-11-2008:26 | multi-article answer; superseded regulation | Pasal 47 is the penalty and refers to the prohibition only by number: "Setiap Orang yang memenuhi unsur sebagaimana dimaksud dalam Pasal 31 ayat (1) atau ayat (2) dipidana ...". Nothing in it says "menyadap", so it can only be found through Pasal 31. BPK lists UU 11/2008 as partly revoked by UU 1/2023; see "Superseded regulation" below. |
| 9 | q-011 "Bolehkah perusahaan mengirim data pelanggan ke server di luar negeri?" (paraphrase) | 0.472 | uu-27-2022:56 (2): 6 / - / 3; pp-71-2019:21 (2): 8 / 7 / -; permen-kominfo-20-2016:22 (2): 7 / - / 5 | pp-71-2019:20, uu-27-2022:55, uu-27-2022:1 | vocabulary gap; chunk boundary | Rank 1 is PP 71/2019 Pasal 20, which is for public-scope operators ("Lingkup Publik ... wajib ... di wilayah Indonesia"); the labelled Pasal 21 is the private-scope rule a company needs. "Perusahaan" does not map to "Lingkup Privat". Rank 2 is again uu-27-2022:55 with the trailing "ke Luar Wilayah Hukum" heading. |
| 10 | q-004 "Pasal 26 UU 11 Tahun 2008 soal penggunaan data pribadi" (exact_ref) | 0.631 | uu-11-2008:26 (2): 2 / 1 / - | uu-27-2022:11, uu-11-2008:26, permen-kominfo-20-2016:24 | other (number collision) | The law number "11" in the query matches the article heading "Pasal 11" of UU 27/2022, a short article about restricting processing. The labelled article is found but one rank lower than in the BM25 member. |

Cause counts over these 10 failures (a failure can have several tags): vocabulary gap 7, multi-article answer 4, chunk boundary 2, extraction error 2, superseded regulation 1, label error 0, other 2 (fusion burying a BM25 hit, number collision).

## Label checks

- No label error was found in these 10 queries: in each case the labelled article text answers the query (quotes above).
- One possible missing label, not affecting the metrics above because the article is not retrieved: q-021 ("Apakah instansi pemerintah boleh menyimpan datanya di server luar negeri?") could add uu-27-2022:56 at grade 1, since Pasal 56 governs "transfer Data Pribadi ... di luar wilayah hukum Negara Republik Indonesia" by any Pengendali, which includes public bodies. Low confidence: storing on a foreign server is not obviously a "transfer". Listed in `eval/LABEL_ISSUES.md` for Aldi.

## Superseded regulation (q-022, q-033)

q-022 (test; UU 11/2008 Pasal 46 grade 2, Pasal 30 grade 1) and q-033 (dev; Pasal 31 and 47, both grade 2) label UU 11/2008 articles that BPK lists as partly revoked by UU 1/2023 (manifest status `amended`). The corpus holds the original 2008 text, the labels follow it, and their `source_note` says so. This analysis did not check which provisions UU 1/2023 revokes or from when they take effect.

Recommendation (Aldi decides; Claude does not edit the dataset): keep both labels as they are and tag the queries `superseded regulation` in the case study, because the benchmark measures retrieval over the corpus as collected, and the API returns `doc_status` with every result. Replacing them would need the amending texts in the corpus first (ADR-013).

## What the failures suggest (hypotheses, none measured)

Each would be a dev-only experiment with paired CIs; none is implemented here.

1. Move section headings to the article they introduce (ingestion, 76 of 273 spans affected). Expected to remove false matches like uu-27-2022:55 for "luar wilayah" queries (q-026, q-011) and give the next article its section context.
2. Terminology queries (mean nDCG@10 0.366) need the statutory term. Options: a stronger or reranking model (T-22), or query expansion with a small legal synonym list (izin to persetujuan, sensitif to spesifik, konsumen to subjek data pribadi). A synonym list written while reading these dev failures would be tuned on dev, so it would need the test split or new queries to show it generalises.
3. Morphology: mengadukan / pengaduan and dihapus / menghapus / penghapusan do not match (q-025, q-030). ADR-007 rejected a stemmer for the risk of merging legal terms; these misses are the measured cost on the other side.
4. Cross-references: penalty articles that cite "Pasal N" (q-033) could be indexed together with the cited article's text.
5. Exact references: parse "Pasal N UU X Tahun Y" into a document and article filter to avoid number collisions (q-004).
6. Fusion: q-026 shows RRF burying a BM25 rank-1 hit that dense misses. A weighted RRF would be one more dev-tuned parameter on 30 queries; not recommended without more queries.

Not supported by the dev data: scanned documents being retrieved worse, and the 512-token limit of e5 causing misses.

## Follow-up: hypothesis 1 tested (T-36)

Headings were moved out of the article spans (ADR-017) and the eval rerun (`reports/results/20261023T074949Z-ed9dbfc`; before/after in `reports/results/20261023T074949Z-ed9dbfc.vs-a0d608d.md`). On dev no configuration changed with a CI excluding 0 (hybrid/article nDCG@10 -0.002 [-0.03, +0.02]). q-026 went from 0.301 to 0.333 and q-011 from 0.472 to 0.550, but uu-27-2022:55 still ranks in the top 3 for q-026, so the trailing heading was not the main reason it ranked high. On test, hybrid/article nDCG@10 fell by 0.022 [-0.049, -0.004]. The fix is kept as a data correction; it did not deliver a measurable gain.
