"""Fixed-size chunker, chapter (BAB) context and chunk-to-article mapping (T-07)."""

from indoreg.chunking.fixed import fixed_chunks, windows
from indoreg.eval.runner import chunk_units
from indoreg.ingest.articles import segment
from indoreg.schemas import ArticleSpan, ManifestEntry

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


def span(article: str, start: int, end: int, chapter: str | None = None) -> ArticleSpan:
    return ArticleSpan(
        doc_id="d",
        article=article,
        page=1,
        char_start=start,
        char_end=end,
        method="plain",
        marker_raw=f"Pasal {article}",
        chapter=chapter,
    )


def test_windows_overlap_cover_range_and_cut_at_whitespace() -> None:
    text = "kata " * 60  # 300 chars of words
    ws = windows(0, len(text), size=50, overlap=10, text=text)
    assert ws[0][0] == 0 and ws[-1][1] == len(text)
    for (s1, e1), (s2, _) in zip(ws, ws[1:], strict=False):
        assert e1 - s1 <= 50
        assert s2 == e1 - 10  # overlap
        assert text[e1] in " \n"  # cut at whitespace, not mid-word
    assert windows(0, 30, size=50, overlap=10, text="x" * 30) == [(0, 30)]


def test_windows_always_progress_without_whitespace() -> None:
    ws = windows(0, 100, size=10, overlap=9, text="x" * 100)
    assert ws[-1][1] == 100 and all(b > a for a, b in ws)


def test_fixed_chunks_list_overlapped_articles_and_stay_in_body() -> None:
    text = "Pasal 1\n" + "a " * 40 + "\nPasal 2\n" + "b " * 40 + "\nPENJELASAN tail"
    p2 = text.index("Pasal 2")
    body_end = text.index("PENJELASAN")
    spans = [span("1", 0, p2, "BAB I"), span("2", p2, body_end, "BAB II")]
    chunks = fixed_chunks(ENTRY, text, spans, size=60, overlap=10)
    assert chunks[0].articles == ["1"] and chunks[0].article == "1"
    assert chunks[0].chapter == "BAB I"
    straddle = [c for c in chunks if c.articles == ["1", "2"]]
    assert straddle and straddle[0].article is None
    assert all(c.char_end <= body_end for c in chunks)
    assert all(c.text == text[c.char_start : c.char_end] for c in chunks)
    assert {c.strategy for c in chunks} == {"fixed"}
    assert fixed_chunks(ENTRY, text, [], 60, 10) == []


def test_chunk_units_for_article_and_fixed_chunks() -> None:
    text = "Pasal 1\nx\nPasal 2\ny\n"
    spans = [span("1", 0, 10), span("2", 10, len(text))]
    fx = fixed_chunks(ENTRY, text, spans, size=100, overlap=0)
    assert chunk_units(fx[0]) == ["d:1", "d:2"]


def test_segment_assigns_last_bab_before_each_article() -> None:
    pages = [
        "BAB I\nKETENTUAN UMUM\nPasal 1\nSatu.\nPasal 2\nDua.\n"
        "BABII\nHAK\nPasal 3\nTiga.\nBAB lII\nSANKSI\nPasal 4\nEmpat."
    ]
    by = {s.article: s.chapter for s in segment(pages, "d").spans}
    assert by == {"1": "BAB I", "2": "BAB I", "3": "BAB II", "4": "BAB III"}


def test_chapter_ocr_variants() -> None:
    pages = [
        "BAB xI\nA\nPasal 1\nSatu.\n"
        "Ix\nBAB\nB\nPasal 2\nDua.\n"
        "BAB\nXIV\nC\nPasal 3\nTiga."
    ]
    by = {s.article: s.chapter for s in segment(pages, "d").spans}
    assert by == {"1": "BAB XI", "2": "BAB IX", "3": "BAB XIV"}
