"""Thin MCP client — HTTP JSON-RPC 2.0 transport (SSE variant is a subclass point).

Speaks the subset of MCP we need: ``initialize``, ``tools/list``, ``tools/call``.
Real MCP servers vary in strictness; this client tolerates both flat and
JSON-RPC response envelopes to interoperate with several implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class McpTool:
    name: str
    description: str | None
    input_schema: dict


class McpClientError(Exception):
    pass


class McpHttpClient:
    """Minimal MCP HTTP client. Injectable via ``transport`` for tests."""

    def __init__(
        self,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_s: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url
        self._headers = {"content-type": "application/json", **(headers or {})}
        self._timeout_s = timeout_s
        self._transport = transport
        self._req_id = 0

    async def _rpc(self, method: str, params: dict | None = None) -> Any:
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(
            timeout=self._timeout_s, transport=self._transport
        ) as client:
            try:
                resp = await client.post(self._url, json=payload, headers=self._headers)
            except httpx.HTTPError as exc:
                raise McpClientError(f"transport error: {exc}") from exc
        if resp.status_code >= 400:
            raise McpClientError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            body = resp.json()
        except ValueError as exc:
            raise McpClientError(f"non-JSON MCP response: {resp.text[:500]}") from exc

        if isinstance(body, dict) and "error" in body and body["error"]:
            err = body["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise McpClientError(f"MCP error: {msg}")
        if isinstance(body, dict) and "result" in body:
            return body["result"]
        return body  # tolerate servers that respond with raw result

    async def initialize(self) -> dict:
        return await self._rpc(
            "initialize",
            {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "agent-ui", "version": "0.1"}},
        )

    async def list_tools(self) -> list[McpTool]:
        result = await self._rpc("tools/list", {})
        raw = result.get("tools", []) if isinstance(result, dict) else result
        out: list[McpTool] = []
        for t in raw:
            name = t.get("name") or t.get("id")
            if not name:
                continue
            out.append(
                McpTool(
                    name=name,
                    description=t.get("description"),
                    input_schema=t.get("inputSchema") or t.get("input_schema") or {"type": "object"},
                )
            )
        return out

    async def call_tool(self, name: str, args: dict) -> Any:
        return await self._rpc("tools/call", {"name": name, "arguments": args})


async def discover_tools(
    *, url: str, headers: dict[str, str] | None, transport: httpx.AsyncBaseTransport | None = None
) -> list[dict]:
    """Convenience for the /refresh route — returns dicts ready for the cache."""
    client = McpHttpClient(url=url, headers=headers, transport=transport)
    tools = await client.list_tools()
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]
