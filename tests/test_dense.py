from pathlib import Path

import numpy as np
import pytest

from indoreg.config import DenseSpec, load_settings
from indoreg.retrieval.dense import DenseRetriever, Matrix, mean_pool_normalise
from indoreg.schemas import Chunk

REPO_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"
VOCAB = ["transfer", "data", "tanda", "tangan", "sanksi"]


class BagOfWords:
    """Stub encoder: normalised word counts over a fixed vocabulary."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> Matrix:
        self.calls.append(texts)
        m = np.array(
            [[t.lower().split().count(w) for w in VOCAB] for t in texts],
            dtype=np.float32,
        )
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        return m / np.where(norms == 0, 1, norms)


def chunk(cid: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=cid,
        doc_id="d",
        title="T",
        strategy="article",
        article=cid,
        chapter=None,
        char_start=0,
        char_end=len(text),
        text=text,
        source_url=None,
        doc_status=None,
    )


CHUNKS = [
    chunk("3", "tanda tangan"),
    chunk("1", "transfer data"),
    chunk("2", "data transfer"),  # same vector as "1": tie broken by chunk_id
    chunk("4", "sanksi"),
]


def test_ranks_by_cosine_with_chunk_id_tie_break(tmp_path: Path) -> None:
    r = DenseRetriever("d", BagOfWords(), "m", tmp_path, query_prefix="q: ")
    r.build(CHUNKS)
    hits = r.search("transfer data", 3)
    assert [h.chunk_id for h in hits] == ["1", "2", "3"]
    assert [h.rank for h in hits] == [1, 2, 3]
    assert hits[0].score == pytest.approx(1.0)
    assert r.stats["dim"] == len(VOCAB) and r.stats["index_bytes"] == 4 * 5 * 4


def test_cache_reused_and_keyed_by_model_and_text(tmp_path: Path) -> None:
    enc = BagOfWords()
    first = DenseRetriever("d", enc, "m", tmp_path, passage_prefix="p: ")
    first.build(CHUNKS)
    assert not first.stats["cache_hit"] and enc.calls[0][0] == "p: tanda tangan"
    again = DenseRetriever("d", enc, "m", tmp_path)
    again.build(CHUNKS)
    assert again.stats["cache_hit"] and len(enc.calls) == 1
    changed = [*CHUNKS[:3], chunk("4", "sanksi data")]
    again.build(changed)
    other_model = DenseRetriever("d", enc, "m2", tmp_path)
    other_model.build(CHUNKS)
    assert len(enc.calls) == 3 and len(list(tmp_path.glob("*.npy"))) == 3


def test_empty_index_returns_nothing(tmp_path: Path) -> None:
    r = DenseRetriever("d", BagOfWords(), "m", tmp_path)
    assert r.search("data", 5) == []


def test_repo_config_declares_pinned_dense_model() -> None:
    spec = load_settings(REPO_CONFIG).retrieval.retrievers["dense-e5-small"]
    assert isinstance(spec, DenseSpec) and len(spec.revision) == 40


def test_mean_pool_ignores_padding_and_normalises() -> None:
    hidden = np.array([[[3.0, 4.0], [100.0, 100.0]]], dtype=np.float32)
    mask = np.array([[1, 0]], dtype=np.int64)
    out = mean_pool_normalise(hidden, mask)
    assert out.tolist() == [[pytest.approx(0.6), pytest.approx(0.8)]]
