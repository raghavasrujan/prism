"""Custom tools CRUD (HTTP + Python) and sandbox execution."""

from __future__ import annotations


_ADD_TOOL_CODE = """\
def run(args):
    return {"sum": args["a"] + args["b"]}
"""

_TIMEOUT_CODE = """\
import time
def run(args):
    time.sleep(5)
    return {"never": True}
"""

_MISSING_RUN_CODE = """\
def not_run(args):
    return args
"""

_RAISES_CODE = """\
def run(args):
    raise RuntimeError("boom on purpose")
"""


def _create_python_tool(client, headers, *, code=_ADD_TOOL_CODE, name="adder", timeout_ms=5000):
    body = {
        "name": name,
        "description": "Adds two numbers",
        "impl_type": "python_inline",
        "code": code,
        "args_schema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
        "timeout_ms": timeout_ms,
        "cpu_time_limit_s": 5,
        "memory_limit_mb": 128,
    }
    return client.post("/api/v1/tools", json=body, headers=headers)


def _create_http_tool(client, headers, *, name="echo"):
    body = {
        "name": name,
        "description": "Echoes back",
        "impl_type": "http",
        "endpoint_url": "https://httpbin.example/anything",
        "method": "POST",
        "headers": {"X-App": "agent-ui"},
        "args_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
    }
    return client.post("/api/v1/tools", json=body, headers=headers)


# --------------------------------------------------------------------------- #
# CRUD (both impls)
# --------------------------------------------------------------------------- #


def test_create_python_tool(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["impl_type"] == "python_inline"
    assert body["has_code"] is True
    assert body["endpoint_url"] is None


def test_create_http_tool(client, auth_headers):
    r = _create_http_tool(client, auth_headers["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["impl_type"] == "http"
    assert body["endpoint_url"] == "https://httpbin.example/anything"
    assert body["has_headers"] is True
    assert body["has_code"] is False


def test_http_tool_missing_endpoint_rejected(client, auth_headers):
    r = client.post(
        "/api/v1/tools",
        headers=auth_headers["headers"],
        json={
            "name": "bad_http",
            "description": "no endpoint",
            "impl_type": "http",
            "args_schema": {"type": "object"},
        },
    )
    assert r.status_code == 422


def test_python_tool_missing_code_rejected(client, auth_headers):
    r = client.post(
        "/api/v1/tools",
        headers=auth_headers["headers"],
        json={
            "name": "bad_py",
            "description": "no code",
            "impl_type": "python_inline",
            "args_schema": {"type": "object"},
        },
    )
    assert r.status_code == 422


def test_duplicate_tool_name_rejected(client, auth_headers):
    r1 = _create_python_tool(client, auth_headers["headers"])
    assert r1.status_code == 201
    r2 = _create_python_tool(client, auth_headers["headers"])
    assert r2.status_code == 409


def test_invalid_tool_name_rejected(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"], name="not-a-valid-name")
    assert r.status_code == 422


def test_update_python_tool(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"])
    tid = r.json()["id"]
    r2 = client.patch(
        f"/api/v1/tools/{tid}",
        headers=auth_headers["headers"],
        json={"description": "Adds two numbers, updated"},
    )
    assert r2.status_code == 200
    assert r2.json()["description"] == "Adds two numbers, updated"


def test_delete_tool(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"])
    tid = r.json()["id"]
    r2 = client.delete(f"/api/v1/tools/{tid}", headers=auth_headers["headers"])
    assert r2.status_code == 204
    r3 = client.get("/api/v1/tools", headers=auth_headers["headers"])
    assert r3.json() == []


def test_code_encrypted_at_rest(client, auth_headers):
    import sqlite3

    r = _create_python_tool(client, auth_headers["headers"])
    tid = r.json()["id"]
    with sqlite3.connect("./data/test.db") as con:
        row = con.execute(
            "SELECT code_source_encrypted FROM custom_tools WHERE id = ?", (tid,)
        ).fetchone()
    assert row is not None and row[0] is not None
    # Plaintext must not appear literally in the ciphertext.
    assert "def run(args):" not in row[0]


# --------------------------------------------------------------------------- #
# Sandbox execution (Python)
# --------------------------------------------------------------------------- #


def test_python_tool_test_happy_path(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"])
    tid = r.json()["id"]
    r2 = client.post(
        f"/api/v1/tools/{tid}/test",
        headers=auth_headers["headers"],
        json={"args": {"a": 2, "b": 3}},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["ok"] is True
    assert body["result"] == {"sum": 5}
    assert body["duration_ms"] >= 0


def test_python_tool_missing_run_function(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"], code=_MISSING_RUN_CODE, name="norun")
    tid = r.json()["id"]
    r2 = client.post(
        f"/api/v1/tools/{tid}/test",
        headers=auth_headers["headers"],
        json={"args": {}},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["ok"] is False
    assert body["error"] and "run(args" in body["error"]


def test_python_tool_raises_exception(client, auth_headers):
    r = _create_python_tool(client, auth_headers["headers"], code=_RAISES_CODE, name="boomer")
    tid = r.json()["id"]
    r2 = client.post(
        f"/api/v1/tools/{tid}/test",
        headers=auth_headers["headers"],
        json={"args": {}},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["ok"] is False
    assert "boom on purpose" in body["error"]


def test_python_tool_wall_clock_timeout(client, auth_headers):
    r = _create_python_tool(
        client, auth_headers["headers"], code=_TIMEOUT_CODE, name="slow", timeout_ms=500
    )
    tid = r.json()["id"]
    r2 = client.post(
        f"/api/v1/tools/{tid}/test",
        headers=auth_headers["headers"],
        json={"args": {}},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["ok"] is False
    assert body["error"] and "timeout" in body["error"].lower()
