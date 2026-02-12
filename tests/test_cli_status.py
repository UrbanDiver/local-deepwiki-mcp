"""Tests for the deepwiki status command (cli/status_cli.py)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_deepwiki.cli.status_cli import (
    _count_wiki_pages,
    _dir_size,
    _format_size,
    _format_timestamp,
    _scan_current_files,
    collect_status,
    display_status,
    main,
    run_status,
)
from local_deepwiki.models import FileInfo, IndexStatus


def _make_index_status(
    repo_path: str = "/tmp/repo",
    total_files: int = 5,
    total_chunks: int = 20,
    languages: dict | None = None,
    files: list | None = None,
    indexed_at: float | None = None,
) -> IndexStatus:
    """Factory for IndexStatus objects used in tests."""
    return IndexStatus(
        repo_path=repo_path,
        indexed_at=indexed_at or time.time(),
        total_files=total_files,
        total_chunks=total_chunks,
        languages=languages or {"python": 3, "typescript": 2},
        files=files or [],
        schema_version=2,
    )


# ── Utility tests ────────────────────────────────────────────────────


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(512) == "512 B"

    def test_kilobytes(self):
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert _format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert _format_size(2 * 1024 * 1024 * 1024) == "2.0 GB"

    def test_zero(self):
        assert _format_size(0) == "0 B"


class TestFormatTimestamp:
    def test_returns_string(self):
        result = _format_timestamp(1700000000.0)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_date_parts(self):
        result = _format_timestamp(1700000000.0)
        # Should contain year and time separator
        assert "-" in result
        assert ":" in result


class TestDirSize:
    def test_nonexistent_directory(self, tmp_path: Path):
        assert _dir_size(tmp_path / "nonexistent") == 0

    def test_empty_directory(self, tmp_path: Path):
        assert _dir_size(tmp_path) == 0

    def test_directory_with_files(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "b.txt").write_text("world!")
        size = _dir_size(tmp_path)
        assert size == 11  # 5 + 6


class TestCountWikiPages:
    def test_nonexistent_directory(self, tmp_path: Path):
        assert _count_wiki_pages(tmp_path / "none") == 0

    def test_empty_directory(self, tmp_path: Path):
        assert _count_wiki_pages(tmp_path) == 0

    def test_counts_md_files(self, tmp_path: Path):
        (tmp_path / "index.md").write_text("# Index")
        (tmp_path / "module.md").write_text("# Module")
        (tmp_path / "style.css").write_text("body {}")
        assert _count_wiki_pages(tmp_path) == 2

    def test_counts_nested_md_files(self, tmp_path: Path):
        sub = tmp_path / "files"
        sub.mkdir()
        (sub / "main.md").write_text("# Main")
        (tmp_path / "index.md").write_text("# Index")
        assert _count_wiki_pages(tmp_path) == 2


# ── Status with no index ─────────────────────────────────────────────


class TestStatusNoIndex:
    def test_not_indexed_returns_indexed_false(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        data = collect_status(wiki_path)
        assert data == {"indexed": False}

    def test_display_not_indexed(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        data = {"indexed": False}
        display_status(data, console)
        captured = capsys.readouterr()
        assert "Not indexed" in captured.out
        assert "deepwiki update" in captured.out

    def test_run_status_not_indexed(self, tmp_path: Path, capsys):
        wiki_path = tmp_path / ".deepwiki"
        result = run_status(wiki_path)
        assert result == 0


# ── Status with index ────────────────────────────────────────────────


class TestStatusWithIndex:
    def test_collects_all_sections(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create a fake index_status.json
        status = _make_index_status(repo_path=str(tmp_path))
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )
        # Create wiki pages
        (wiki_path / "index.md").write_text("# Index")
        (wiki_path / "module.md").write_text("# Module")

        data = collect_status(wiki_path)

        assert data["indexed"] is True
        assert data["repository"]["path"] == str(tmp_path)
        assert data["repository"]["schema_version"] == 2
        assert data["index"]["total_files"] == 5
        assert data["index"]["total_chunks"] == 20
        assert data["index"]["languages"] == {"python": 3, "typescript": 2}
        assert data["wiki"]["page_count"] == 2
        assert data["wiki"]["disk_usage_bytes"] > 0
        assert "freshness" in data

    def test_note_when_no_wiki_pages(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        status = _make_index_status(repo_path=str(tmp_path))
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        data = collect_status(wiki_path)
        assert data.get("note") == "Indexed but wiki not generated"

    def test_display_with_index(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        data = {
            "indexed": True,
            "repository": {
                "path": "/tmp/repo",
                "indexed_at_human": "2024-01-01 12:00:00",
                "schema_version": 2,
            },
            "index": {
                "total_files": 10,
                "total_chunks": 50,
                "languages": {"python": 7, "go": 3},
            },
            "wiki": {
                "page_count": 5,
                "disk_usage_human": "1.2 MB",
            },
            "freshness": {
                "status": "Fresh",
                "new_count": 0,
                "modified_count": 0,
                "deleted_count": 0,
            },
        }
        display_status(data, console)
        captured = capsys.readouterr()
        assert "Repository" in captured.out
        assert "Index" in captured.out
        assert "Wiki" in captured.out
        assert "Freshness" in captured.out
        assert "Fresh" in captured.out


# ── JSON output ──────────────────────────────────────────────────────


class TestStatusJson:
    def test_json_output_not_indexed(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"
        run_status(wiki_path, as_json=True, console=console)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"indexed": False}

    def test_json_output_with_index(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        status = _make_index_status(repo_path=str(tmp_path), indexed_at=1700000000.0)
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        run_status(wiki_path, as_json=True, console=console)
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["indexed"] is True
        assert "repository" in data
        assert "index" in data
        assert "wiki" in data
        assert data["repository"]["indexed_at"] == 1700000000.0

    def test_json_has_freshness(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        status = _make_index_status(repo_path=str(tmp_path))
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        run_status(wiki_path, as_json=True, console=console)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "freshness" in data
        assert "status" in data["freshness"]


# ── Verbose mode ─────────────────────────────────────────────────────


class TestStatusVerbose:
    def test_verbose_includes_file_lists(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create index with one file
        files = [
            FileInfo(
                path="old.py",
                hash="abc123",
                language="python",
                chunk_count=3,
                size_bytes=100,
                last_modified=1700000000.0,
            ),
        ]
        status = _make_index_status(
            repo_path=str(tmp_path),
            total_files=1,
            total_chunks=3,
            languages={"python": 1},
            files=files,
        )
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        # old.py is in index but not on disk → deleted
        data = collect_status(wiki_path, verbose=True)
        freshness = data["freshness"]
        assert "deleted_files" in freshness
        assert "old.py" in freshness["deleted_files"]

    def test_verbose_display_shows_files(self, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        data = {
            "indexed": True,
            "repository": {
                "path": "/tmp/repo",
                "indexed_at_human": "2024-01-01 12:00:00",
                "schema_version": 2,
            },
            "index": {
                "total_files": 5,
                "total_chunks": 20,
                "languages": {"python": 5},
            },
            "wiki": {"page_count": 3, "disk_usage_human": "100 KB"},
            "freshness": {
                "status": "Stale (2 files changed)",
                "new_count": 1,
                "modified_count": 1,
                "deleted_count": 0,
                "new_files": ["new_module.py"],
                "modified_files": ["main.py"],
            },
        }
        display_status(data, console)
        captured = capsys.readouterr()
        assert "Stale" in captured.out
        assert "new_module.py" in captured.out
        assert "main.py" in captured.out


# ── _scan_current_files ──────────────────────────────────────────────


class TestScanCurrentFiles:
    """Verify _scan_current_files mirrors the indexer's exclusion logic."""

    def test_includes_python_file(self, tmp_path: Path):
        (tmp_path / "app.py").write_text("print('hi')")
        result = _scan_current_files(tmp_path)
        assert "app.py" in result

    def test_skips_hidden_directories(self, tmp_path: Path):
        """Hidden dirs like .claude/ and .github/ should be excluded."""
        hidden = tmp_path / ".claude" / "helpers"
        hidden.mkdir(parents=True)
        (hidden / "script.js").write_text("console.log('test')")
        (tmp_path / "app.js").write_text("console.log('main')")

        result = _scan_current_files(tmp_path)
        assert "app.js" in result
        assert not any(".claude" in k for k in result)

    def test_skips_htmlcov_via_exclude_patterns(self, tmp_path: Path):
        """htmlcov/** is in default exclude_patterns and should be skipped."""
        cov = tmp_path / "htmlcov"
        cov.mkdir()
        (cov / "coverage.js").write_text("var x = 1;")
        (tmp_path / "main.js").write_text("var y = 2;")

        result = _scan_current_files(tmp_path)
        assert "main.js" in result
        assert not any("htmlcov" in k for k in result)

    def test_skips_node_modules(self, tmp_path: Path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("")
        (tmp_path / "app.js").write_text("")

        result = _scan_current_files(tmp_path)
        assert "app.js" in result
        assert not any("node_modules" in k for k in result)

    def test_skips_dotgit(self, tmp_path: Path):
        git_dir = tmp_path / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "pack.py").write_text("")
        assert _scan_current_files(tmp_path) == {}

    def test_skips_deepwiki(self, tmp_path: Path):
        wiki = tmp_path / ".deepwiki"
        wiki.mkdir()
        (wiki / "index.py").write_text("")
        assert _scan_current_files(tmp_path) == {}

    def test_empty_directory(self, tmp_path: Path):
        assert _scan_current_files(tmp_path) == {}

    def test_ignores_unrecognised_extensions(self, tmp_path: Path):
        (tmp_path / "data.csv").write_text("a,b,c")
        (tmp_path / "readme.md").write_text("# Hi")
        assert _scan_current_files(tmp_path) == {}


# ── Freshness detection ──────────────────────────────────────────────


class TestStatusFreshness:
    def test_fresh_when_no_changes(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Write a source file
        (tmp_path / "app.py").write_text("print('hello')")

        # Compute hash the same way status_cli does
        from local_deepwiki.core.parser import _compute_file_hash

        file_hash = _compute_file_hash(tmp_path / "app.py")

        files = [
            FileInfo(
                path="app.py",
                hash=file_hash,
                language="python",
                chunk_count=2,
                size_bytes=100,
                last_modified=1700000000.0,
            ),
        ]
        status = _make_index_status(
            repo_path=str(tmp_path),
            total_files=1,
            total_chunks=2,
            languages={"python": 1},
            files=files,
        )
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        data = collect_status(wiki_path)
        assert data["freshness"]["status"] == "Fresh"

    def test_stale_when_file_modified(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (tmp_path / "app.py").write_text("print('changed')")

        files = [
            FileInfo(
                path="app.py",
                hash="oldhash123",
                language="python",
                chunk_count=2,
                size_bytes=100,
                last_modified=1700000000.0,
            ),
        ]
        status = _make_index_status(
            repo_path=str(tmp_path),
            total_files=1,
            total_chunks=2,
            languages={"python": 1},
            files=files,
        )
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        data = collect_status(wiki_path)
        assert "Stale" in data["freshness"]["status"]
        assert data["freshness"]["modified_count"] >= 1

    def test_repo_not_found(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        status = _make_index_status(repo_path="/nonexistent/path")
        import json as json_mod

        (wiki_path / "index_status.json").write_text(
            json_mod.dumps(status.model_dump(), indent=2)
        )

        data = collect_status(wiki_path)
        assert data["freshness"]["status"] == "Repository not found"


# ── Main dispatch ────────────────────────────────────────────────────


class TestMainDispatch:
    def test_default_args(self, capsys):
        with patch.object(sys, "argv", ["deepwiki status"]):
            result = main()
        assert result == 0

    def test_help_flag(self):
        with patch.object(sys, "argv", ["deepwiki status", "--help"]):
            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    def test_json_flag(self, capsys):
        with patch.object(sys, "argv", ["deepwiki status", "--json"]):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "indexed" in data

    def test_custom_wiki_path(self, tmp_path: Path, capsys):
        wiki = tmp_path / "custom-wiki"
        with patch.object(sys, "argv", ["deepwiki status", str(wiki)]):
            result = main()
        assert result == 0
