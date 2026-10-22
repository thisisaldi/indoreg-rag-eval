"""Data crossing module boundaries: manifest entries, article spans, chunks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

DocStatus = Literal["in_force", "amended", "revoked", "unknown"]
# How an article marker was resolved (ADR-010); "plain" is an exact "Pasal N".
Method = Literal["plain", "confusion", "catchword_swap", "tiebreak_later", "gap_fill"]


class ManifestEntry(BaseModel):
    """One source regulation (design.md 3.1). Null fields are still to be filled."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    doc_id: str
    title: str
    reg_type: str
    number: str
    year: int
    status: DocStatus | None
    status_source: str | None
    source_url: str | None
    retrieved_on: str | None
    filename: str
    sha256: str
    text_quality: Literal["native", "image_text_layer"]


class ArticleSpan(BaseModel):
    """A body article located in the cleaned text of one document (design.md 3.2)."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    article: str
    page: int
    char_start: int
    char_end: int
    method: Method
    marker_raw: str


class Chunk(BaseModel):
    """A retrievable unit with its citation fields (design.md 3.3)."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    doc_id: str
    title: str
    strategy: Literal["article", "fixed"]
    article: str | None
    chapter: str | None
    char_start: int
    char_end: int
    text: str
    source_url: str | None
    doc_status: DocStatus | None
