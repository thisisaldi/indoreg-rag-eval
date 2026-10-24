"""Add body articles from an external SQLite dump to the PDF article chunks (ADR-020).

Run: python -m indoreg.ingest.external --config configs/full.yaml
Reads settings.external.base_chunks (the PDF corpus, from `make ingest`) and writes
<paths.chunks>/article.jsonl with those chunks first, then the external ones.

The dump has no status or per-document URL, so external chunks carry
doc_status "unknown" and the dataset URL. Documents already in the manifest are
skipped: the PDF text is the labeled one.
"""

import argparse
import hashlib
import re
import sqlite3
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from indoreg.config import ExternalCorpusConfig, load_settings
from indoreg.ingest.pipeline import load_manifest
from indoreg.logging import configure_logging, get_logger
from indoreg.schemas import Chunk

log = get_logger(__name__)

ARTICLE = re.compile(r"Pasal\s+(\d+[A-Z]?)")
# type, number, year, about, chapter, article, content
Row = tuple[str, str, int, str, str, str, str]


def slug(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "-", value.lower()).strip("-") or "x"


def to_chunks(
    rows: Iterable[Row],
    cfg: ExternalCorpusConfig,
    skip_doc_ids: set[str],
) -> Iterator[Chunk]:
    """Rows in dump order -> one chunk per body article. Pure, so it is unit tested."""
    doc_of: dict[tuple[str, str, int, str], str] = {}
    taken: set[str] = set()
    seen_ids: set[str] = set()
    for reg_type, number, year, about, chapter, article, content in rows:
        prefix = cfg.types.get(reg_type)
        m = ARTICLE.fullmatch(article or "")
        text = (content or "").strip()
        if prefix is None or m is None or len(text) < cfg.min_chars:
            continue
        base = f"{prefix}-{slug(number or '')}-{year}"
        if base in skip_doc_ids:
            continue
        key = (prefix, number, year, about)
        if key not in doc_of:
            # Same type/number/year with another title: a dump metadata error,
            # kept apart with a stable suffix.
            doc_id = f"ext-{base}"
            if doc_id in taken:
                doc_id += "-" + hashlib.sha1(about.encode()).hexdigest()[:6]
            doc_of[key] = doc_id
            taken.add(doc_id)
        doc_id = doc_of[key]
        art = m.group(1)
        chunk_id = f"{doc_id}:article:{art}"
        n = 2
        while chunk_id in seen_ids:  # the dump repeats some articles
            chunk_id = f"{doc_id}:article:{art}#{n}"
            n += 1
        seen_ids.add(chunk_id)
        body = f"Pasal {art}\n{text}"
        yield Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            title=f"{reg_type.title()} Nomor {number} Tahun {year} tentang {about}"[
                :300
            ],
            strategy="article",
            article=art,
            chapter=None if chapter in (None, "", "N/A") else chapter,
            articles=[art],
            char_start=0,
            char_end=len(body),
            text=body,
            source_url=cfg.source_url,
            doc_status="unknown",
        )


def read_rows(db: Path, types: Iterable[str]) -> Iterator[Row]:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        t = sorted(types)
        marks = ",".join("?" * len(t))
        yield from con.execute(
            "SELECT regulation_type, regulation_number, year, about, chapter, article,"
            f" content FROM regulations WHERE regulation_type IN ({marks})"
            " ORDER BY id",
            t,
        )
    finally:
        con.close()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    configure_logging(settings.logging.level)
    cfg = settings.external
    if cfg is None:
        log.error("no 'external' section in the config")
        return 2
    if sha256_file(cfg.db) != cfg.sha256:
        log.error("external db sha256 mismatch", extra={"fields": {"db": str(cfg.db)}})
        return 1
    manifest_ids = {e.doc_id for e in load_manifest(settings.paths.manifest)}
    base = cfg.base_chunks.read_text(encoding="utf-8")
    out = settings.paths.chunks / "article.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    docs: set[str] = set()
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(base)
        for c in to_chunks(read_rows(cfg.db, cfg.types), cfg, manifest_ids):
            f.write(c.model_dump_json() + "\n")
            n += 1
            docs.add(c.doc_id)
    log.info(
        "external corpus written",
        extra={
            "fields": {
                "out": str(out),
                "base_chunks": base.count("\n"),
                "external_chunks": n,
                "external_documents": len(docs),
            }
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
