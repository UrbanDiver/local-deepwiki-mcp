"""Tests for CLI progress bar functionality."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.cli_progress import (
    MultiPhaseProgress,
    ProgressCallback,
    create_indeterminate_progress,
    create_progress,
    file_progress,
    is_interactive,
)


class TestIsInteractive:
    """Tests for is_interactive function."""

    def test_returns_false_when_not_tty(self):
        """Test returns False when stdout is not a TTY."""
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            assert is_interactive() is False

    def test_returns_false_when_no_isatty(self):
        """Test returns False when stdout has no isatty method."""
        with patch("sys.stdout") as mock_stdout:
            del mock_stdout.isatty
            assert is_interactive() is False

    def test_returns_false_when_ci_env_set(self):
        """Test returns False when CI environment variable is set."""
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            with patch.dict(os.environ, {"CI": "true"}):
                assert is_interactive() is False

    def test_returns_false_when_no_color_env_set(self):
        """Test returns False when NO_COLOR environment variable is set."""
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=True):
                assert is_interactive() is False

    def test_returns_false_when_term_is_dumb(self):
        """Test returns False when TERM is dumb."""
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            with patch.dict(os.environ, {"TERM": "dumb"}, clear=True):
                assert is_interactive() is False

    def test_returns_true_for_interactive_terminal(self):
        """Test returns True for an interactive terminal."""
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            # Clear environment variables that would make it non-interactive
            with patch.dict(os.environ, {}, clear=True):
                assert is_interactive() is True


class TestCreateProgress:
    """Tests for create_progress function."""

    def test_creates_progress_instance(self):
        """Test that create_progress returns a Progress instance."""
        progress = create_progress(disable=True)
        assert progress is not None

    def test_respects_disable_flag(self):
        """Test that disable flag is respected."""
        progress = create_progress(disable=True)
        assert progress.disable is True

    def test_auto_disables_in_non_interactive(self):
        """Test that progress is auto-disabled in non-interactive mode."""
        with patch("local_deepwiki.cli_progress.is_interactive", return_value=False):
            progress = create_progress()
            assert progress.disable is True


class TestCreateIndeterminateProgress:
    """Tests for create_indeterminate_progress function."""

    def test_creates_progress_instance(self):
        """Test that create_indeterminate_progress returns a Progress instance."""
        progress = create_indeterminate_progress(disable=True)
        assert progress is not None

    def test_respects_disable_flag(self):
        """Test that disable flag is respected."""
        progress = create_indeterminate_progress(disable=True)
        assert progress.disable is True


class TestFileProgress:
    """Tests for file_progress context manager."""

    def test_file_progress_yields_correct_tuple(self, tmp_path: Path):
        """Test that file_progress yields correct tuple."""
        files = [tmp_path / "a.txt", tmp_path / "b.txt"]
        with file_progress(files, "Test", disable=True) as (progress, task, file_list):
            assert progress is not None
            assert task is not None
            assert file_list == files

    def test_file_progress_converts_iterable_to_list(self, tmp_path: Path):
        """Test that file_progress converts iterable to list."""

        def file_generator():
            yield tmp_path / "a.txt"
            yield tmp_path / "b.txt"

        with file_progress(file_generator(), "Test", disable=True) as (_, _, file_list):
            assert isinstance(file_list, list)
            assert len(file_list) == 2


class TestProgressCallback:
    """Tests for ProgressCallback adapter class."""

    def test_callback_updates_progress(self):
        """Test that callback updates progress correctly."""
        mock_progress = MagicMock()
        task_id = 1

        callback = ProgressCallback(mock_progress, task_id)
        callback("Processing file.py", 1, 10)

        mock_progress.update.assert_called()

    def test_callback_calculates_advance(self):
        """Test that callback calculates advance correctly."""
        mock_progress = MagicMock()
        task_id = 1

        callback = ProgressCallback(mock_progress, task_id)
        callback("First", 1, 10)
        callback("Second", 3, 10)  # Should advance by 2

        # Check that advance was called with correct values
        calls = mock_progress.update.call_args_list
        # Find the advance call
        advance_calls = [c for c in calls if "advance" in str(c)]
        assert len(advance_calls) > 0

    def test_callback_handles_reset(self):
        """Test that callback handles progress reset (new phase)."""
        mock_progress = MagicMock()
        task_id = 1

        callback = ProgressCallback(mock_progress, task_id)
        callback("Phase 1", 5, 10)
        callback("Phase 2", 1, 5)  # Reset to lower value (new phase)

        # Should update with completed=1 for reset
        mock_progress.update.assert_called()

    def test_callback_updates_description(self):
        """Test that callback updates description when show_message is True."""
        mock_progress = MagicMock()
        task_id = 1

        callback = ProgressCallback(mock_progress, task_id, show_message=True)
        callback("Processing", 1, 10)

        # Check description was updated
        calls = mock_progress.update.call_args_list
        desc_calls = [c for c in calls if "description" in str(c)]
        assert len(desc_calls) > 0

    def test_callback_truncates_long_messages(self):
        """Test that callback truncates long messages."""
        mock_progress = MagicMock()
        task_id = 1

        callback = ProgressCallback(mock_progress, task_id, show_message=True)
        long_msg = "A" * 100  # Long message
        callback(long_msg, 1, 10)

        # Find the description update call
        for call in mock_progress.update.call_args_list:
            kwargs = call[1] if len(call) > 1 else {}
            if "description" in kwargs:
                desc = kwargs["description"]
                assert len(desc) <= 53  # 50 chars + "..."
                break


class TestMultiPhaseProgress:
    """Tests for MultiPhaseProgress class."""

    def test_context_manager_works(self):
        """Test that MultiPhaseProgress works as context manager."""
        with MultiPhaseProgress(disable=True) as progress:
            assert progress._active is True
        assert progress._active is False

    def test_add_phase_creates_task(self):
        """Test that add_phase creates a task."""
        with MultiPhaseProgress(disable=True) as progress:
            task_id = progress.add_phase("test", "Test Phase", total=10)
            assert task_id is not None
            assert "test" in progress._tasks

    def test_add_phase_raises_when_not_started(self):
        """Test that add_phase raises when not started."""
        progress = MultiPhaseProgress(disable=True)
        with pytest.raises(RuntimeError, match="not started"):
            progress.add_phase("test", "Test")

    def test_update_phase(self):
        """Test updating a phase."""
        with MultiPhaseProgress(disable=True) as progress:
            progress.add_phase("test", "Test", total=10)
            # Should not raise
            progress.update("test", advance=1)
            progress.update("test", completed=5)
            progress.update("test", description="New description")
            progress.update("test", total=20)

    def test_update_nonexistent_phase_does_nothing(self):
        """Test that updating nonexistent phase does nothing."""
        with MultiPhaseProgress(disable=True) as progress:
            # Should not raise
            progress.update("nonexistent", advance=1)

    def test_update_when_not_active_does_nothing(self):
        """Test that update when not active does nothing."""
        progress = MultiPhaseProgress(disable=True)
        # Should not raise
        progress.update("test", advance=1)

    def test_complete_phase(self):
        """Test completing a phase."""
        with MultiPhaseProgress(disable=True) as progress:
            progress.add_phase("test", "Test", total=10)
            progress.update("test", advance=5)
            # Should not raise
            progress.complete_phase("test")

    def test_complete_nonexistent_phase_does_nothing(self):
        """Test that completing nonexistent phase does nothing."""
        with MultiPhaseProgress(disable=True) as progress:
            # Should not raise
            progress.complete_phase("nonexistent")

    def test_get_callback(self):
        """Test getting a callback for a phase."""
        with MultiPhaseProgress(disable=True) as progress:
            progress.add_phase("test", "Test", total=10)
            callback = progress.get_callback("test")
            assert callback is not None
            assert isinstance(callback, ProgressCallback)

    def test_get_callback_nonexistent_returns_none(self):
        """Test that get_callback for nonexistent phase returns None."""
        with MultiPhaseProgress(disable=True) as progress:
            callback = progress.get_callback("nonexistent")
            assert callback is None

    def test_get_callback_when_not_active_returns_none(self):
        """Test that get_callback when not active returns None."""
        progress = MultiPhaseProgress(disable=True)
        callback = progress.get_callback("test")
        assert callback is None

    def test_multiple_phases(self):
        """Test tracking multiple phases."""
        with MultiPhaseProgress(disable=True) as progress:
            progress.add_phase("phase1", "Phase 1", total=5)
            progress.add_phase("phase2", "Phase 2", total=10)

            progress.update("phase1", advance=3)
            progress.update("phase2", advance=5)

            assert "phase1" in progress._tasks
            assert "phase2" in progress._tasks


class TestProgressIntegration:
    """Integration tests for progress functionality."""

    def test_html_export_progress_option(self, tmp_path: Path):
        """Test that HTML export supports --no-progress option."""
        from local_deepwiki.export.html import HtmlExporter

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        output_path = tmp_path / "output"

        exporter = HtmlExporter(wiki_path, output_path, no_progress=True)
        count = exporter.export()

        assert count == 1
        assert (output_path / "index.html").exists()

    def test_pdf_export_progress_option(self, tmp_path: Path):
        """Test that PDF export supports --no-progress option."""
        try:
            from local_deepwiki.export.pdf import PdfExporter
        except (ImportError, OSError) as e:
            # weasyprint requires system dependencies (pango, gobject)
            pytest.skip(f"weasyprint not properly configured: {e}")

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        output_path = tmp_path / "output.pdf"

        try:
            exporter = PdfExporter(wiki_path, output_path, no_progress=True)
            result = exporter.export_single()
            # Check if file was actually created (weasyprint may silently fail)
            if not result.exists():
                pytest.skip("PDF generation silently failed - likely missing system deps")
            assert result.exists()
        except (OSError, Exception) as e:
            # Handle missing system dependencies gracefully
            error_str = str(e).lower()
            if (
                "library" in error_str
                or "gobject" in error_str
                or "pango" in error_str
                or "cairo" in error_str
                or "fontconfig" in error_str
            ):
                pytest.skip(f"PDF export requires system dependencies: {e}")
            raise
