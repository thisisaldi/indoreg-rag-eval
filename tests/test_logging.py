import io
import json

from indoreg.logging import configure_logging, get_logger, request_context


def lines(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(x) for x in buf.getvalue().splitlines()]


def test_json_lines_with_request_id_and_fields() -> None:
    buf = io.StringIO()
    configure_logging("INFO", stream=buf)
    log = get_logger("test")
    log.info("outside")
    with request_context("abc123") as rid:
        log.info("search done", extra={"fields": {"top_k": 5, "latency_ms": 12}})
    out = lines(buf)
    assert rid == "abc123"
    assert "request_id" not in out[0]
    assert out[1]["request_id"] == "abc123"
    assert out[1]["msg"] == "search done"
    assert out[1]["top_k"] == 5
    assert out[1]["logger"] == "indoreg.test"
    assert out[1]["level"] == "INFO"


def test_generated_request_id_and_exception() -> None:
    buf = io.StringIO()
    configure_logging("INFO", stream=buf)
    log = get_logger("indoreg.test")
    with request_context() as rid:
        try:
            raise ValueError("boom")
        except ValueError:
            log.exception("failed")
    (rec,) = lines(buf)
    assert rec["request_id"] == rid and len(rid) == 32
    assert "ValueError: boom" in str(rec["exc"])


def test_level_filters() -> None:
    buf = io.StringIO()
    configure_logging("WARNING", stream=buf)
    get_logger("test").info("hidden")
    assert buf.getvalue() == ""
