"""Tests for run_search function and main() CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.cli.interactive_search import (
    run_search,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


# =============================================================================
# run_search Function Tests (basic)
# =============================================================================


class TestRunSearch:
    """Tests for the run_search function."""

    async def test_run_search_repo_not_found(self, tmp_path: Path) -> None:
        """run_search should handle missing repository."""
        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            await run_search(
                repo_path=tmp_path / "nonexistent",
                query="test",
                interactive=False,
            )

            # Should print error
            mock_console.print.assert_called()
            call_args = str(mock_console.print.call_args)
            assert "not found" in call_args.lower()

    async def test_run_search_not_indexed(self, tmp_path: Path) -> None:
        """run_search should handle non-indexed repository."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            await run_search(
                repo_path=repo_path,
                query="test",
                interactive=False,
            )

            # Should print error about not indexed
            mock_console.print.assert_called()
            call_args = str(mock_console.print.call_args)
            assert "not indexed" in call_args.lower()

    async def test_run_search_non_interactive_no_query(self, tmp_path: Path) -> None:
        """run_search should require query in non-interactive mode."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch("local_deepwiki.cli.interactive_search.VectorStore"):
                    await run_search(
                        repo_path=repo_path,
                        query=None,
                        interactive=False,
                    )

                    # Should print error about query required
                    mock_console.print.assert_called()
                    call_args = str(mock_console.print.call_args)
                    assert (
                        "query" in call_args.lower() and "required" in call_args.lower()
                    )


# =============================================================================
# run_search Function Additional Tests
# =============================================================================


class TestRunSearchFunction:
    """Additional tests for the run_search function."""

    async def test_run_search_non_interactive_with_query(self, tmp_path: Path) -> None:
        """run_search should execute search and display results."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await run_search(
                        repo_path=repo_path,
                        query="test query",
                        interactive=False,
                    )

                    # Search should have been called
                    mock_store.search.assert_called()

    async def test_run_search_non_interactive_with_preview(
        self, tmp_path: Path
    ) -> None:
        """run_search should show preview when requested."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        chunk = CodeChunk(
            id="test",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test",
            content="def test(): pass",
            start_line=1,
            end_line=2,
        )
        results = [SearchResult(chunk=chunk, score=0.9)]

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=results)

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await run_search(
                        repo_path=repo_path,
                        query="test",
                        interactive=False,
                        show_preview=True,
                    )

                    # Should have printed multiple times (results + preview)
                    assert mock_console.print.call_count >= 2

    async def test_run_search_interactive_with_query(self, tmp_path: Path) -> None:
        """run_search should run interactive mode with initial query."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    with patch(
                        "local_deepwiki.cli.interactive_search.InteractiveSearch.run"
                    ) as mock_run:
                        mock_run.return_value = None

                        await run_search(
                            repo_path=repo_path,
                            query="test",
                            interactive=True,
                        )

                        # Interactive run should have been called with initial query
                        mock_run.assert_called_once_with(initial_query="test")

    async def test_run_search_interactive_without_query(self, tmp_path: Path) -> None:
        """run_search should run interactive mode without initial query."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    with patch(
                        "local_deepwiki.cli.interactive_search.InteractiveSearch.run"
                    ) as mock_run:
                        mock_run.return_value = None

                        await run_search(
                            repo_path=repo_path,
                            query=None,
                            interactive=True,
                        )

                        # Interactive run should have been called without query
                        mock_run.assert_called_once()

    async def test_run_search_with_all_filters(self, tmp_path: Path) -> None:
        """run_search should pass all filters to search instance."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await run_search(
                        repo_path=repo_path,
                        query="test",
                        language="python",
                        chunk_type="function",
                        file_pattern="*.py",
                        min_score=0.5,
                        limit=10,
                        interactive=False,
                    )

                    # Search should have been called
                    mock_store.search.assert_called()


# =============================================================================
# CLI Main Function Tests
# =============================================================================


class TestMainFunction:
    """Tests for the main CLI entry point."""

    def test_main_with_valid_args(self, tmp_path: Path) -> None:
        """main should parse arguments and run search."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            coro.close()
            return None

        with patch(
            "sys.argv",
            ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive"],
        ):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=close_coro,
            ) as mock_run:
                result = main()

                assert result == 0
                mock_run.assert_called_once()

    def test_main_invalid_min_score(self, tmp_path: Path) -> None:
        """main should error on invalid min_score."""
        from local_deepwiki.cli.interactive_search import main

        with patch(
            "sys.argv", ["deepwiki-search", str(tmp_path), "--min-score", "1.5"]
        ):
            with patch("sys.stderr"):
                result = main()
                assert result == 1

    def test_main_non_interactive_requires_query(self, tmp_path: Path) -> None:
        """main should error when non-interactive mode lacks query."""
        from local_deepwiki.cli.interactive_search import main

        with patch("sys.argv", ["deepwiki-search", str(tmp_path), "--no-interactive"]):
            with patch("sys.stderr"):
                result = main()
                assert result == 1

    def test_main_keyboard_interrupt(self, tmp_path: Path) -> None:
        """main should handle KeyboardInterrupt."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro_and_interrupt(coro):
            """Close coroutine then raise KeyboardInterrupt."""
            coro.close()
            raise KeyboardInterrupt

        with patch(
            "sys.argv",
            ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive"],
        ):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=close_coro_and_interrupt,
            ):
                result = main()
                assert result == 130

    def test_main_exception(self, tmp_path: Path) -> None:
        """main should handle exceptions."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro_and_raise(coro):
            """Close coroutine then raise RuntimeError."""
            coro.close()
            raise RuntimeError("Test error")

        with patch(
            "sys.argv",
            ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive"],
        ):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=close_coro_and_raise,
            ):
                with patch("sys.stderr"):
                    result = main()
                    assert result == 1

    def test_main_with_preview_flag(self, tmp_path: Path) -> None:
        """main should pass preview flag correctly."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        captured_coro = []

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            captured_coro.append(coro)
            coro.close()
            return None

        with patch(
            "sys.argv",
            ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive", "-p"],
        ):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=close_coro,
            ):
                result = main()

                assert result == 0
                # Check that run was called with a coroutine
                assert len(captured_coro) == 1

    def test_main_with_all_filter_args(self, tmp_path: Path) -> None:
        """main should parse all filter arguments."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            coro.close()
            return None

        with patch(
            "sys.argv",
            [
                "deepwiki-search",
                str(repo_path),
                "-q",
                "test",
                "-l",
                "python",
                "-t",
                "function",
                "-f",
                "*.py",
                "-s",
                "0.5",
                "--limit",
                "10",
                "--no-interactive",
            ],
        ):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=close_coro,
            ) as mock_run:
                result = main()

                assert result == 0


# =============================================================================
# Module Entry Point Tests
# =============================================================================


class TestModuleEntryPoint:
    """Tests for __name__ == '__main__' execution."""

    def test_module_can_be_imported(self) -> None:
        """Module should be importable without side effects."""
        import importlib
        import local_deepwiki.cli.interactive_search as module

        # Reimporting should work
        importlib.reload(module)

    def test_main_called_when_run_as_script(self) -> None:
        """main should be callable."""
        from local_deepwiki.cli.interactive_search import main

        assert callable(main)

    def test_module_name_main_execution(self, tmp_path: Path) -> None:
        """Test module execution via runpy to cover if __name__ == '__main__' block."""
        import subprocess
        import sys

        # Create a minimal test repo structure
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        # Run the module with arguments to make it exit quickly with error
        # (non-interactive mode without query returns error code 1)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "local_deepwiki.cli.interactive_search",
                str(repo_path),
                "--no-interactive",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tmp_path,
        )

        # The module should have executed (entry point was called)
        # Exit code 1 means the validation ran (query required for non-interactive)
        assert result.returncode == 1
        assert "query" in result.stderr.lower() or "required" in result.stderr.lower()
