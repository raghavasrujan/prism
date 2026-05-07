"""Middleware — request-id + structured request logging."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.context import bind, snapshot
from app.logging_config import get_logger
from app.security import new_uuid

_log = get_logger("http")

_HEADER = "X-Request-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign / accept X-Request-Id and log start + finish for every request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(_HEADER)
        request_id = incoming if incoming else new_uuid()
        bind(request_id=request_id, user_id=None, user_email=None, conversation_id=None)

        start = time.perf_counter()
        _log.info(
            "http.request.start",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query) or None,
            client=request.client.host if request.client else None,
        )
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            ctx = snapshot()
            _log.info(
                "http.request.finish",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=duration_ms,
                **{k: v for k, v in ctx.items() if v is not None},
            )

    @staticmethod
    def header_name() -> str:
        return _HEADER


class ResponseRequestIdMiddleware(BaseHTTPMiddleware):
    """Echo the current request_id back on every response header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        ctx = snapshot()
        rid = ctx.get("request_id")
        if rid:
            response.headers[_HEADER] = rid
        return response
