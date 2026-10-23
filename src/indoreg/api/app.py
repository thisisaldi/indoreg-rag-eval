"""FastAPI app: POST /search and GET /health over one retriever (design.md 5).

The retriever is built once in the lifespan and shared read-only by requests;
it is the same Retriever the eval runner benchmarks. Tests inject a stub.

Every request gets an ID (a well-formed incoming X-Request-ID, else a new
one), returned in the X-Request-ID header and attached to its log lines (T-25).

Run locally: uv run uvicorn indoreg.api.app:create_app --factory
"""

import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from indoreg.api.models import (
    HealthResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from indoreg.config import ConfigError, Settings, load_settings
from indoreg.logging import (
    configure_logging,
    get_logger,
    request_context,
    request_id_var,
)
from indoreg.retrieval.base import Retriever
from indoreg.retrieval.registry import build_retriever
from indoreg.schemas import Chunk
from indoreg.search import load_chunks

log = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
# Incoming IDs are untrusted: accept only short tokens, never raw text into logs.
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


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
    if settings is None:
        try:
            settings = load_settings()
        except ConfigError as e:
            # Fail fast with one clear line instead of a traceback (T-25).
            raise SystemExit(f"invalid configuration: {e}") from None
    configure_logging(settings.logging.level)
    cfg = settings.search
    log_query_text = settings.logging.log_query_text

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

    @app.middleware("http")
    async def request_id_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        with request_context(incoming if SAFE_ID.fullmatch(incoming) else None) as rid:
            start = time.perf_counter()
            try:
                response = await call_next(request)
            except Exception:
                # No stack trace in the body (design.md 4.7); it goes to the log.
                log.exception("unhandled error")
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "internal server error", "request_id": rid},
                )
            response.headers[REQUEST_ID_HEADER] = rid
            log.info(
                "request",
                extra={
                    "fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 3),
                    }
                },
            )
            return response

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
        fields: dict[str, object] = {
            "retriever": index.retriever.name,
            "query_chars": len(body.query),
            "top_k": top_k,
            "results": len(hits),
            "retrieval_ms": round(latency_ms, 3),
        }
        if log_query_text:  # off by default: queries may be sensitive (design 10)
            fields["query"] = body.query
        log.info("search", extra={"fields": fields})
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
            request_id=request_id_var.get() or "",
            query=body.query,
            retriever=index.retriever.name,
            results=results,
            latency_ms=round(latency_ms, 3),
        )

    return app
