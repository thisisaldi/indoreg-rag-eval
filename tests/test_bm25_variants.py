from pathlib import Path

import pytest

from indoreg.config import ConfigError, load_settings
from indoreg.retrieval.bm25 import BM25Retriever
from indoreg.retrieval.preprocess import basic_tokens, id_tokens
from indoreg.retrieval.registry import build_retriever
from indoreg.schemas import Chunk

REPO_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


def chunk(cid: str, title: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=cid,
        doc_id=cid.split(":")[0],
        title=title,
        strategy="article",
        article="1",
        chapter=None,
        char_start=0,
        char_end=len(text),
        text=text,
        source_url=None,
        doc_status=None,
    )


def test_id_tokens_drop_function_words_and_strip_particles() -> None:
    assert id_tokens("Apakah datanya boleh dikirim ke luar negeri?") == [
        "data",
        "dikirim",
        "luar",
        "negeri",
    ]
    assert id_tokens("Bolehkah data dikirim?") == [
        "data",
        "dikirim",
    ]  # boleh is a stopword
    assert id_tokens("tidak berlaku Pasal 56") == ["tidak", "berlaku", "pasal", "56"]
    # Too short to strip: "punya" keeps its letters.
    assert id_tokens("punya") == ["punya"]
    assert basic_tokens("Apakah datanya") == ["apakah", "datanya"]


def test_title_indexing_lets_law_names_match() -> None:
    docs = [
        chunk(
            "uu27:1",
            "Undang-Undang Nomor 27 Tahun 2022",
            "transfer data ke luar negeri",
        ),
        chunk(
            "pp71:1",
            "Peraturan Pemerintah Nomor 71 Tahun 2019",
            "transfer data ke luar negeri",
        ),
    ]
    plain = BM25Retriever("p", 1.5, 0.75, tokenizer=id_tokens, index_title=False)
    titled = BM25Retriever("t", 1.5, 0.75, tokenizer=id_tokens, index_title=True)
    for r in (plain, titled):
        r.build(docs)
    q = "transfer data Undang-Undang 27 Tahun 2022"
    assert (
        plain.search(q, 2)[0].score == plain.search(q, 2)[1].score
    )  # cannot tell apart
    assert titled.search(q, 2)[0].chunk_id == "uu27:1"


def test_registry_builds_configured_variants() -> None:
    settings = load_settings(REPO_CONFIG)
    r = build_retriever("bm25-id-title", settings)
    assert isinstance(r, BM25Retriever) and r.index_title and r.tokenizer is id_tokens
    with pytest.raises(ValueError, match="unknown retriever"):
        build_retriever("nope", settings)


def test_config_rejects_undefined_retriever_names(tmp_path: Path) -> None:
    text = REPO_CONFIG.read_text(encoding="utf-8").replace(
        "retriever: bm25-basic", "retriever: bm25-missing"
    )
    p = tmp_path / "c.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="bm25-missing"):
        load_settings(p)
