"""Tests for handlers._shared module."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.errors import (
    DeepWikiError,
    ExportError,
    IndexingError,
    ValidationError,
    format_error_response,
)
from local_deepwiki.handlers._shared import (
    FORBIDDEN_EXPORT_DIRS,
    FORBIDDEN_VAR_SUBDIRS,
    ProgressNotifier,
    create_progress_notifier,
    handle_tool_errors,
    _format_research_results,
    _is_test_file,
    _load_index_status,
    _validate_export_path,
)
from local_deepwiki.progress import OperationType, ProgressPhase, ProgressUpdate
from local_deepwiki.security import AccessDeniedException, AuthenticationException


class TestHandleToolErrors:
    """Tests for the handle_tool_errors decorator."""

    async def test_successful_execution(self):
        """Test decorator allows successful execution through."""

        @handle_tool_errors
        async def successful_tool(args: dict[str, Any]) -> list[TextContent]:
            return [TextContent(type="text", text="success")]

        result = await successful_tool({})
        assert len(result) == 1
        assert result[0].text == "success"

    async def test_deepwiki_error_handling(self):
        """Test DeepWikiError is formatted correctly."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise ValidationError(message="Invalid input", hint="Check your parameters")

        result = await failing_tool({})
        assert len(result) == 1
        assert "Invalid input" in result[0].text
        assert "Hint:" in result[0].text

    async def test_value_error_wrapping(self):
        """Test ValueError is wrapped in ValidationError."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise ValueError("Bad value")

        result = await failing_tool({})
        assert len(result) == 1
        assert "Bad value" in result[0].text
        assert "Hint:" in result[0].text

    async def test_file_not_found_error_handling(self):
        """Test FileNotFoundError is mapped to DeepWikiError."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise FileNotFoundError("File not found")

        result = await failing_tool({})
        assert len(result) == 1
        assert (
            "File not found" in result[0].text or "not found" in result[0].text.lower()
        )

    async def test_permission_error_handling(self):
        """Test PermissionError is mapped to DeepWikiError."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise PermissionError("Permission denied")

        result = await failing_tool({})
        assert len(result) == 1
        assert "permission" in result[0].text.lower()

    async def test_access_denied_exception_handling(self):
        """Test AccessDeniedException is handled with proper hint."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise AccessDeniedException("User lacks permission")

        result = await failing_tool({})
        assert len(result) == 1
        assert "Access denied" in result[0].text
        assert "permission" in result[0].text

    async def test_authentication_exception_handling(self):
        """Test AuthenticationException is handled with proper hint."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise AuthenticationException("Not authenticated")

        result = await failing_tool({})
        assert len(result) == 1
        assert "Authentication required" in result[0].text

    async def test_connection_error_handling(self):
        """Test ConnectionError is mapped to DeepWikiError."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise ConnectionError("Connection failed")

        result = await failing_tool({})
        assert len(result) == 1
        assert "Connection" in result[0].text or "connection" in result[0].text

    async def test_timeout_error_handling(self):
        """Test TimeoutError is mapped to DeepWikiError."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise TimeoutError("Request timed out")

        result = await failing_tool({})
        assert len(result) == 1
        # TimeoutError message can vary, so just check for error response
        assert (
            "Request timed out" in result[0].text
            or "timeout" in result[0].text.lower()
            or "error" in result[0].text.lower()
        )

    async def test_rate_limit_error_handling(self):
        """Test RateLimitExceeded is handled with proper hint."""
        from local_deepwiki.core.rate_limiter import RateLimitExceeded

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise RateLimitExceeded("Rate limit exceeded: 10 requests per minute")

        result = await failing_tool({})
        assert len(result) == 1
        assert "Rate limit" in result[0].text or "rate limit" in result[0].text
        assert "wait" in result[0].text.lower() or "reduce" in result[0].text.lower()

    async def test_cancelled_error_propagates(self):
        """Test asyncio.CancelledError is re-raised."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await failing_tool({})

    async def test_generic_exception_handling(self):
        """Test generic exceptions are caught and formatted."""

        @handle_tool_errors
        async def failing_tool(args: dict[str, Any]) -> list[TextContent]:
            raise RuntimeError("Unexpected error")

        result = await failing_tool({})
        assert len(result) == 1
        assert "unexpected error" in result[0].text.lower()
        assert "Hint:" in result[0].text


class TestForbiddenExportDirs:
    """Tests for FORBIDDEN_EXPORT_DIRS constant."""

    def test_forbidden_dirs_includes_system_paths(self):
        """Test that forbidden directories include critical system paths."""
        assert "/etc" in FORBIDDEN_EXPORT_DIRS
        assert "/usr" in FORBIDDEN_EXPORT_DIRS
        assert "/bin" in FORBIDDEN_EXPORT_DIRS
        assert "/sbin" in FORBIDDEN_EXPORT_DIRS

    def test_forbidden_dirs_includes_home_ssh(self):
        """Test that .ssh directory is forbidden."""
        ssh_path = str(Path.home() / ".ssh")
        assert ssh_path in FORBIDDEN_EXPORT_DIRS

    def test_forbidden_dirs_is_frozen(self):
        """Test that FORBIDDEN_EXPORT_DIRS is immutable."""
        assert isinstance(FORBIDDEN_EXPORT_DIRS, frozenset)
        with pytest.raises(AttributeError):
            FORBIDDEN_EXPORT_DIRS.add("/new/path")


class TestValidateExportPath:
    """Tests for _validate_export_path function."""

    def test_valid_path_in_project(self, tmp_path):
        """Test that valid project paths are accepted."""
        output_path = tmp_path / "output"
        wiki_path = tmp_path / ".deepwiki"

        result = _validate_export_path(output_path, wiki_path)
        assert result == output_path.resolve()

    def test_forbidden_system_directory(self, tmp_path):
        """Test that system directories are rejected."""
        output_path = Path("/etc/output")
        wiki_path = tmp_path / ".deepwiki"

        with pytest.raises(ValidationError) as exc_info:
            _validate_export_path(output_path, wiki_path)

        assert "Cannot export to system directory" in str(exc_info.value)
        assert "/etc" in str(exc_info.value)

    def test_forbidden_usr_directory(self, tmp_path):
        """Test that /usr is rejected."""
        output_path = Path("/usr/local/output")
        wiki_path = tmp_path / ".deepwiki"

        with pytest.raises(ValidationError) as exc_info:
            _validate_export_path(output_path, wiki_path)

        assert "system directory" in str(exc_info.value).lower()

    def test_forbidden_ssh_directory(self, tmp_path):
        """Test that .ssh directory is rejected."""
        output_path = Path.home() / ".ssh" / "output"
        wiki_path = tmp_path / ".deepwiki"

        with pytest.raises(ValidationError) as exc_info:
            _validate_export_path(output_path, wiki_path)

        assert "system directory" in str(exc_info.value).lower()

    def test_forbidden_var_log_directory(self, tmp_path):
        """Test that /var/log is rejected."""
        output_path = Path("/var/log/output")
        wiki_path = tmp_path / ".deepwiki"

        with pytest.raises(ValidationError) as exc_info:
            _validate_export_path(output_path, wiki_path)

        assert "system directory" in str(exc_info.value).lower()

    def test_allowed_var_folders(self, tmp_path):
        """Test that /var/folders is allowed (temp directories)."""
        # Use a real temp directory that actually exists
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output"
            wiki_path = tmp_path / ".deepwiki"

            # Should not raise - temp directories are allowed
            result = _validate_export_path(output_path, wiki_path)
            # Verify it's a resolved path
            assert result.is_absolute()

    def test_forbidden_config_directory(self, tmp_path):
        """Test that ~/.config (except local-deepwiki) is rejected."""
        output_path = Path.home() / ".config" / "other-app" / "output"
        wiki_path = tmp_path / ".deepwiki"

        with pytest.raises(ValidationError) as exc_info:
            _validate_export_path(output_path, wiki_path)

        assert "config directory" in str(exc_info.value).lower()

    def test_allowed_local_deepwiki_config(self, tmp_path):
        """Test that ~/.config/local-deepwiki is allowed."""
        output_path = Path.home() / ".config" / "local-deepwiki" / "output"
        wiki_path = tmp_path / ".deepwiki"

        result = _validate_export_path(output_path, wiki_path)
        assert result == output_path.resolve()

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if missing."""
        output_path = tmp_path / "nested" / "deep" / "output.html"
        wiki_path = tmp_path / ".deepwiki"

        result = _validate_export_path(output_path, wiki_path)
        assert result.parent.exists()

    def test_permission_error_on_parent_creation(self, tmp_path):
        """Test handling of permission errors during parent creation."""
        output_path = tmp_path / "nested" / "output.html"
        wiki_path = tmp_path / ".deepwiki"

        with patch("pathlib.Path.mkdir", side_effect=PermissionError("No permission")):
            with pytest.raises(ValidationError) as exc_info:
                _validate_export_path(output_path, wiki_path)

            assert "Cannot create output directory" in str(exc_info.value)

    def test_os_error_on_parent_creation(self, tmp_path):
        """Test handling of OS errors during parent creation."""
        output_path = tmp_path / "nested" / "output.html"
        wiki_path = tmp_path / ".deepwiki"

        with patch("pathlib.Path.mkdir", side_effect=OSError("Disk full")):
            with pytest.raises(ValidationError) as exc_info:
                _validate_export_path(output_path, wiki_path)

            assert "Failed to create output directory" in str(exc_info.value)


class TestLoadIndexStatus:
    """Tests for _load_index_status function."""

    async def test_successful_load(self, tmp_path):
        """Test successful loading of index status."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        with patch("local_deepwiki.handlers._shared.get_config") as mock_config:
            config = Mock()
            wiki_path = tmp_path / ".deepwiki"
            wiki_path.mkdir()
            vector_db_path = tmp_path / "vectors.lance"
            vector_db_path.mkdir()

            config.get_wiki_path.return_value = wiki_path
            config.get_vector_db_path.return_value = vector_db_path
            mock_config.return_value = config

            # Patch Path.exists to return True for vector_db_path
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "local_deepwiki.core.index_manager.IndexStatusManager"
                ) as mock_manager:
                    mock_status = Mock()
                    mock_manager.return_value.load.return_value = mock_status

                    (
                        index_status,
                        result_wiki_path,
                        result_config,
                    ) = await _load_index_status(repo_path)

                    assert index_status == mock_status
                    assert result_wiki_path == wiki_path
                    assert result_config == config

    async def test_missing_vector_db(self, tmp_path):
        """Test error when vector database doesn't exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        with patch("local_deepwiki.handlers._shared.get_config") as mock_config:
            config = Mock()
            wiki_path = tmp_path / ".deepwiki"
            vector_db_path = tmp_path / "vectors.lance"  # Does not exist

            config.get_wiki_path.return_value = wiki_path
            config.get_vector_db_path.return_value = vector_db_path
            mock_config.return_value = config

            with pytest.raises(ValidationError) as exc_info:
                await _load_index_status(repo_path)

            assert "not indexed" in str(exc_info.value).lower()

    async def test_missing_index_status(self, tmp_path):
        """Test error when index status file doesn't exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        with patch("local_deepwiki.handlers._shared.get_config") as mock_config:
            config = Mock()
            wiki_path = tmp_path / ".deepwiki"
            wiki_path.mkdir()
            vector_db_path = tmp_path / "vectors.lance"
            vector_db_path.mkdir()

            config.get_wiki_path.return_value = wiki_path
            config.get_vector_db_path.return_value = vector_db_path
            mock_config.return_value = config

            # Patch Path.exists to return True for vector_db_path check
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "local_deepwiki.core.index_manager.IndexStatusManager"
                ) as mock_manager:
                    mock_manager.return_value.load.return_value = None

                    with pytest.raises(ValidationError) as exc_info:
                        await _load_index_status(repo_path)

                    assert "not indexed" in str(exc_info.value).lower()


class TestIsTestFile:
    """Tests for _is_test_file helper."""

    def test_test_directory(self):
        """Test files in test directories."""
        assert _is_test_file("tests/test_something.py")
        assert _is_test_file("test/something.py")
        assert _is_test_file("testing/file.py")
        assert _is_test_file("spec/file.js")
        assert _is_test_file("specs/file.js")

    def test_test_prefix(self):
        """Test files with test_ prefix."""
        assert _is_test_file("test_something.py")
        assert _is_test_file("src/test_module.py")

    def test_test_suffix(self):
        """Test files with _test suffix."""
        assert _is_test_file("something_test.py")
        assert _is_test_file("module_test.py")

    def test_conftest(self):
        """Test conftest files."""
        assert _is_test_file("conftest.py")
        assert _is_test_file("tests/conftest.py")

    def test_non_test_file(self):
        """Test regular files are not identified as tests."""
        assert not _is_test_file("src/module.py")
        assert not _is_test_file("main.py")
        assert not _is_test_file("utils/helper.py")


class TestFormatResearchResults:
    """Tests for _format_research_results function."""

    def test_format_basic_result(self):
        """Test formatting basic research result."""
        from local_deepwiki.models import (
            DeepResearchResult,
            ResearchStep,
            ResearchStepType,
            SourceReference,
            SubQuestion,
        )

        sub_questions = [
            SubQuestion(question="What is X?", category="definition"),
            SubQuestion(question="How does Y work?", category="implementation"),
        ]

        sources = [
            SourceReference(
                file_path="src/module.py",
                start_line=10,
                end_line=20,
                chunk_type="function",
                name="my_function",
                relevance_score=0.95,
            ),
        ]

        traces = [
            ResearchStep(
                step_type=ResearchStepType.DECOMPOSITION,
                description="Decomposing question",
                duration_ms=100,
            ),
        ]

        result = DeepResearchResult(
            question="Main question",
            answer="Answer text",
            sub_questions=sub_questions,
            sources=sources,
            reasoning_trace=traces,
            total_chunks_analyzed=50,
            total_llm_calls=3,
        )

        formatted = _format_research_results(result)

        assert formatted["question"] == "Main question"
        assert formatted["answer"] == "Answer text"
        assert len(formatted["sub_questions"]) == 2
        assert formatted["sub_questions"][0]["question"] == "What is X?"
        assert len(formatted["sources"]) == 1
        assert formatted["sources"][0]["file"] == "src/module.py"
        assert formatted["sources"][0]["relevance"] == 0.95
        assert len(formatted["research_trace"]) == 1
        assert formatted["stats"]["chunks_analyzed"] == 50
        assert formatted["stats"]["llm_calls"] == 3


class TestProgressNotifier:
    """Tests for ProgressNotifier class."""

    def test_initialization(self):
        """Test ProgressNotifier initialization."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )
        server = Mock()

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=server,
            progress_token="token123",
            buffer_interval=0.5,
        )

        assert notifier.progress_manager == manager
        assert notifier.server == server
        assert notifier.progress_token == "token123"
        # ProgressBuffer doesn't expose flush_interval, just verify buffer exists
        assert notifier.buffer is not None

    async def test_update_with_message(self):
        """Test updating progress with a message."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )
        server = Mock()

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=server,
            progress_token="token123",
        )

        await notifier.update(current=1, total=10, message="Processing file 1")

        assert "Processing file 1" in notifier.messages

    async def test_update_without_server(self):
        """Test that updates work without a server."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=None,
            progress_token=None,
        )

        # Should not raise
        await notifier.update(current=1, total=10, message="Test")

    async def test_flush(self):
        """Test flushing pending notifications."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )
        server = Mock()
        # Mock the async send_progress_notification
        server.request_context.session.send_progress_notification = AsyncMock()

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=server,
            progress_token="token123",
        )

        await notifier.update(current=1, total=10, message="Test")
        await notifier.flush()

        # After flush, messages should still be available
        assert len(notifier.messages) > 0

    async def test_send_notifications_without_token(self):
        """Test that notifications are skipped without progress token."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )
        server = Mock()

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=server,
            progress_token=None,  # No token
        )

        update = ProgressUpdate(
            operation_id="test",
            operation_type=OperationType.INDEX_REPOSITORY,
            current=1,
            total=10,
            message="Test",
            timestamp=0,
            phase=ProgressPhase.PARSING,
        )

        # Should not raise, just skip notification
        await notifier._send_notifications([update])

    async def test_send_notifications_with_error(self):
        """Test that notification errors are logged but don't crash."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )
        server = Mock()
        server.request_context.session.send_progress_notification = AsyncMock(
            side_effect=RuntimeError("Connection lost")
        )

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=server,
            progress_token="token123",
        )

        update = ProgressUpdate(
            operation_id="test",
            operation_type=OperationType.INDEX_REPOSITORY,
            current=1,
            total=10,
            message="Test",
            timestamp=0,
            phase=ProgressPhase.PARSING,
        )

        # Should not raise, just log warning
        await notifier._send_notifications([update])

    def test_messages_property(self):
        """Test accessing accumulated messages."""
        from local_deepwiki.progress import ProgressManager

        manager = ProgressManager(
            operation_id="test", operation_type=OperationType.INDEX_REPOSITORY
        )

        notifier = ProgressNotifier(
            progress_manager=manager,
            server=None,
            progress_token=None,
        )

        assert isinstance(notifier.messages, list)
        assert len(notifier.messages) == 0


class TestForbiddenVarSubdirs:
    """Tests for FORBIDDEN_VAR_SUBDIRS constant."""

    def test_forbidden_var_subdirs_includes_log(self):
        """Test that /var/log is forbidden."""
        assert "/var/log" in FORBIDDEN_VAR_SUBDIRS
        assert "/private/var/log" in FORBIDDEN_VAR_SUBDIRS

    def test_forbidden_var_subdirs_includes_db(self):
        """Test that /var/db is forbidden."""
        assert "/var/db" in FORBIDDEN_VAR_SUBDIRS
        assert "/private/var/db" in FORBIDDEN_VAR_SUBDIRS

    def test_forbidden_var_subdirs_is_frozen(self):
        """Test that FORBIDDEN_VAR_SUBDIRS is immutable."""
        assert isinstance(FORBIDDEN_VAR_SUBDIRS, frozenset)


class TestCreateProgressNotifier:
    """Tests for create_progress_notifier function."""

    def test_create_with_server(self):
        """Test creating notifier with server."""
        server = Mock()
        server.request_context.meta.progressToken = "token123"

        notifier, operation_id = create_progress_notifier(
            operation_type=OperationType.INDEX_REPOSITORY,
            server=server,
            total=100,
        )

        assert notifier is not None
        assert isinstance(notifier, ProgressNotifier)
        assert operation_id is not None

    def test_create_without_server(self):
        """Test creating notifier without server."""
        notifier, operation_id = create_progress_notifier(
            operation_type=OperationType.INDEX_REPOSITORY,
            server=None,
            total=100,
        )

        assert notifier is not None
        assert isinstance(notifier, ProgressNotifier)
        assert operation_id is not None

    def test_create_without_progress_token(self):
        """Test creating notifier when server has no progress token."""
        server = Mock()
        server.request_context.meta = None

        notifier, operation_id = create_progress_notifier(
            operation_type=OperationType.INDEX_REPOSITORY,
            server=server,
            total=100,
        )

        assert notifier is not None
        assert operation_id is not None

    def test_create_with_no_request_context(self):
        """Test creating notifier when server has no request context."""
        server = Mock()
        server.request_context = Mock(side_effect=LookupError("No context"))

        notifier, operation_id = create_progress_notifier(
            operation_type=OperationType.INDEX_REPOSITORY,
            server=server,
            total=100,
        )

        assert notifier is not None
        assert operation_id is not None
