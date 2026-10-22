from indoreg.chunking.article import article_chunks
from indoreg.retrieval.bm25 import BM25Retriever, tokenize
from indoreg.schemas import ArticleSpan, Chunk, ManifestEntry

ENTRY = ManifestEntry(
    doc_id="d",
    title="T",
    reg_type="UU",
    number="1",
    year=2000,
    status="in_force",
    status_source="s",
    source_url="https://example.org/d",
    retrieved_on=None,
    filename="d.pdf",
    sha256="0" * 64,
    text_quality="native",
)


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


def test_article_chunks_reconstruct_text_and_carry_citation() -> None:
    text = "Pasal 1\nSatu.\nPasal 2\nDua.\n"
    spans = [
        ArticleSpan(
            doc_id="d",
            article="1",
            page=1,
            char_start=0,
            char_end=14,
            method="plain",
            marker_raw="Pasal 1",
        ),
        ArticleSpan(
            doc_id="d",
            article="2",
            page=1,
            char_start=14,
            char_end=len(text),
            method="plain",
            marker_raw="Pasal 2",
        ),
    ]
    chunks = article_chunks(ENTRY, text, spans)
    assert "".join(c.text for c in chunks) == text
    assert chunks[1].chunk_id == "d:article:2"
    assert chunks[1].source_url == "https://example.org/d"
    assert chunks[1].doc_status == "in_force"


def test_tokenize_lowercases_words() -> None:
    assert tokenize("Data Pribadi, (1) Pasal") == ["data", "pribadi", "1", "pasal"]


def test_bm25_ranks_matching_chunk_first_with_stable_ties() -> None:
    bm25 = BM25Retriever("bm25", k1=1.5, b=0.75)
    bm25.build(
        [
            chunk("a", "tanda tangan elektronik sah"),
            chunk("b", "transfer data pribadi ke luar negeri"),
            chunk("c", "transfer data pribadi dalam negeri"),
            chunk("d", "transfer data pribadi dalam negeri"),
        ]
    )
    hits = bm25.search("transfer ke luar negeri", top_k=3)
    assert [h.chunk_id for h in hits] == ["b", "c", "d"]  # c, d tie: by chunk_id
    assert [h.rank for h in hits] == [1, 2, 3]
    assert hits[0].score > hits[1].score == hits[2].score


def test_bm25_no_match_and_top_k() -> None:
    bm25 = BM25Retriever("bm25", k1=1.5, b=0.75)
    bm25.build([chunk("a", "satu dua"), chunk("b", "dua tiga")])
    assert bm25.search("empat", top_k=5) == []
    assert len(bm25.search("dua", top_k=1)) == 1
