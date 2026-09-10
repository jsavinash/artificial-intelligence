"""Structured JSON logging configured once per process.

Emits single-line JSON records compatible with Datadog, ELK and GCP Logging,
and injects a ``service`` field so aggregators can route per-app.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.typing import FilteringBoundLogger

_configured = False


def configure_logging(service: str, level: str = "INFO") -> None:
    """Idempotently configure structlog + stdlib logging in JSON mode."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level.upper(),
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )

    # Access logs duplicate our structured request logging.
    logging.getLogger("uvicorn.access").handlers = []
    structlog.get_logger(service=service).info("logging_configured", level=level)
    _configured = True


def get_logger(**initial_context: Any) -> FilteringBoundLogger:
    """Return a bound logger; keyword args become permanent record fields."""
    return structlog.get_logger(**initial_context)  # type: ignore[no-any-return]
