"""MCP servers CRUD + tool discovery (mocked JSON-RPC transport)."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx


def _create_mcp(client, headers, *, name="filesystem", url="https://mcp.example/rpc"):
    return client.post(
        "/api/v1/mcp",
        headers=headers,
        json={"name": name, "transport": "http", "url": url, "headers": {"X-Auth": "abc"}},
    )


def test_create_and_list_mcp(client, auth_headers):
    r = _create_mcp(client, auth_headers["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "filesystem"
    assert body["has_headers"] is True
    assert body["last_probe_ok"] is None

    r2 = client.get("/api/v1/mcp", headers=auth_headers["headers"])
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_duplicate_mcp_name_rejected(client, auth_headers):
    _create_mcp(client, auth_headers["headers"])
    r2 = _create_mcp(client, auth_headers["headers"])
    assert r2.status_code == 409


def test_delete_mcp(client, auth_headers):
    r = _create_mcp(client, auth_headers["headers"])
    sid = r.json()["id"]
    r2 = client.delete(f"/api/v1/mcp/{sid}", headers=auth_headers["headers"])
    assert r2.status_code == 204
    assert client.get("/api/v1/mcp", headers=auth_headers["headers"]).json() == []


def test_headers_encrypted_at_rest(client, auth_headers):
    import sqlite3

    r = _create_mcp(client, auth_headers["headers"])
    sid = r.json()["id"]
    with sqlite3.connect("./data/test.db") as con:
        row = con.execute(
            "SELECT headers_encrypted FROM mcp_servers WHERE id = ?", (sid,)
        ).fetchone()
    assert row is not None and row[0] is not None
    assert "abc" not in row[0]  # X-Auth value should not be visible in ciphertext


# --------------------------------------------------------------------------- #
# Refresh (tool discovery) with a MOCK MCP server
# --------------------------------------------------------------------------- #


def _make_transport(response_body: dict, status_code: int = 200):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=response_body)

    return httpx.MockTransport(_handler)


def test_refresh_discovers_tools(client, auth_headers):
    r = _create_mcp(client, auth_headers["headers"])
    sid = r.json()["id"]

    mock_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {
                    "name": "list_files",
                    "description": "List files in a directory",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
                {"name": "read_file", "inputSchema": {"type": "object"}},
            ]
        },
    }

    transport = _make_transport(mock_response)
    with patch("app.routers.mcp.discover_tools") as mock_discover:
        # Delegate to the real function but with our mock transport injected
        from app.services.mcp_client import discover_tools as real

        async def _wrapped(url, headers):  # type: ignore[override]
            return await real(url=url, headers=headers, transport=transport)

        mock_discover.side_effect = _wrapped
        r2 = client.post(f"/api/v1/mcp/{sid}/refresh", headers=auth_headers["headers"])

    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["ok"] is True
    assert len(body["tools"]) == 2
    assert {t["tool_name"] for t in body["tools"]} == {"list_files", "read_file"}


def test_refresh_handles_error_response(client, auth_headers):
    r = _create_mcp(client, auth_headers["headers"])
    sid = r.json()["id"]

    err_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32601, "message": "method not found"},
    }

    transport = _make_transport(err_response)
    with patch("app.routers.mcp.discover_tools") as mock_discover:
        from app.services.mcp_client import discover_tools as real

        async def _wrapped(url, headers):
            return await real(url=url, headers=headers, transport=transport)

        mock_discover.side_effect = _wrapped
        r2 = client.post(f"/api/v1/mcp/{sid}/refresh", headers=auth_headers["headers"])

    assert r2.status_code == 200
    body = r2.json()
    assert body["ok"] is False
    assert "method not found" in (body["error"] or "")


def test_refresh_records_probe_state(client, auth_headers):
    r = _create_mcp(client, auth_headers["headers"])
    sid = r.json()["id"]

    transport = _make_transport({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
    with patch("app.routers.mcp.discover_tools") as mock_discover:
        from app.services.mcp_client import discover_tools as real

        async def _wrapped(url, headers):
            return await real(url=url, headers=headers, transport=transport)

        mock_discover.side_effect = _wrapped
        client.post(f"/api/v1/mcp/{sid}/refresh", headers=auth_headers["headers"])

    r_get = client.get(f"/api/v1/mcp/{sid}", headers=auth_headers["headers"])
    body = r_get.json()
    assert body["last_probe_ok"] is True
    assert body["last_probed_at"] is not None
