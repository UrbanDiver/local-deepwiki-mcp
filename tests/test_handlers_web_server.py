"""Tests for web server lifecycle handlers: serve_wiki and stop_wiki_server."""

from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.handlers.web_server import (
    MAX_CONCURRENT_SERVERS,
    RunningServer,
    _clear_running_servers,
    _get_running_servers,
    _is_port_in_use,
    _running_servers,
    _validate_wiki_path,
    handle_serve_wiki,
    handle_stop_wiki_server,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_server_registry():
    """Ensure the server registry is clean before and after each test."""
    _clear_running_servers()
    yield
    for server in _get_running_servers().values():
        try:
            server.process.terminate()
        except Exception:
            pass
    _clear_running_servers()


@pytest.fixture()
def wiki_dir(tmp_path: Path) -> Path:
    """Create a temporary wiki directory with an index.md."""
    wiki = tmp_path / ".deepwiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("# Test Wiki")
    return wiki


def _make_mock_process(*, alive: bool = True, returncode: int = 0) -> MagicMock:
    """Create a mock subprocess.Popen with controllable poll() behavior."""
    proc = MagicMock()
    proc.pid = 12345
    proc.returncode = None if alive else returncode
    proc.poll.return_value = None if alive else returncode
    proc.stderr = MagicMock()
    proc.stderr.read.return_value = b""
    proc.stdout = MagicMock()
    proc.wait = MagicMock()
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    return proc


def _register_server(
    port: int,
    wiki_path: str = "/tmp/wiki",
    *,
    alive: bool = True,
    host: str = "127.0.0.1",
) -> RunningServer:
    """Register a mock server in the registry."""
    proc = _make_mock_process(alive=alive)
    record = RunningServer(
        process=proc,
        wiki_path=wiki_path,
        host=host,
        port=port,
        pid=proc.pid,
        url=f"http://{host}:{port}",
        started_at=time.time(),
    )
    _running_servers[port] = record
    return record


# ---------------------------------------------------------------------------
# _is_port_in_use tests
# ---------------------------------------------------------------------------

class TestIsPortInUse:
    """Tests for the _is_port_in_use helper."""

    def test_bound_socket_returns_true(self):
        """A port with a listening socket should return True."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            _, port = sock.getsockname()
            assert _is_port_in_use("127.0.0.1", port) is True

    def test_unused_port_returns_false(self):
        """A high unused port should return False."""
        assert _is_port_in_use("127.0.0.1", 59999) is False

    def test_socket_error_handling(self):
        """connect_ex raising OSError should be handled gracefully."""
        with patch("local_deepwiki.handlers.web_server.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock.__exit__ = MagicMock(return_value=False)
            mock_sock.connect_ex.side_effect = OSError("mocked")
            mock_sock_cls.return_value = mock_sock

            with pytest.raises(OSError):
                _is_port_in_use("127.0.0.1", 8080)


# ---------------------------------------------------------------------------
# _validate_wiki_path tests
# ---------------------------------------------------------------------------

class TestValidateWikiPath:
    """Tests for the _validate_wiki_path helper."""

    def test_valid_directory(self, wiki_dir: Path):
        """A valid directory should be returned resolved."""
        result = _validate_wiki_path(str(wiki_dir))
        assert result == wiki_dir.resolve()

    def test_null_byte_rejected(self):
        """Paths containing null bytes should raise ValueError."""
        with pytest.raises(ValueError, match="null byte"):
            _validate_wiki_path("/tmp/wiki\x00bad")

    def test_dash_prefix_rejected(self):
        """Paths starting with '-' should raise ValueError."""
        with pytest.raises(ValueError, match="must not start with"):
            _validate_wiki_path("-rf /")

    def test_nonexistent_path_raises(self):
        """Non-existent paths should raise an error."""
        with pytest.raises(Exception, match="does not exist|not found"):
            _validate_wiki_path("/nonexistent/path/wiki")

    def test_file_not_directory_raises(self, tmp_path: Path):
        """A file path (not directory) should raise an error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a dir")
        with pytest.raises(Exception, match="not a directory"):
            _validate_wiki_path(str(file_path))


# ---------------------------------------------------------------------------
# handle_serve_wiki tests
# ---------------------------------------------------------------------------

class TestHandleServeWiki:
    """Tests for the handle_serve_wiki handler."""

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=False)
    @patch("local_deepwiki.handlers.web_server._wait_for_server_ready", new_callable=AsyncMock, return_value=True)
    @patch("local_deepwiki.handlers.web_server.subprocess.Popen")
    async def test_start_server_success(
        self, mock_popen, mock_ready, mock_port_check, mock_ac, wiki_dir
    ):
        """Successful server start should return 'started' status."""
        mock_ac.return_value.require_permission = MagicMock()
        proc = _make_mock_process(alive=True)
        mock_popen.return_value = proc

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9000})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "started"
        assert data["port"] == 9000
        assert "url" in data
        assert data["pid"] == proc.pid

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=False)
    @patch("local_deepwiki.handlers.web_server._wait_for_server_ready", new_callable=AsyncMock, return_value=True)
    @patch("local_deepwiki.handlers.web_server.subprocess.Popen")
    @patch("local_deepwiki.handlers.web_server.webbrowser.open")
    async def test_open_browser_true_calls_webbrowser(
        self, mock_wb, mock_popen, mock_ready, mock_port_check, mock_ac, wiki_dir
    ):
        """open_browser=True should trigger webbrowser.open."""
        mock_ac.return_value.require_permission = MagicMock()
        mock_popen.return_value = _make_mock_process(alive=True)

        await handle_serve_wiki({
            "wiki_path": str(wiki_dir), "port": 9001, "open_browser": True,
        })

        mock_wb.assert_called_once()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=False)
    @patch("local_deepwiki.handlers.web_server._wait_for_server_ready", new_callable=AsyncMock, return_value=True)
    @patch("local_deepwiki.handlers.web_server.subprocess.Popen")
    @patch("local_deepwiki.handlers.web_server.webbrowser.open")
    async def test_open_browser_false_skips(
        self, mock_wb, mock_popen, mock_ready, mock_port_check, mock_ac, wiki_dir
    ):
        """open_browser=False (default) should NOT call webbrowser.open."""
        mock_ac.return_value.require_permission = MagicMock()
        mock_popen.return_value = _make_mock_process(alive=True)

        await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9002})

        mock_wb.assert_not_called()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_nonexistent_path_error(self, mock_ac):
        """Non-existent wiki_path should return an error."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": "/nonexistent/wiki", "port": 9003})

        data = json.loads(result[0].text)
        assert "error" in data.get("status", "").lower() or "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_file_not_directory_error(self, mock_ac, tmp_path):
        """A file path (not directory) should return an error."""
        mock_ac.return_value.require_permission = MagicMock()
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a dir")

        result = await handle_serve_wiki({"wiki_path": str(file_path), "port": 9004})

        assert "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_port_below_1024_rejected(self, mock_ac):
        """Port below 1024 should be rejected by Pydantic validation."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": "/tmp", "port": 80})

        assert "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_port_above_65535_rejected(self, mock_ac):
        """Port above 65535 should be rejected by Pydantic validation."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": "/tmp", "port": 70000})

        assert "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_non_loopback_host_rejected(self, mock_ac, wiki_dir):
        """Non-loopback host should be rejected."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({
            "wiki_path": str(wiki_dir), "host": "0.0.0.0", "port": 9005,
        })

        assert "error" in result[0].text.lower()
        assert "loopback" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_null_byte_in_path_rejected(self, mock_ac):
        """Null byte in wiki_path should be rejected."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": "/tmp/wiki\x00bad", "port": 9006})

        assert "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_dash_prefix_path_rejected(self, mock_ac):
        """wiki_path starting with '-' should be rejected."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": "-rf /", "port": 9007})

        assert "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=True)
    async def test_port_in_use_external(self, mock_port_check, mock_ac, wiki_dir):
        """Port in use by an external process should return an error."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9008})

        assert "error" in result[0].text.lower() or "already in use" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_already_running_returns_status(self, mock_ac, wiki_dir):
        """An already-running server on the same port should return 'already_running'."""
        mock_ac.return_value.require_permission = MagicMock()
        _register_server(9009, wiki_path=str(wiki_dir.resolve()), alive=True)

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9009})

        data = json.loads(result[0].text)
        assert data["status"] == "already_running"

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=False)
    @patch("local_deepwiki.handlers.web_server._wait_for_server_ready", new_callable=AsyncMock, return_value=True)
    @patch("local_deepwiki.handlers.web_server.subprocess.Popen")
    async def test_dead_process_cleanup_respawn(
        self, mock_popen, mock_ready, mock_port_check, mock_ac, wiki_dir
    ):
        """A dead registered process should be cleaned up and a new one spawned."""
        mock_ac.return_value.require_permission = MagicMock()
        _register_server(9010, wiki_path=str(wiki_dir.resolve()), alive=False)
        new_proc = _make_mock_process(alive=True)
        mock_popen.return_value = new_proc

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9010})

        data = json.loads(result[0].text)
        assert data["status"] == "started"

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_max_concurrent_servers_exceeded(self, mock_ac, wiki_dir):
        """Exceeding MAX_CONCURRENT_SERVERS should return an error."""
        mock_ac.return_value.require_permission = MagicMock()
        for i in range(MAX_CONCURRENT_SERVERS):
            _register_server(10000 + i, alive=True)

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 11000})

        assert "error" in result[0].text.lower() or "maximum" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=False)
    @patch("local_deepwiki.handlers.web_server.subprocess.Popen", side_effect=OSError("spawn failed"))
    async def test_popen_raises_oserror(self, mock_popen, mock_port_check, mock_ac, wiki_dir):
        """OSError from Popen should be handled and return an error."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9011})

        assert "error" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    @patch("local_deepwiki.handlers.web_server._is_port_in_use", return_value=False)
    @patch("local_deepwiki.handlers.web_server._wait_for_server_ready", new_callable=AsyncMock, return_value=False)
    @patch("local_deepwiki.handlers.web_server.subprocess.Popen")
    async def test_startup_timeout_reads_stderr(
        self, mock_popen, mock_ready, mock_port_check, mock_ac, wiki_dir
    ):
        """Server that exits during startup should include stderr in error."""
        mock_ac.return_value.require_permission = MagicMock()
        proc = _make_mock_process(alive=False, returncode=1)
        proc.stderr.read.return_value = b"Flask error: address in use"
        mock_popen.return_value = proc

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9012})

        assert "error" in result[0].text.lower()
        assert "flask" in result[0].text.lower() or "exited" in result[0].text.lower()


# ---------------------------------------------------------------------------
# handle_stop_wiki_server tests
# ---------------------------------------------------------------------------

class TestHandleStopWikiServer:
    """Tests for the handle_stop_wiki_server handler."""

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_stop_running_server(self, mock_ac):
        """Stopping a running server should terminate it and return 'stopped'."""
        mock_ac.return_value.require_permission = MagicMock()
        record = _register_server(9020, alive=True)

        result = await handle_stop_wiki_server({"port": 9020})

        data = json.loads(result[0].text)
        assert data["status"] == "stopped"
        record.process.terminate.assert_called_once()
        assert 9020 not in _running_servers

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_stop_not_found_lists_running(self, mock_ac):
        """Stopping a non-existent server should return 'not_found' with running list."""
        mock_ac.return_value.require_permission = MagicMock()

        result = await handle_stop_wiki_server({"port": 9021})

        data = json.loads(result[0].text)
        assert data["status"] == "not_found"
        assert "running_servers" in data

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_stop_already_dead(self, mock_ac):
        """Stopping an already-exited server should return 'already_stopped'."""
        mock_ac.return_value.require_permission = MagicMock()
        _register_server(9022, alive=False)

        result = await handle_stop_wiki_server({"port": 9022})

        data = json.loads(result[0].text)
        assert data["status"] == "already_stopped"
        assert 9022 not in _running_servers

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_wiki_path_filter_match(self, mock_ac, wiki_dir):
        """Stop with matching wiki_path should succeed."""
        mock_ac.return_value.require_permission = MagicMock()
        resolved = str(wiki_dir.resolve())
        _register_server(9023, wiki_path=resolved, alive=True)

        result = await handle_stop_wiki_server({
            "port": 9023, "wiki_path": str(wiki_dir),
        })

        data = json.loads(result[0].text)
        assert data["status"] == "stopped"

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_wiki_path_filter_mismatch(self, mock_ac, wiki_dir):
        """Stop with non-matching wiki_path should return 'not_found'."""
        mock_ac.return_value.require_permission = MagicMock()
        _register_server(9024, wiki_path="/other/wiki", alive=True)

        result = await handle_stop_wiki_server({
            "port": 9024, "wiki_path": str(wiki_dir),
        })

        data = json.loads(result[0].text)
        assert data["status"] == "not_found"

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_terminate_timeout_escalates_to_kill(self, mock_ac):
        """If terminate times out, should escalate to kill."""
        mock_ac.return_value.require_permission = MagicMock()
        record = _register_server(9025, alive=True)
        # First wait (after terminate) raises timeout; second wait (after kill) succeeds
        record.process.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 5),
            None,
        ]

        result = await handle_stop_wiki_server({"port": 9025})

        data = json.loads(result[0].text)
        assert data["status"] == "stopped"
        record.process.terminate.assert_called_once()
        record.process.kill.assert_called_once()


# ---------------------------------------------------------------------------
# RBAC tests
# ---------------------------------------------------------------------------

class TestRBACAccess:
    """Tests for RBAC permission checks."""

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_serve_wiki_access_denied(self, mock_ac, wiki_dir):
        """serve_wiki should handle AccessDeniedException."""
        from local_deepwiki.security import AccessDeniedException

        mock_ac.return_value.require_permission.side_effect = AccessDeniedException(
            "No admin access"
        )

        result = await handle_serve_wiki({"wiki_path": str(wiki_dir), "port": 9030})

        assert "access denied" in result[0].text.lower() or "denied" in result[0].text.lower()

    @patch("local_deepwiki.handlers.web_server.get_access_controller")
    async def test_stop_wiki_access_denied(self, mock_ac):
        """stop_wiki_server should handle AccessDeniedException."""
        from local_deepwiki.security import AccessDeniedException

        mock_ac.return_value.require_permission.side_effect = AccessDeniedException(
            "No admin access"
        )

        result = await handle_stop_wiki_server({"port": 9031})

        assert "access denied" in result[0].text.lower() or "denied" in result[0].text.lower()
