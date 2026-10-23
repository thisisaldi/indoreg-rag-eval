import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from indoreg.api.app import create_app
from indoreg.api.models import DISCLAIMER, SearchResponse
from indoreg.config import load_settings
from indoreg.retrieval.base import RetrievalResult
from indoreg.schemas import Chunk

REPO_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


def chunk(n: int) -> Chunk:
    return Chunk(
        chunk_id=f"uu:article:{n}",
        doc_id="uu",
        title="Undang-Undang Contoh",
        strategy="article",
        article=str(n),
        chapter=None,
        articles=[str(n)],
        char_start=0,
        char_end=4,
        text=f"isi pasal {n}",
        source_url="https://example.org/uu",
        doc_status="in_force",
    )


CHUNKS = [chunk(n) for n in range(1, 31)]


class Stub:
    """Returns chunks in id order; records the last query."""

    name = "stub"

    def __init__(self) -> None:
        self.ids: list[str] = []
        self.last: tuple[str, int] | None = None

    def build(self, chunks: Sequence[Chunk]) -> None:
        self.ids = [c.chunk_id for c in chunks]

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        self.last = (query, top_k)
        return [
            RetrievalResult(chunk_id=c, score=1.0 / r, rank=r)
            for r, c in enumerate(self.ids[:top_k], 1)
        ]


@pytest.fixture
def stub() -> Stub:
    return Stub()


@pytest.fixture
def client(stub: Stub) -> Iterator[TestClient]:
    app = create_app(load_settings(REPO_CONFIG), retriever=stub, chunks=CHUNKS)
    with TestClient(app) as c:
        yield c


def test_search_returns_cited_results_and_disclaimer(
    client: TestClient, stub: Stub
) -> None:
    r = client.post("/search", json={"query": "  transfer data  ", "top_k": 3})
    assert r.status_code == 200
    body = SearchResponse.model_validate(r.json())
    assert stub.last == ("transfer data", 3)  # stripped before retrieval
    assert [h.rank for h in body.results] == [1, 2, 3]
    hit = body.results[0]
    assert (hit.doc_id, hit.article, hit.doc_status) == ("uu", "1", "in_force")
    assert hit.source_url == "https://example.org/uu" and hit.title
    assert body.disclaimer == DISCLAIMER and body.retriever == "stub"
    assert body.request_id and body.latency_ms >= 0


def test_top_k_defaults_to_config(client: TestClient, stub: Stub) -> None:
    r = client.post("/search", json={"query": "data"})
    assert r.status_code == 200 and len(r.json()["results"]) == 5
    assert stub.last == ("data", 5)


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"query": ""}, "query"),
        ({"query": "   \n\t"}, "query"),
        ({"query": "x" * 501}, "query"),
        ({"query": "data", "top_k": 0}, "top_k"),
        ({"query": "data", "top_k": 21}, "top_k"),
        ({"query": "data", "top_k": "lima"}, "top_k"),
        ({"top_k": 5}, "query"),
    ],
)
def test_invalid_requests_return_422(
    client: TestClient, payload: dict, field: str
) -> None:
    r = client.post("/search", json=payload)
    assert r.status_code == 422
    assert any(e["loc"][-1] == field for e in r.json()["detail"])


def test_query_at_the_limit_is_accepted(client: TestClient) -> None:
    assert client.post("/search", json={"query": "x" * 500}).status_code == 200


def test_health_reports_index(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["retriever"] == "stub"
    assert body["chunks"] == 30 and body["strategy"] == "article"
    assert body["index_built_at"]


def test_openapi_docs_render(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert {"/search", "/health"} <= set(spec["paths"])
    assert client.get("/docs").status_code == 200


def log_lines(err: str) -> list[dict]:
    return [json.loads(x) for x in err.splitlines() if x.startswith("{")]


def make_client(stub: Stub) -> TestClient:
    return TestClient(create_app(load_settings(REPO_CONFIG), stub, CHUNKS))


def test_request_id_header_body_and_logs(
    stub: Stub, capsys: pytest.CaptureFixture[str]
) -> None:
    with make_client(stub) as c:
        r = c.post("/search", json={"query": "rahasia pribadi"})
        mine = c.get("/health", headers={"X-Request-ID": "trace-42"})
        bad = c.get("/health", headers={"X-Request-ID": "x y\n{evil}"})
    rid = r.headers["X-Request-ID"]
    assert r.json()["request_id"] == rid and len(rid) == 32
    assert mine.headers["X-Request-ID"] == "trace-42"
    assert bad.headers["X-Request-ID"] != "x y\n{evil}"
    logs = log_lines(capsys.readouterr().err)
    search = next(x for x in logs if x["msg"] == "search")
    request = next(x for x in logs if x["msg"] == "request" and x["request_id"] == rid)
    assert search["request_id"] == rid and search["query_chars"] == 15
    assert "query" not in search  # query text is off by default
    assert request["status"] == 200 and request["path"] == "/search"
    assert request["latency_ms"] >= 0
    assert all("rahasia" not in json.dumps(x) for x in logs)


def test_query_text_logged_only_when_enabled(
    stub: Stub, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INDOREG_LOGGING__LOG_QUERY_TEXT", "true")
    with make_client(stub) as c:
        c.post("/search", json={"query": "rahasia pribadi"})
    search = next(x for x in log_lines(capsys.readouterr().err) if x["msg"] == "search")
    assert search["query"] == "rahasia pribadi"


def test_unhandled_error_is_500_with_request_id_and_no_trace(
    stub: Stub, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(query: str, top_k: int) -> list[RetrievalResult]:
        raise RuntimeError("index exploded")

    monkeypatch.setattr(stub, "search", boom)
    with make_client(stub) as c:
        r = c.post("/search", json={"query": "data"})
    assert r.status_code == 500
    assert r.json() == {
        "detail": "internal server error",
        "request_id": r.headers["X-Request-ID"],
    }
    assert "exploded" not in r.text
    err = next(x for x in log_lines(capsys.readouterr().err) if "exc" in x)
    assert "index exploded" in err["exc"]


def test_bad_config_exits_with_a_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INDOREG_CONFIG", str(tmp_path / "missing.yaml"))
    with pytest.raises(SystemExit, match="invalid configuration: config file"):
        create_app()
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        REPO_CONFIG.read_text(encoding="utf-8").replace(
            "max_top_k: 20", "max_top_k: -1"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("INDOREG_CONFIG", str(bad))
    with pytest.raises(SystemExit, match="invalid configuration"):
        create_app()


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    ok = "https://naufaldi.vercel.app"  # configs/default.yaml search.cors_origins
    pre = client.options(
        "/search",
        headers={
            "Origin": ok,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == ok
    r = client.post("/search", json={"query": "data"}, headers={"Origin": ok})
    assert r.headers["access-control-allow-origin"] == ok
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()
    other = client.post(
        "/search", json={"query": "data"}, headers={"Origin": "https://evil.example"}
    )
    assert "access-control-allow-origin" not in other.headers
