"""Structured (JSON) logging plus per-request context.

Both the Django app and the FastAPI service emit the same shape so a single
log pipeline can index them together::

    {"ts": "...", "level": "INFO", "logger": "ai_client", "message": "...",
     "request_id": "9f2c...", "path": "/api/v1/ai/caption/", "user": "rajeev",
     "duration_ms": 42.1, "event": "ai.caption.request"}
"""
from __future__ import annotations

import json
import logging
import traceback
from contextvars import ContextVar
from typing import Any

# Populated by RequestLogMiddleware (Django) / middleware (FastAPI).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
request_path_var: ContextVar[str | None] = ContextVar("request_path", default=None)
request_user_var: ContextVar[str | None] = ContextVar("request_user", default=None)

# Reserved LogRecord attributes that must not be duplicated as "extra" fields.
_RESERVED = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "message", "module", "msecs", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info",
        "thread", "threadName", "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    """Render a LogRecord as a single line of JSON."""

    def __init__(self, timestamp_format: str = "%Y-%m-%dT%H:%M:%S%z") -> None:
        super().__init__()
        self.timestamp_format = timestamp_format

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.timestamp_format),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class RequestContextFilter(logging.Filter):
    """Attach request-scoped context to every record, including third-party ones."""

    def filter(self, record: logging.LogRecord) -> bool:
        for attr, var in (
            ("request_id", request_id_var),
            ("path", request_path_var),
            ("user", request_user_var),
        ):
            if not hasattr(record, attr):
                value = var.get()
                if value is not None:
                    setattr(record, attr, value)
        return True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
