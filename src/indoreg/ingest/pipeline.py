"""Manifest -> extracted text -> cleaned text + article spans -> article chunks.

Run: python -m indoreg.ingest.pipeline [--config PATH]
Outputs are deterministic: same inputs give byte-identical files (FR-ING-4).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from indoreg.chunking.article import article_chunks
from indoreg.chunking.fixed import fixed_chunks
from indoreg.config import Settings, load_settings
from indoreg.ingest.articles import segment
from indoreg.ingest.extract import extract_pages
from indoreg.logging import configure_logging, get_logger
from indoreg.schemas import Chunk, ManifestEntry

log = get_logger(__name__)


def load_manifest(path: Path) -> list[ManifestEntry]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    return [ManifestEntry.model_validate(e) for e in entries]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def ingest_document(settings: Settings, entry: ManifestEntry) -> dict[str, list[Chunk]]:
    """Chunks of one document per strategy ("article", "fixed")."""
    pdf = settings.paths.raw / entry.filename
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != entry.sha256:
        raise ValueError(f"{entry.doc_id}: sha256 mismatch for {pdf}")
    seg = segment(extract_pages(pdf, entry.doc_id), entry.doc_id)
    out = settings.paths.processed
    _write(out / f"{entry.doc_id}.txt", seg.text)
    spans = [s.model_dump() for s in seg.spans]
    _write(out / f"{entry.doc_id}.articles.json", json.dumps(spans, indent=1) + "\n")
    log.info(
        "document segmented",
        extra={
            "fields": {
                "doc_id": entry.doc_id,
                "articles": len(seg.spans),
                "last_article": seg.last_article,
                "missing": seg.missing,
                "unresolved_markers": seg.unresolved,
                "methods": dict(sorted(seg.methods.items())),
                "penjelasan_page": seg.boundary_page,
                "closing_page": seg.closing_page,
            }
        },
    )
    fx = settings.chunking.fixed
    return {
        "article": article_chunks(entry, seg.text, seg.spans),
        "fixed": fixed_chunks(
            entry, seg.text, seg.spans, fx.size_chars, fx.overlap_chars
        ),
    }


def run(settings: Settings) -> dict[str, list[Chunk]]:
    chunks: dict[str, list[Chunk]] = {"article": [], "fixed": []}
    failed: list[str] = []
    for entry in load_manifest(settings.paths.manifest):
        try:
            for strategy, part in ingest_document(settings, entry).items():
                chunks[strategy].extend(part)
        except (OSError, ValueError) as e:
            log.error(
                "document failed",
                extra={"fields": {"doc_id": entry.doc_id, "error": str(e)}},
            )
            failed.append(entry.doc_id)
    for strategy, part in chunks.items():
        lines = "".join(c.model_dump_json() + "\n" for c in part)
        _write(settings.paths.chunks / f"{strategy}.jsonl", lines)
    log.info(
        "ingest finished",
        extra={
            "fields": {
                "chunks": {k: len(v) for k, v in chunks.items()},
                "failed_documents": failed,
            }
        },
    )
    return chunks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    configure_logging(settings.logging.level)
    run(settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
