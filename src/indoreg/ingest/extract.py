"""PDF to per-page text with pdfplumber (ADR-005)."""

from pathlib import Path

import pdfplumber

from indoreg.logging import get_logger

log = get_logger(__name__)


def extract_pages(path: Path, doc_id: str) -> list[str]:
    """Text of each page. A page that fails is logged and kept as "" (FR-ING-3)."""
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            try:
                pages.append(page.extract_text() or "")
            # pdfminer raises many unrelated exception types on damaged pages;
            # the page is logged with its location and skipped, never silently.
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "page extraction failed",
                    extra={
                        "fields": {"doc_id": doc_id, "page": number, "error": repr(e)}
                    },
                )
                pages.append("")
    return pages
