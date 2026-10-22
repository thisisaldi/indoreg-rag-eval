from pathlib import Path

import pytest

from indoreg.config import ConfigError, load_settings

REPO_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"

VALID = """
paths: {raw: r, manifest: m.json, dataset: d.jsonl, processed: p, chunks: c, cache: k,
  results: o}
chunking: {fixed: {size_chars: 100, overlap_chars: 10}}
logging: {level: INFO, log_query_text: false}
retrieval: {bm25: {k1: 1.5, b: 0.75}}
search: {default_top_k: 5, max_top_k: 20}
eval: {retrievers: [bm25-basic], splits: [dev, test], recall_ks: [5, 10], ndcg_k: 10,
  depth: 20}
"""


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_repo_default_config_loads() -> None:
    s = load_settings(REPO_CONFIG)
    assert s.paths.raw == Path("data/raw")
    assert s.chunking.fixed.overlap_chars < s.chunking.fixed.size_chars
    assert s.logging.log_query_text is False


def test_env_overrides_nested_yaml_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INDOREG_CHUNKING__FIXED__SIZE_CHARS", "500")
    s = load_settings(write(tmp_path, VALID))
    assert s.chunking.fixed.size_chars == 500
    # The untouched sibling keeps its YAML value.
    assert s.chunking.fixed.overlap_chars == 10


def test_config_path_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INDOREG_CONFIG", str(write(tmp_path, VALID)))
    assert load_settings().paths.manifest == Path("m.json")


@pytest.mark.parametrize(
    "text, fragment",
    [
        (VALID.replace("overlap_chars: 10", "overlap_chars: 100"), "overlap_chars"),
        (VALID.replace("level: INFO", "level: LOUD"), "level"),
        (VALID + "extra_key: 1\n", "extra_key"),
        (VALID.replace("results: o", ""), "results"),
        ("- just\n- a list\n", "mapping"),
        ("paths: [unclosed\n", "invalid YAML"),
    ],
)
def test_invalid_config_fails_fast(tmp_path: Path, text: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_settings(write(tmp_path, text))


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / "nope.yaml")
