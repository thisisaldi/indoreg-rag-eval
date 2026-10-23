"""Fixed-size overlapping chunker over the body text (FR-CHK-2, FR-CHK-3).

Windows cover the body only (first article start to last article end), so the
Penjelasan stays out (ADR-012). Each chunk lists every article its span overlaps
(design.md 3.3), which is how fixed chunks map to article labels (4.1).
"""

from indoreg.schemas import ArticleSpan, Chunk, ManifestEntry


def windows(
    start: int, end: int, size: int, overlap: int, text: str
) -> list[tuple[int, int]]:
    """Character windows of at most `size`, each starting `overlap` before the last
    one ended. A cut moves back to the last whitespace in the window's second half,
    so words are not split when that is possible."""
    out: list[tuple[int, int]] = []
    s = start
    while s < end:
        e = min(s + size, end)
        if e < end:
            cut = max(
                text.rfind(" ", s + size // 2, e), text.rfind("\n", s + size // 2, e)
            )
            if cut > s:
                e = cut
        out.append((s, e))
        if e >= end:
            break
        s = max(e - overlap, s + 1)
    return out


def fixed_chunks(
    entry: ManifestEntry,
    text: str,
    spans: list[ArticleSpan],
    size: int,
    overlap: int,
) -> list[Chunk]:
    if not spans:
        return []
    chunks = []
    for i, (s, e) in enumerate(
        windows(spans[0].char_start, spans[-1].char_end, size, overlap, text)
    ):
        hit = [sp for sp in spans if sp.char_start < e and sp.char_end > s]
        chunks.append(
            Chunk(
                chunk_id=f"{entry.doc_id}:fixed:{i:04d}",
                doc_id=entry.doc_id,
                title=entry.title,
                strategy="fixed",
                article=hit[0].article if len(hit) == 1 else None,
                chapter=hit[0].chapter if hit else None,
                articles=[sp.article for sp in hit],
                char_start=s,
                char_end=e,
                text=text[s:e],
                source_url=entry.source_url,
                doc_status=entry.status,
            )
        )
    return chunks
