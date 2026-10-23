import json
from pathlib import Path

import pytest

from indoreg.config import load_settings
from indoreg.eval.dataset import DatasetError, load_dataset
from indoreg.eval.runner import markdown, percentile, run, write
from indoreg.schemas import Chunk

ARTICLES = {
    "1": "transfer data pribadi ke luar negeri wajib setara",
    "2": "transfer data pribadi dalam negeri",
    "3": "tanda tangan elektronik sah",
}


def query(
    qid: str, text: str, split: str, labels: list[tuple[str, int]], **extra: object
) -> str:
    rec = {
        "query_id": qid,
        "query": text,
        "type": "paraphrase",
        "split": split,
        "relevant": [{"doc_id": "d", "article": a, "grade": g} for a, g in labels],
        "source_note": "test",
        "version": 1,
        **extra,
    }
    return json.dumps(rec)


def setup(tmp_path: Path, lines: list[str]) -> Path:
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    rows = [
        Chunk(
            chunk_id=f"d:article:{a}",
            doc_id="d",
            title="T",
            strategy="article",
            article=a,
            chapter=None,
            char_start=0,
            char_end=len(t),
            text=t,
            source_url=None,
            doc_status=None,
        ).model_dump_json()
        for a, t in ARTICLES.items()
    ]
    (chunks / "article.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (tmp_path / "dataset.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    cfg = tmp_path / "cfg.yaml"
    dataset = (tmp_path / "dataset.jsonl").as_posix()
    out = (tmp_path / "out").as_posix()
    cfg.write_text(
        f"""
paths: {{raw: r, manifest: m, dataset: {dataset},
  processed: p, chunks: {chunks.as_posix()}, cache: k, results: {out}}}
chunking: {{fixed: {{size_chars: 100, overlap_chars: 10}}}}
logging: {{level: INFO, log_query_text: false}}
retrieval: {{bm25: {{k1: 1.5, b: 0.75}},
  retrievers: {{bm25-basic: {{type: bm25, preprocess: basic, index_title: false}}}}}}
search: {{default_top_k: 5, max_top_k: 20, retriever: bm25-basic,
  strategy: article}}
eval: {{retrievers: [bm25-basic], strategies: [article],
  baseline: bm25-basic/article,
  bootstrap: {{iterations: 200, seed: 42, confidence: 0.95}},
  splits: [dev, test], recall_ks: [1, 2], ndcg_k: 2,
  depth: 3}}
""",
        encoding="utf-8",
    )
    return cfg


DATA = [
    query("q-1", "transfer data ke luar negeri", "dev", [("1", 2)]),
    query("q-2", "tanda tangan elektronik", "dev", [("3", 2), ("2", 1)]),
    query("q-3", "transfer dalam negeri", "test", [("2", 2)]),
]


def test_run_scores_dev_and_test_splits(tmp_path: Path) -> None:
    settings = load_settings(setup(tmp_path, DATA))
    res = run(settings, settings.paths.dataset, allow_drafts=False)
    dev = res["results"]["dev"]["bm25-basic/article"]
    test = res["results"]["test"]["bm25-basic/article"]
    assert dev["summary"]["n"] == 2 and test["summary"]["n"] == 1
    q1, q2 = dev["queries"]
    assert q1["ranking"][0] == "d:1" and q1["rr"] == 1.0 and q1["recall@1"] == 1.0
    assert q2["ranking"] == ["d:3"]  # article 2 shares no query word
    assert q2["recall@2"] == 0.5 and q2["rr"] == 1.0
    assert dev["summary"]["recall@2"] == pytest.approx(0.75)
    assert dev["summary"]["rr"] == 1.0
    assert not res["dataset"]["unverified_drafts"]


def test_metrics_identical_across_reruns(tmp_path: Path) -> None:
    settings = load_settings(setup(tmp_path, DATA))

    def strip(res: dict) -> dict:
        out = json.loads(json.dumps(res["results"]))
        for by_ret in out.values():
            for r in by_ret.values():
                r["summary"].pop("latency_p50_ms")
                r["summary"].pop("latency_p95_ms")
                for row in r["queries"]:
                    row.pop("latency_ms")
        return out

    a = run(settings, settings.paths.dataset, False)
    b = run(settings, settings.paths.dataset, False)
    assert strip(a) == strip(b)


def test_write_json_and_markdown(tmp_path: Path) -> None:
    settings = load_settings(setup(tmp_path, DATA))
    res = run(settings, settings.paths.dataset, False)
    path = write(res, settings.paths.results)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["run_id"] == res["run_id"] and "git" in saved and "config" in saved
    md = path.with_suffix(".md").read_text(encoding="utf-8")
    assert "| bm25-basic/article | 2 |" in md and "MRR" in md and "UNVERIFIED" not in md
    assert saved["dataset"]["labels_human_verified"] and "not human-verified" not in md


def test_llm_checked_labels_are_disclosed(tmp_path: Path) -> None:
    lines = [
        query(
            "q-1",
            "transfer",
            "dev",
            [("1", 2)],
            source_note="checked; not human-verified",
        )
    ]
    settings = load_settings(setup(tmp_path, lines))
    res = run(settings, settings.paths.dataset, False)
    assert not res["dataset"]["labels_human_verified"]
    assert "not human-verified (ADR-015)" in markdown(res)


def test_drafts_need_flag_and_are_marked(tmp_path: Path) -> None:
    draft = [query("q-1", "transfer", "dev", [("1", 2)], draft_status="unverified")]
    settings = load_settings(setup(tmp_path, draft))
    with pytest.raises(DatasetError, match="unverified draft"):
        run(settings, settings.paths.dataset, allow_drafts=False)
    res = run(settings, settings.paths.dataset, allow_drafts=True)
    assert res["dataset"]["unverified_drafts"] and res["run_id"].endswith("-unverified")
    md = markdown(res)
    assert "UNVERIFIED LABELS" in md
    assert (
        "| bm25-basic/article | 0 | n/a |" in md
    )  # empty test split renders, not crashes


@pytest.mark.parametrize(
    "line, fragment",
    [
        (query("q-1", "x", "dev", [("1", 1)]), "grade-2"),
        (query("q-1", "x", "dev", [("1", 2), ("1", 1)]), "duplicate label"),
        (query("q-1", "x", "train", [("1", 2)]), "split"),
        (query("q-1", "x", "dev", [("1", 3)]), "grade"),
        ("{not json", "line 1"),
    ],
)
def test_invalid_records_are_reported(tmp_path: Path, line: str, fragment: str) -> None:
    p = tmp_path / "d.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(DatasetError, match=fragment):
        load_dataset(p)


def test_duplicate_query_ids(tmp_path: Path) -> None:
    p = tmp_path / "d.jsonl"
    p.write_text("\n".join([DATA[0], DATA[0]]) + "\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="duplicate query_id q-1"):
        load_dataset(p)


def test_percentile_nearest_rank() -> None:
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 50) == 3.0
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 95) == 5.0
    assert percentile([7.0], 95) == 7.0


def test_summary_has_ci_and_compare_is_paired(tmp_path: Path) -> None:
    from indoreg.config import BootstrapConfig
    from indoreg.eval.runner import compare

    settings = load_settings(setup(tmp_path, DATA))
    res = run(settings, settings.paths.dataset, False)
    s = res["results"]["dev"]["bm25-basic/article"]["summary"]
    assert s["ci"]["rr"]["low"] <= s["rr"] <= s["ci"]["rr"]["high"]
    assert res["comparisons"] == {"dev": {}, "test": {}}  # only the baseline ran
    rows_a = [{"m": 1.0}, {"m": 0.0}, {"m": 1.0}]
    rows_b = [{"m": 0.0}, {"m": 0.0}, {"m": 1.0}]
    results = {"dev": {"base": {"queries": rows_b}, "new": {"queries": rows_a}}}
    boot = BootstrapConfig(iterations=100, seed=1, confidence=0.95)
    c = compare(results, "base", ["m"], boot)["dev"]["new"]["m"]
    assert c["win_loss"] == {"wins": 1, "losses": 0, "ties": 2}
    assert c["diff"]["mean"] == pytest.approx(1 / 3)


def test_compare_strategies_pairs_each_retriever_with_itself() -> None:
    from indoreg.config import BootstrapConfig
    from indoreg.eval.runner import compare_strategies

    def rows(*vals: float) -> dict:
        return {"queries": [{"m": v} for v in vals]}

    results = {
        "dev": {
            "a/article": rows(1.0, 1.0),
            "b/article": rows(0.0, 0.0),
            "a/fixed": rows(0.0, 1.0),
            "b/fixed": rows(1.0, 0.0),
        }
    }
    boot = BootstrapConfig(iterations=50, seed=1, confidence=0.95)
    c = compare_strategies(results, ["a", "b"], ["article", "fixed"], ["m"], boot)
    assert list(c["dev"]) == ["a/fixed", "b/fixed"]
    assert c["dev"]["a/fixed"]["m"]["win_loss"] == {"wins": 0, "losses": 1, "ties": 1}
    assert c["dev"]["b/fixed"]["m"]["win_loss"] == {"wins": 1, "losses": 0, "ties": 1}
    assert c["dev"]["a/fixed"]["m"]["diff"]["mean"] == pytest.approx(-0.5)
