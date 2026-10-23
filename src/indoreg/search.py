"""Command-line search over the ingested articles (BM25).

Run: python -m indoreg.search "your question" [--top-k N] [--config PATH]
Needs the chunks written by `python -m indoreg.ingest.pipeline`.
"""

import argparse
import sys
import textwrap
from pathlib import Path

from indoreg.config import Settings, load_settings
from indoreg.retrieval.bm25 import BM25Retriever
from indoreg.schemas import Chunk

DISCLAIMER = (
    "Retrieval only. Not legal advice. "
    "Check amendment and revocation status at the source."
)
PREVIEW_CHARS = 400


def load_chunks(settings: Settings, strategy: str) -> list[Chunk]:
    path = settings.paths.chunks / f"{strategy}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run the ingest step first")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Chunk.model_validate_json(ln) for ln in lines if ln]


def render(query: str, chunks: list[Chunk], settings: Settings, top_k: int) -> str:
    cfg = settings.retrieval.bm25
    bm25 = BM25Retriever("bm25-basic", k1=cfg.k1, b=cfg.b)
    bm25.build(chunks)
    by_id = {c.chunk_id: c for c in chunks}
    hits = bm25.search(query, top_k)
    out = [f'Query: "{query}"  ({len(chunks)} articles indexed, BM25)', ""]
    if not hits:
        out.append("No article matched any query word.")
    for h in hits:
        c = by_id[h.chunk_id]
        body = " ".join(c.text.split())
        if len(body) > PREVIEW_CHARS:
            body = body[:PREVIEW_CHARS] + " ..."
        out += [
            f"{h.rank}. Pasal {c.article} - {c.title}",
            f"   score {h.score:.2f} | status: {c.doc_status or 'not yet recorded'}"
            f" | source: {c.source_url or 'not yet recorded'}",
            textwrap.indent(textwrap.fill(body, 96), "   "),
            "",
        ]
    out.append(DISCLAIMER)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search Indonesian regulations.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    top_k = args.top_k or settings.search.default_top_k
    if not 1 <= top_k <= settings.search.max_top_k:
        parser.error(f"--top-k must be between 1 and {settings.search.max_top_k}")
    if not args.query.strip():
        parser.error("query must not be empty")
    try:
        chunks = load_chunks(settings, settings.search.strategy)
    except FileNotFoundError as e:
        sys.stderr.write(f"{e}\n")
        return 1
    sys.stdout.write(render(args.query, chunks, settings, top_k) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
