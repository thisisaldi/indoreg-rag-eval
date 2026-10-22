"""JSON logging with a per-request ID carried in a context variable."""

import json
import logging
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import IO, Any

ROOT_LOGGER = "indoreg"
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Structured fields go in `extra={"fields": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid is not None:
            payload["request_id"] = rid
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", stream: IO[str] | None = None) -> None:
    """Send all `indoreg.*` logs to one JSON handler. Safe to call more than once."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger(ROOT_LOGGER)
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(
        name if name.startswith(ROOT_LOGGER) else f"{ROOT_LOGGER}.{name}"
    )


@contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Attach a request ID (generated if not given) to log lines in the block."""
    rid = request_id or uuid.uuid4().hex
    token = request_id_var.set(rid)
    try:
        yield rid
    finally:
        request_id_var.reset(token)
