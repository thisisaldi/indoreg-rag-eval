"""Article-based chunker: one chunk per body article span (FR-CHK-1, FR-CHK-3)."""

from indoreg.schemas import ArticleSpan, Chunk, ManifestEntry


def article_chunks(
    entry: ManifestEntry, text: str, spans: list[ArticleSpan]
) -> list[Chunk]:
    """Chunk text is exactly text[char_start:char_end], so offsets reconstruct it."""
    return [
        Chunk(
            chunk_id=f"{entry.doc_id}:article:{s.article}",
            doc_id=entry.doc_id,
            title=entry.title,
            strategy="article",
            article=s.article,
            chapter=s.chapter,
            articles=[s.article],
            char_start=s.char_start,
            char_end=s.char_end,
            text=text[s.char_start : s.char_end],
            source_url=entry.source_url,
            doc_status=entry.status,
        )
        for s in spans
    ]
