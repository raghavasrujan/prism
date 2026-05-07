"""Subprocess-based Python sandbox.

v1 implementation of ``SandboxAdapter``. Runs user code in an isolated child
Python process with:

- Wall-clock timeout (portable, via subprocess.run timeout parameter)
- POSIX: ``RLIMIT_CPU``, ``RLIMIT_AS``, ``RLIMIT_FSIZE``, ``RLIMIT_NOFILE``
- Windows dev fallback: wall-clock only (rlimit is POSIX-only)
- Fresh temp CWD per invocation
- Env stripped to an explicit allow-list
- ``args`` sent as JSON on stdin; result read as JSON from stdout

Critical Windows note
---------------------
``asyncio.create_subprocess_exec`` raises ``NotImplementedError`` on Windows
unless the event loop is a ``ProactorEventLoop``.  Uvicorn on Windows may use
a different loop.  We therefore use ``asyncio.to_thread`` + the standard
blocking ``subprocess.run``, which works on **any** event loop on any platform.
``subprocess.run`` with ``timeout=`` kills the child and raises
``subprocess.TimeoutExpired`` — no ProactorEventLoop needed.

Interface stays compatible with future container / microVM backends.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import get_settings
from app.logging_config import get_logger

_log = get_logger(__name__)

_IS_POSIX = os.name == "posix"


@dataclass
class SandboxResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    result: object | None = None
    error: str | None = None


class SandboxAdapter(Protocol):
    async def run_python(
        self,
        code: str,
        args: dict,
        *,
        runtime: str,
        timeout_s: float,
        cpu_time_s: int,
        memory_mb: int,
        network: bool,
        env: dict[str, str] | None = None,
    ) -> SandboxResult: ...


# The runner wrapper that the child process actually executes. It reads the
# user's code file path from argv, imports it, invokes ``run(args)``, and
# emits ``{"ok": bool, "result": ...}`` on the FINAL stdout line.
_RUNNER_SOURCE = '''\
import json, sys, traceback, io

def _main():
    if len(sys.argv) < 2:
        print(json.dumps({"__sandbox__": True, "ok": False, "error": "runner missing code path"}))
        sys.exit(2)
    code_path = sys.argv[1]
    with open(code_path, "r", encoding="utf-8") as fh:
        user_code = fh.read()
    ns = {"__name__": "__user_tool__"}
    try:
        exec(compile(user_code, "<user_tool>", "exec"), ns, ns)
    except Exception as exc:
        print(json.dumps({
            "__sandbox__": True, "ok": False,
            "error": f"compile/exec error: {exc}",
            "trace": traceback.format_exc(),
        }))
        sys.exit(3)
    run = ns.get("run")
    if not callable(run):
        print(json.dumps({
            "__sandbox__": True, "ok": False,
            "error": "tool must define run(args: dict) -> dict",
        }))
        sys.exit(4)
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        print(json.dumps({
            "__sandbox__": True, "ok": False, "error": f"invalid args json: {exc}",
        }))
        sys.exit(5)
    try:
        result = run(args)
    except Exception as exc:
        print(json.dumps({
            "__sandbox__": True, "ok": False,
            "error": str(exc), "trace": traceback.format_exc(),
        }))
        sys.exit(1)
    try:
        payload = json.dumps({"__sandbox__": True, "ok": True, "result": result}, default=str)
    except Exception as exc:
        payload = json.dumps({
            "__sandbox__": True, "ok": False,
            "error": f"result is not JSON serialisable: {exc}",
        })
        print(payload)
        sys.exit(6)
    print(payload)

if __name__ == "__main__":
    _main()
'''


def _apply_posix_rlimit(cpu_s: int, memory_mb: int):
    """Return a preexec_fn that applies rlimits — POSIX only."""
    import resource  # POSIX-only

    def _preexec():
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        except (ValueError, OSError):
            pass
        try:
            mem_bytes = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (25 * 1024 * 1024, 25 * 1024 * 1024))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ValueError, OSError):
            pass

    return _preexec


class SubprocessSandbox:
    """Default sandbox for v1 — subprocess + rlimit (POSIX) or wall-clock (Windows)."""

    def __init__(self, python_exe: str | None = None) -> None:
        self._python = python_exe or get_settings().sandbox_python or sys.executable

    async def run_python(
        self,
        code: str,
        args: dict,
        *,
        runtime: str = "python3.14",
        timeout_s: float = 30.0,
        cpu_time_s: int = 10,
        memory_mb: int = 256,
        network: bool = False,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        # runtime is advisory in v1; SubprocessSandbox uses configured interpreter.
        del runtime

        with tempfile.TemporaryDirectory(prefix="agent_sbx_") as tmp:
            tmp_path = Path(tmp)
            code_file = tmp_path / "user_tool.py"
            code_file.write_text(code, encoding="utf-8")
            runner_file = tmp_path / "_runner.py"
            runner_file.write_text(_RUNNER_SOURCE, encoding="utf-8")

            child_env = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows needs this
                "TEMP": tmp,
                "TMP": tmp,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "NO_COLOR": "1",
            }
            if env:
                for k, v in env.items():
                    child_env[k] = str(v)

            cmd = [self._python, "-I", "-B", str(runner_file), str(code_file)]
            input_bytes = json.dumps(args, default=str).encode("utf-8")

            # POSIX rlimit applied via preexec_fn; no-op on Windows.
            preexec = _apply_posix_rlimit(cpu_time_s, memory_mb) if _IS_POSIX else None

            start = time.perf_counter()
            _log.info(
                "tool.exec.start",
                impl_type="python_inline",
                timeout_s=timeout_s,
                memory_mb=memory_mb,
                cpu_time_s=cpu_time_s,
                network=network,
            )

            # ── Run in a thread so any event loop works (no ProactorEventLoop needed) ──
            timed_out = False
            stdout_b = b""
            stderr_b = b""
            exit_code = -1

            def _run_blocking() -> None:
                nonlocal timed_out, stdout_b, stderr_b, exit_code
                try:
                    kwargs: dict = dict(
                        input=input_bytes,
                        capture_output=True,
                        timeout=timeout_s,
                        cwd=str(tmp_path),
                        env=child_env,
                    )
                    if preexec is not None:
                        kwargs["preexec_fn"] = preexec
                    result = subprocess.run(cmd, **kwargs)
                    stdout_b = result.stdout
                    stderr_b = result.stderr
                    exit_code = result.returncode
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    stdout_b = exc.stdout or b""
                    stderr_b = exc.stderr or b""
                except FileNotFoundError:
                    stderr_b = f"sandbox python not found: {cmd[0]}".encode()
                    exit_code = -2

            try:
                await asyncio.to_thread(_run_blocking)
            except Exception as exc:  # pragma: no cover
                return SandboxResult(
                    ok=False,
                    exit_code=-1,
                    stdout="",
                    stderr=str(exc),
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    error=f"sandbox launch error: {exc}",
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")

            if timed_out:
                _log.warning("tool.exec.timeout", duration_ms=duration_ms)
                return SandboxResult(
                    ok=False,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=duration_ms,
                    timed_out=True,
                    error=f"timeout after {timeout_s}s",
                )

            if exit_code == -2:
                return SandboxResult(
                    ok=False,
                    exit_code=-2,
                    stdout="",
                    stderr=stderr,
                    duration_ms=duration_ms,
                    error=stderr,
                )

            # Runner always emits a single JSON line as its LAST stdout line.
            parsed_result: object | None = None
            parsed_ok = False
            error: str | None = None
            for line in reversed(stdout.strip().splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and parsed.get("__sandbox__") is True:
                    parsed_ok = bool(parsed.get("ok"))
                    parsed_result = parsed.get("result")
                    error = parsed.get("error")
                    break
            else:
                error = "runner produced no JSON output"

            _log.info(
                "tool.exec.finish",
                ok=parsed_ok,
                duration_ms=duration_ms,
                exit_code=exit_code,
                stdout_bytes=len(stdout),
                stderr_bytes=len(stderr),
            )

            return SandboxResult(
                ok=parsed_ok,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                timed_out=False,
                result=parsed_result,
                error=error if not parsed_ok else None,
            )


def get_sandbox() -> SandboxAdapter:
    """Factory — swap to ContainerSandbox in v2 by changing this line."""
    return SubprocessSandbox()


__all__ = [
    "SandboxAdapter",
    "SandboxResult",
    "SubprocessSandbox",
    "get_sandbox",
]
