# Label issues for dataset-v1 (proposals, not applied)

`eval/dataset.jsonl` is frozen as `dataset-v1` and Claude does not edit it (CLAUDE.md hard rule 1, ADR-015). These are proposals for Aldi. Applying any of them means a new dataset version with a changelog line (ADR-004), and new result files.

| Query | Split | Proposal | Evidence | Confidence | Source |
|---|---|---|---|---|---|
| q-021 "Apakah instansi pemerintah boleh menyimpan datanya di server luar negeri?" | dev | Consider adding uu-27-2022 Pasal 56, grade 1 | Pasal 56(1): "Pengendali Data Pribadi dapat melakukan transfer Data Pribadi kepada Pengendali Data Pribadi dan/atau Prosesor Data Pribadi di luar wilayah hukum Negara Republik Indonesia ..."; a public body can be a Pengendali. Storing on a foreign server is not clearly a "transfer". | Low | T-21, `reports/error_analysis.md` |
| q-022 | test | Keep labels; tag `superseded regulation` in reporting | UU 11/2008 Pasal 30 and 46; BPK lists UU 11/2008 as partly revoked by UU 1/2023; labels follow the corpus text, as the source_note says | Decision for Aldi | T-21 |
| q-033 | dev | Keep labels; tag `superseded regulation` in reporting | UU 11/2008 Pasal 31 and 47; same status note as q-022 | Decision for Aldi | T-21 |

No label errors were found in the 10 dev failures analysed in T-21.
