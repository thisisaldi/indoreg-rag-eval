"""CI eval (T-15): run the eval on a tiny synthetic corpus and fail if any metric
drops below the recorded floor.

The floor in tests/fixtures/ci_eval/floor.json holds the exact metrics of a known
good run (the pipeline is deterministic). To re-record after an intended change,
run: INDOREG_RECORD_FLOOR=1 uv run pytest tests/test_ci_eval.py
and justify the new floor in the commit message. Never lower it to make CI pass.
"""

import json
import os
from pathlib import Path

import pytest

from indoreg.config import Settings, load_settings
from indoreg.eval.runner import run

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ci_eval"
FLOOR = FIXTURE / "floor.json"
TOLERANCE = 1e-9  # float noise only; any real drop fails


def fixture_settings(tmp_path: Path) -> Settings:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"""
paths: {{raw: r, manifest: m, dataset: {(FIXTURE / "dataset.jsonl").as_posix()},
  processed: p, chunks: {(FIXTURE / "chunks").as_posix()}, cache: k,
  results: {(tmp_path / "out").as_posix()}}}
chunking: {{fixed: {{size_chars: 100, overlap_chars: 10}}}}
logging: {{level: WARNING, log_query_text: false}}
retrieval: {{bm25: {{k1: 1.5, b: 0.75}}}}
search: {{default_top_k: 5, max_top_k: 20, strategy: article}}
eval: {{retrievers: [bm25-basic], strategies: [article], splits: [dev, test],
  recall_ks: [1, 3], ndcg_k: 3,
  depth: 5}}
""",
        encoding="utf-8",
    )
    return load_settings(cfg)


def current_metrics(tmp_path: Path) -> dict[str, dict[str, dict[str, float]]]:
    settings = fixture_settings(tmp_path)
    res = run(settings, settings.paths.dataset, allow_drafts=False)
    return {
        split: {
            name: {k: r["summary"][k] for k in res["metric_keys"]}
            for name, r in by_ret.items()
        }
        for split, by_ret in res["results"].items()
    }


def test_metrics_do_not_drop_below_floor(tmp_path: Path) -> None:
    got = current_metrics(tmp_path)
    if os.environ.get("INDOREG_RECORD_FLOOR") == "1":
        FLOOR.write_text(
            json.dumps(got, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        pytest.skip("floor re-recorded")
    floor = json.loads(FLOOR.read_text(encoding="utf-8"))
    drops = [
        f"{split}/{name}/{k}: {got[split][name][k]:.4f} < floor {v:.4f}"
        for split, by_ret in floor.items()
        for name, metrics in by_ret.items()
        for k, v in metrics.items()
        if got[split][name][k] < v - TOLERANCE
    ]
    assert not drops, "metrics below CI floor:\n" + "\n".join(drops)
