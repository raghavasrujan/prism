"""HTTP tool runner + top-level dispatcher."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.logging_config import get_logger
from app.models_db.custom_tool import CustomTool, ToolImplType
from app.services.sandbox import SandboxResult, get_sandbox

_log = get_logger(__name__)


@dataclass
class ToolResult:
    ok: bool
    result: Any | None
    error: str | None
    stdout: str
    stderr: str
    duration_ms: int
    status_code: int | None = None


async def _run_http(tool: CustomTool, args: dict) -> ToolResult:
    method = (tool.method or "POST").upper()
    headers = dict(tool.headers_encrypted or {})
    headers.setdefault("content-type", "application/json")
    timeout_s = max(tool.timeout_ms / 1000, 0.5)

    start = time.perf_counter()
    _log.info(
        "tool.exec.start",
        impl_type="http",
        method=method,
        endpoint=tool.endpoint_url,
        timeout_s=timeout_s,
    )
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            resp = await client.request(
                method,
                tool.endpoint_url,
                json=args if method in {"POST", "PUT", "PATCH"} else None,
                params=args if method in {"GET", "DELETE"} else None,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            _log.warning("tool.exec.error", error=str(exc), duration_ms=duration_ms)
            return ToolResult(
                ok=False,
                result=None,
                error=str(exc),
                stdout="",
                stderr=str(exc),
                duration_ms=duration_ms,
            )
    duration_ms = int((time.perf_counter() - start) * 1000)
    body_text = resp.text
    try:
        result_data = resp.json()
    except ValueError:
        result_data = {"raw": body_text}

    ok = 200 <= resp.status_code < 300
    _log.info(
        "tool.exec.finish",
        impl_type="http",
        ok=ok,
        duration_ms=duration_ms,
        status_code=resp.status_code,
    )
    return ToolResult(
        ok=ok,
        result=result_data if ok else None,
        error=None if ok else f"HTTP {resp.status_code}: {body_text[:500]}",
        stdout=body_text[:8192],
        stderr="",
        duration_ms=duration_ms,
        status_code=resp.status_code,
    )


async def _run_python(tool: CustomTool, args: dict) -> ToolResult:
    sbx = get_sandbox()
    sr: SandboxResult = await sbx.run_python(
        tool.code_source_encrypted or "",
        args,
        runtime=(tool.runtime.value if tool.runtime else "python3.14"),
        timeout_s=tool.timeout_ms / 1000,
        cpu_time_s=tool.cpu_time_limit_s,
        memory_mb=tool.memory_limit_mb,
        network=tool.network_access,
        env=tool.allowed_env_json or None,
    )
    return ToolResult(
        ok=sr.ok,
        result=sr.result,
        error=sr.error,
        stdout=sr.stdout,
        stderr=sr.stderr,
        duration_ms=sr.duration_ms,
    )


async def execute_tool(tool: CustomTool, args: dict) -> ToolResult:
    if tool.impl_type == ToolImplType.http:
        return await _run_http(tool, args)
    if tool.impl_type == ToolImplType.python_inline:
        return await _run_python(tool, args)
    raise ValueError(f"unknown tool impl_type: {tool.impl_type}")
