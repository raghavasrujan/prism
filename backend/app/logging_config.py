"""Structured JSON logging (structlog) with file + optional stdout sinks.

Every log record carries top-level `request_id`, `user`, `user_id`,
`conversation_id` fields so `grep -E '"request_id":"..."'` reconstructs a
single turn. Swap the file sink for cloud (App Insights / GCP) by changing
only this module.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import socket
import sys
from pathlib import Path

import structlog

from app.context import (
    conversation_id_var,
    request_id_var,
    user_email_var,
    user_id_var,
)

_CONFIGURED = False

_SECRET_KEYS = {
    "password",
    "api_key",
    "authorization",
    "x-api-key",
    "secret",
    "token",
    "refresh",
    "master_key",
    "jwt_secret",
    "code_source",
    "code",
}


def _scrub_secrets(_logger, _name, event_dict):
    """Redact sensitive-looking keys before serialisation."""
    for k in list(event_dict.keys()):
        if k.lower() in _SECRET_KEYS:
            event_dict[k] = "***"
    return event_dict


def _merge_correlation(_logger, _name, event_dict):
    if "request_id" not in event_dict:
        v = request_id_var.get()
        if v is not None:
            event_dict["request_id"] = v
    if "user_id" not in event_dict:
        v = user_id_var.get()
        if v is not None:
            event_dict["user_id"] = v
    if "user" not in event_dict:
        v = user_email_var.get()
        if v is not None:
            event_dict["user"] = v
    if "conversation_id" not in event_dict:
        v = conversation_id_var.get()
        if v is not None:
            event_dict["conversation_id"] = v
    return event_dict


def _add_static_fields(_logger, _name, event_dict):
    event_dict.setdefault("service", "agent-ui-api")
    event_dict.setdefault("host", socket.gethostname())
    event_dict.setdefault("pid", os.getpid())
    return event_dict


def configure_logging(
    *,
    log_level: str = "INFO",
    log_dir: str = "./logs",
    log_to_stdout: bool = True,
) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # Path(log_dir).mkdir(parents=True, exist_ok=True)
    # host = socket.gethostname()
    # pid = os.getpid()

    # app_log_path = Path(log_dir) / f"app-{host}-{pid}.log"
    # err_log_path = Path(log_dir) / f"error-{host}-{pid}.log"

    handlers: list[logging.Handler] = []

    # file_handler = logging.handlers.RotatingFileHandler(
    #     app_log_path,
    #     maxBytes=50 * 1024 * 1024,
    #     backupCount=20,
    #     encoding="utf-8",
    # )
    # file_handler.setLevel(log_level)
    # file_handler.setFormatter(logging.Formatter("%(message)s"))
    # handlers.append(file_handler)

    # err_handler = logging.handlers.RotatingFileHandler(
    #     err_log_path,
    #     maxBytes=50 * 1024 * 1024,
    #     backupCount=10,
    #     encoding="utf-8",
    # )
    # err_handler.setLevel("ERROR")
    # err_handler.setFormatter(logging.Formatter("%(message)s"))
    # handlers.append(err_handler)

    if log_to_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(log_level)
        stdout_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(stdout_handler)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    # Tame noisy libs; they still go through the same JSON sink.
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _merge_correlation,
            _add_static_fields,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _scrub_secrets,
            structlog.processors.JSONRenderer(sort_keys=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
