"""FastAPI app: POST /search and GET /health over one retriever (design.md 5).

The retriever is built once in the lifespan and shared read-only by requests;
it is the same Retriever the eval runner benchmarks. Tests inject a stub.

Run locally: uv run uvicorn indoreg.api.app:create_app --factory
"""

import time
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request

from indoreg.api.models import (
    HealthResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from indoreg.config import Settings, load_settings
from indoreg.logging import configure_logging, get_logger
from indoreg.retrieval.base import Retriever
from indoreg.retrieval.registry import build_retriever
from indoreg.schemas import Chunk
from indoreg.search import load_chunks

log = get_logger(__name__)


@dataclass(frozen=True)
class Index:
    retriever: Retriever
    chunks: dict[str, Chunk]
    built_at: str


def build_index(
    settings: Settings,
    retriever: Retriever | None = None,
    chunks: Sequence[Chunk] | None = None,
) -> Index:
    chunks = (
        chunks
        if chunks is not None
        else load_chunks(settings, settings.search.strategy)
    )
    retriever = retriever or build_retriever(settings.search.retriever, settings)
    retriever.build(chunks)
    built_at = datetime.now(UTC).isoformat()
    log.info(
        "index built",
        extra={"fields": {"retriever": retriever.name, "chunks": len(chunks)}},
    )
    return Index(retriever, {c.chunk_id: c for c in chunks}, built_at)


def _invalid(field: str, msg: str) -> HTTPException:
    """422 with the same shape as FastAPI's own validation errors."""
    return HTTPException(
        status_code=422,
        detail=[{"loc": ["body", field], "msg": msg, "type": "value_error"}],
    )


def create_app(
    settings: Settings | None = None,
    retriever: Retriever | None = None,
    chunks: Sequence[Chunk] | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.logging.level)
    cfg = settings.search

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.index = build_index(settings, retriever, chunks)
        yield

    app = FastAPI(
        title="IndoReg-RAG search",
        description="Article retrieval over Indonesian personal data protection"
        " regulations. Retrieval only, not legal advice.",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        index: Index = request.app.state.index
        return HealthResponse(
            status="ok",
            retriever=index.retriever.name,
            strategy=cfg.strategy,
            chunks=len(index.chunks),
            index_built_at=index.built_at,
        )

    @app.post("/search", response_model=SearchResponse)
    def search(body: SearchRequest, request: Request) -> SearchResponse:
        if len(body.query) > cfg.max_query_chars:
            raise _invalid("query", f"at most {cfg.max_query_chars} characters")
        top_k = cfg.default_top_k if body.top_k is None else body.top_k
        if not 1 <= top_k <= cfg.max_top_k:
            raise _invalid("top_k", f"must be between 1 and {cfg.max_top_k}")
        index: Index = request.app.state.index
        start = time.perf_counter()
        hits = index.retriever.search(body.query, top_k)
        latency_ms = (time.perf_counter() - start) * 1000
        results = []
        for h in hits:
            c = index.chunks[h.chunk_id]
            results.append(
                SearchHit(
                    rank=h.rank,
                    score=h.score,
                    text=c.text,
                    doc_id=c.doc_id,
                    title=c.title,
                    article=c.article,
                    articles=c.articles,
                    doc_status=c.doc_status,
                    source_url=c.source_url,
                )
            )
        return SearchResponse(
            request_id=uuid.uuid4().hex,
            query=body.query,
            retriever=index.retriever.name,
            results=results,
            latency_ms=round(latency_ms, 3),
        )

    return app
