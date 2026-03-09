# Copyright (c) 2026
"""Structured logging configuration for Instagram scraper.

Provides JSON-formatted logging with context binding for observability.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self, TextIO, cast

# Context variables for request-scoped logging
_context_vars: dict[str, ContextVar[str | None]] = {}


@dataclass
class JSONFormatter(logging.Formatter):
    """JSON formatter for structured log output.

    Outputs logs as single-line JSON objects suitable for log aggregation
    systems like Elasticsearch, Loki, or CloudWatch.
    """

    include_extra: bool = True

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to format.

        Returns
        -------
        str
            JSON-formatted log line.

        """
        log_data: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add context from ContextVar
        for key, ctx_var in _context_vars.items():
            value = ctx_var.get(None)
            if value is not None:
                log_data[key] = value

        # Add extra fields from record
        if self.include_extra:
            extra = {
                k: v
                for k, v in record.__dict__.items()
                if k
                not in {
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "message",
                    "asctime",
                }
                and not k.startswith("_")
            }
            if extra:
                log_data["extra"] = extra

        return json.dumps(log_data, ensure_ascii=False, default=str)


def configure_logging(
    level: str = "INFO",
    *,
    json_format: bool = True,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure root logger with structured output.

    Parameters
    ----------
    level : str
        Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    json_format : bool
        Use JSON formatter for structured output.
    stream : object | None
        Output stream (defaults to sys.stderr).

    Returns
    -------
    logging.Logger
        Configured root logger.

    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    out_stream = stream if stream is not None else sys.stderr
    handler = logging.StreamHandler(out_stream)  # type: ignore[arg-type]
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ),
        )

    root_logger.addHandler(handler)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Parameters
    ----------
    name : str
        Logger name (typically __name__).

    Returns
    -------
    logging.Logger
        Configured logger instance.

    """
    return logging.getLogger(name)


@dataclass
class LogContext:
    """Context manager for adding fields to all log records within scope.

    Uses ContextVar for thread-safe, async-safe context propagation.

    Examples
    --------
    >>> with LogContext(request_id="abc123"):
    ...     logger.info("processing")  # includes request_id

    Attributes
    ----------
    **fields : str
        Key-value pairs to add to log context.

    """

    _fields: dict[str, str | None] = field(default_factory=dict)
    _tokens: dict[str, object] = field(default_factory=dict, init=False)

    def __init__(self, **fields: str | None) -> None:
        """Initialize LogContext with given fields."""
        self._fields = fields
        self._tokens = {}

    def __enter__(self) -> Self:
        """Enter context and bind fields to ContextVars.

        Returns
        -------
        LogContext
            This context instance.

        """
        for key, value in self._fields.items():
            if key not in _context_vars:
                _context_vars[key] = ContextVar(f"log_context_{key}", default=None)
            self._tokens[key] = _context_vars[key].set(value)
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context and reset ContextVars."""
        for key in self._fields:
            if key in self._tokens:
                token = cast("Any", self._tokens[key])
                _context_vars[key].reset(token)
