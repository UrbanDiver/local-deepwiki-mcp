"""Web server lifecycle handlers: serve_wiki and stop_wiki_server."""

from __future__ import annotations

import asyncio
import atexit
import os
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    Permission,
    ServeWikiArgs,
    StopWikiServerArgs,
    ValidationError,
    get_access_controller,
    handle_tool_errors,
    logger,
    make_tool_text_content,
    path_not_found_error,
)

# --- Security: loopback-only host restriction ---
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# --- DoS prevention: cap concurrent servers ---
MAX_CONCURRENT_SERVERS = 5

SERVER_STARTUP_TIMEOUT = 10
HEALTH_CHECK_INTERVAL = 0.3


@dataclass(frozen=True)
class RunningServer:
    """Immutable record of a running wiki server process."""

    process: subprocess.Popen
    wiki_path: str
    host: str
    port: int
    pid: int
    url: str
    started_at: float


# Registry keyed by port. Port is the right key because OS enforces port uniqueness.
_running_servers: dict[int, RunningServer] = {}

# --- Race condition prevention ---
_registry_lock = asyncio.Lock()


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already bound on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


async def _wait_for_server_ready(host: str, port: int, timeout: float) -> bool:
    """Poll until the server is accepting connections or timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if _is_port_in_use(host, port):
            return True
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    return False


def _build_safe_env() -> dict[str, str]:
    """Build a sanitized env for the subprocess.

    Prevents leaking API keys, DB passwords, etc. to the child process.
    """
    return {
        k: os.environ[k]
        for k in ("PATH", "HOME", "LANG", "PYTHONPATH", "VIRTUAL_ENV")
        if os.environ.get(k)
    }


def _validate_wiki_path(raw_path: str) -> Path:
    """Validate wiki_path for null bytes, option injection, and existence."""
    if "\x00" in raw_path:
        raise ValueError("wiki_path contains null byte")
    if raw_path.lstrip().startswith("-"):
        raise ValueError("wiki_path must not start with '-'")

    resolved = Path(raw_path).resolve()

    if not resolved.exists():
        raise path_not_found_error(str(resolved), "wiki directory")
    if not resolved.is_dir():
        raise ValidationError(
            message=f"Path is not a directory: {resolved}",
            hint="Provide a path to a .deepwiki directory.",
            field="wiki_path",
            value=str(resolved),
        )
    return resolved


def _prune_dead_servers() -> None:
    """Remove entries for processes that have already exited."""
    dead_ports = [p for p, s in _running_servers.items() if s.process.poll() is not None]
    for port in dead_ports:
        del _running_servers[port]


# --- Orphan cleanup on MCP server exit ---
def _cleanup_all_servers() -> None:
    """Terminate all tracked servers. Registered via atexit."""
    for server_info in list(_running_servers.values()):
        try:
            server_info.process.terminate()
            server_info.process.wait(timeout=3)
        except Exception:
            try:
                server_info.process.kill()
            except Exception:
                pass
    _running_servers.clear()


atexit.register(_cleanup_all_servers)


# --- Test helpers ---
def _get_running_servers() -> dict[int, RunningServer]:
    """Return a shallow copy of the running servers registry (for testing)."""
    return dict(_running_servers)


def _clear_running_servers() -> None:
    """Clear the running servers registry (for testing)."""
    _running_servers.clear()


@handle_tool_errors
async def handle_serve_wiki(args: dict[str, Any]) -> list[TextContent]:
    """Start the Flask wiki web server as a subprocess."""
    get_access_controller().require_permission(Permission.SYSTEM_ADMIN)

    try:
        validated = ServeWikiArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    # Host restriction - loopback only
    if validated.host not in ALLOWED_HOSTS:
        raise ValueError(
            f"Host must be a loopback address ({', '.join(sorted(ALLOWED_HOSTS))}), "
            f"got: {validated.host!r}"
        )

    # Path validation - null bytes, option injection, existence
    wiki_path = _validate_wiki_path(validated.wiki_path)
    host = validated.host
    port = validated.port

    # Warn if wiki has no content (but don't block)
    if not (wiki_path / "index.md").exists():
        logger.warning("Wiki directory has no index.md: %s", wiki_path)

    # Concurrent server limit
    _prune_dead_servers()
    if len(_running_servers) >= MAX_CONCURRENT_SERVERS:
        raise ValueError(
            f"Maximum concurrent servers ({MAX_CONCURRENT_SERVERS}) reached. "
            f"Stop an existing server first."
        )

    # asyncio.Lock prevents TOCTOU race between port check and registration
    async with _registry_lock:
        # Check registry for existing server on this port
        existing = _running_servers.get(port)
        if existing is not None:
            if existing.process.poll() is None:
                return make_tool_text_content("serve_wiki", {
                    "status": "already_running",
                    "message": f"Wiki server already running on port {port}",
                    "url": existing.url,
                    "pid": existing.pid,
                    "wiki_path": existing.wiki_path,
                })
            del _running_servers[port]

        # Check port not in use by external process
        if await asyncio.to_thread(_is_port_in_use, host, port):
            raise ValidationError(
                message=f"Port {port} is already in use",
                hint=f"Choose a different port or stop the process using port {port}.",
                field="port",
                value=str(port),
            )

        # Sanitized env - no API keys/DB passwords leak to child
        safe_env = _build_safe_env()

        # Spawn subprocess
        process = await asyncio.to_thread(
            subprocess.Popen,
            [sys.executable, "-m", "local_deepwiki.web.app",
             str(wiki_path), "--host", host, "--port", str(port)],
            shell=False,
            env=safe_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to accept connections
        url = f"http://{host}:{port}"
        ready = await _wait_for_server_ready(host, port, SERVER_STARTUP_TIMEOUT)

        if not ready:
            # Read stderr for diagnostics on failure
            if process.poll() is not None:
                stderr_out = ""
                if process.stderr:
                    stderr_out = process.stderr.read().decode("utf-8", errors="replace")[:500]
                raise ValidationError(
                    message=f"Wiki server exited with code {process.returncode}",
                    hint=f"Check Flask is installed and wiki path is valid. stderr: {stderr_out}",
                    field="wiki_path",
                    value=str(wiki_path),
                )
            logger.warning(
                "Server started but not accepting connections after %ds",
                SERVER_STARTUP_TIMEOUT,
            )

        # Register in registry (immutable record)
        _running_servers[port] = RunningServer(
            process=process,
            wiki_path=str(wiki_path),
            host=host,
            port=port,
            pid=process.pid,
            url=url,
            started_at=time.time(),
        )

    logger.info("Wiki server started: pid=%d, url=%s", process.pid, url)

    # open_browser defaults to False; wrapped in try/except for headless environments
    if validated.open_browser:
        try:
            await asyncio.to_thread(webbrowser.open, url)
        except Exception as e:
            logger.warning("Failed to open browser: %s", e)

    return make_tool_text_content(
        "serve_wiki",
        {
            "status": "started",
            "message": f"Wiki server started at {url}",
            "url": url,
            "pid": process.pid,
            "wiki_path": str(wiki_path),
            "host": host,
            "port": port,
        },
        hints={
            "open_in_browser": url,
            "stop_command": f"Use stop_wiki_server with port={port} to stop",
        },
    )


@handle_tool_errors
async def handle_stop_wiki_server(args: dict[str, Any]) -> list[TextContent]:
    """Stop a previously started wiki server subprocess."""
    get_access_controller().require_permission(Permission.SYSTEM_ADMIN)

    try:
        validated = StopWikiServerArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    port = validated.port
    server_record = _running_servers.get(port)

    if server_record is None:
        running = {
            str(p): {"wiki_path": s.wiki_path, "url": s.url, "pid": s.pid}
            for p, s in _running_servers.items()
            if s.process.poll() is None
        }
        return make_tool_text_content("stop_wiki_server", {
            "status": "not_found",
            "message": f"No wiki server found on port {port}",
            "running_servers": running,
        })

    # Optional wiki_path filter
    if validated.wiki_path is not None:
        resolved_filter = str(Path(validated.wiki_path).resolve())
        if server_record.wiki_path != resolved_filter:
            return make_tool_text_content("stop_wiki_server", {
                "status": "not_found",
                "message": (
                    f"Server on port {port} serves {server_record.wiki_path}, "
                    f"not {resolved_filter}"
                ),
            })

    if server_record.process.poll() is not None:
        del _running_servers[port]
        return make_tool_text_content("stop_wiki_server", {
            "status": "already_stopped",
            "message": (
                f"Server on port {port} had already exited "
                f"(code {server_record.process.returncode})"
            ),
        })

    # Graceful terminate, then force kill if needed
    logger.info("Stopping wiki server: pid=%d, port=%d", server_record.pid, port)
    server_record.process.terminate()
    try:
        await asyncio.to_thread(server_record.process.wait, timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("Server did not stop gracefully, sending SIGKILL")
        server_record.process.kill()
        await asyncio.to_thread(server_record.process.wait, timeout=3)

    del _running_servers[port]
    logger.info("Wiki server stopped: pid=%d, port=%d", server_record.pid, port)

    return make_tool_text_content("stop_wiki_server", {
        "status": "stopped",
        "message": f"Wiki server on port {port} has been stopped",
        "pid": server_record.pid,
        "wiki_path": server_record.wiki_path,
    })
