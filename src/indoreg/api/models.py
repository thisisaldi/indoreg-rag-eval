"""Request and response models for the search API (design.md 5, FR-API)."""

from pydantic import BaseModel, Field, field_validator

from indoreg.schemas import DocStatus

DISCLAIMER = (
    "Retrieval only. Not legal advice. Check amendment and revocation status at"
    " the source."
)


class SearchRequest(BaseModel):
    """Length and top_k bounds come from config and are checked by the endpoint."""

    query: str
    top_k: int | None = Field(default=None, description="defaults to config")

    @field_validator("query")
    @classmethod
    def _strip_and_require_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty or whitespace")
        return v


class SearchHit(BaseModel):
    rank: int
    score: float
    text: str
    doc_id: str
    title: str
    article: str | None  # None for a fixed chunk spanning several articles
    articles: list[str]
    doc_status: DocStatus | None
    source_url: str | None


class SearchResponse(BaseModel):
    request_id: str
    query: str
    retriever: str
    results: list[SearchHit]
    latency_ms: float
    disclaimer: str = DISCLAIMER


class HealthResponse(BaseModel):
    status: str
    retriever: str
    strategy: str
    chunks: int
    index_built_at: str
