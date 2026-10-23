from collections.abc import Sequence
from pathlib import Path

import pytest

from indoreg.config import ConfigError, load_settings
from indoreg.retrieval.base import RetrievalResult
from indoreg.retrieval.hybrid import HybridRetriever, rrf
from indoreg.retrieval.registry import build_retriever
from indoreg.schemas import Chunk

REPO_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


def ranking(*ids: str) -> list[RetrievalResult]:
    return [
        RetrievalResult(chunk_id=c, score=0.0, rank=r) for r, c in enumerate(ids, 1)
    ]


class Fixed:
    """Stub member returning a fixed ranking, truncated to top_k."""

    def __init__(self, ids: Sequence[str]) -> None:
        self.name = "fixed"
        self.ids = list(ids)
        self.built = False
        self.asked: list[int] = []

    def build(self, chunks: Sequence[Chunk]) -> None:
        self.built = True

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        self.asked.append(top_k)
        return ranking(*self.ids[:top_k])


def test_rrf_hand_computed() -> None:
    fused = rrf([ranking("a", "b", "c"), ranking("c", "a")], k=1)
    # a: 1/2 + 1/3 = 0.833, c: 1/4 + 1/2 = 0.75, b: 1/3
    assert [h.chunk_id for h in fused] == ["a", "c", "b"]
    assert fused[0].score == pytest.approx(5 / 6) and fused[2].rank == 3


def test_rrf_ties_break_on_chunk_id_and_empty_member_is_ignored() -> None:
    fused = rrf([ranking("b", "a"), ranking("a", "b"), []], k=60)
    assert [h.chunk_id for h in fused] == ["a", "b"]
    assert rrf([[], []], k=60) == []


def test_hybrid_builds_members_and_searches_to_depth() -> None:
    m1, m2 = Fixed(["a", "c", "b"]), Fixed(["c", "d"])
    h = HybridRetriever("h", [m1, m2], rrf_k=1, depth=2)
    h.build([])
    hits = h.search("q", 1)
    assert m1.built and m2.built and m1.asked == [2] and m2.asked == [2]
    assert [x.chunk_id for x in hits] == ["c"]  # 1/3 + 1/2 beats a's 1/2


def test_registry_builds_hybrid_of_bm25_members(tmp_path: Path) -> None:
    text = REPO_CONFIG.read_text(encoding="utf-8")
    text += "\n"  # members are BM25 only, so no model download
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        text.replace(
            "    bm25-id-title: {type: bm25, preprocess: id, index_title: true}\n",
            "    bm25-id-title: {type: bm25, preprocess: id, index_title: true}\n"
            "    hy: {type: hybrid, members: [bm25-basic, bm25-id], rrf_k: 60,"
            " depth: 5}\n",
        ),
        encoding="utf-8",
    )
    r = build_retriever("hy", load_settings(cfg))
    assert isinstance(r, HybridRetriever) and [m.name for m in r.members] == [
        "bm25-basic",
        "bm25-id",
    ]


@pytest.mark.parametrize("members", ["[bm25-basic, nope]", "[bm25-basic, hy]"])
def test_config_rejects_bad_hybrid_members(tmp_path: Path, members: str) -> None:
    text = REPO_CONFIG.read_text(encoding="utf-8").replace(
        "    bm25-id-title: {type: bm25, preprocess: id, index_title: true}\n",
        "    bm25-id-title: {type: bm25, preprocess: id, index_title: true}\n"
        f"    hy: {{type: hybrid, members: {members}, rrf_k: 60, depth: 5}}\n",
    )
    cfg = tmp_path / "c.yaml"
    cfg.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="members"):
        load_settings(cfg)
