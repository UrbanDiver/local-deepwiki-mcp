"""Tests for cache management CLI."""

import argparse
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.cli.cache_cli import (
    EMBEDDING_CACHE_DB,
    _dir_size,
    _format_size,
    _get_embedding_stats,
    _get_llm_stats,
    _resolve_llm_cache_path,
    cmd_clear,
    cmd_cleanup,
    cmd_stats,
    main,
)


class TestResolveLLMCachePath:
    def test_default_repo(self):
        path = _resolve_llm_cache_path(".")
        assert path == Path(".").resolve() / ".deepwiki/llm_cache.lance"

    def test_custom_repo(self, tmp_path):
        path = _resolve_llm_cache_path(str(tmp_path))
        assert path == tmp_path / ".deepwiki/llm_cache.lance"


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(500) == "500 B"

    def test_kilobytes(self):
        assert _format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert _format_size(1048576) == "1.0 MB"

    def test_gigabytes(self):
        assert _format_size(1073741824) == "1.0 GB"

    def test_zero(self):
        assert _format_size(0) == "0 B"


class TestDirSize:
    def test_nonexistent_dir(self, tmp_path):
        assert _dir_size(tmp_path / "nonexistent") == 0

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert _dir_size(d) == 0

    def test_dir_with_files(self, tmp_path):
        d = tmp_path / "files"
        d.mkdir()
        (d / "a.txt").write_text("hello")
        (d / "b.txt").write_text("world")
        size = _dir_size(d)
        assert size > 0


class TestGetEmbeddingStats:
    def test_no_cache_file(self):
        with patch(
            "local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB",
            Path("/nonexistent/path/cache.db"),
        ):
            stats = _get_embedding_stats()
        assert stats["entry_count"] == 0

    def test_with_entries(self, tmp_path):
        db_path = tmp_path / "test_cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE embeddings (
                key TEXT, embedding TEXT, model TEXT,
                created_at REAL, last_accessed REAL
            )"""
        )
        now = time.time()
        conn.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)",
            ("k1", "[1,2,3]", "test", now - 3600, now),
        )
        conn.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)",
            ("k2", "[4,5,6]", "test", now - 7200, now),
        )
        conn.commit()
        conn.close()

        with patch("local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB", db_path):
            stats = _get_embedding_stats()

        assert stats["entry_count"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["oldest_entry"] != "N/A"
        assert stats["newest_entry"] != "N/A"

    def test_empty_table(self, tmp_path):
        db_path = tmp_path / "test_cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE embeddings (
                key TEXT, embedding TEXT, model TEXT,
                created_at REAL, last_accessed REAL
            )"""
        )
        conn.commit()
        conn.close()

        with patch("local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB", db_path):
            stats = _get_embedding_stats()

        assert stats["entry_count"] == 0


class TestGetLLMStats:
    def test_no_cache_dir(self, tmp_path):
        stats = _get_llm_stats(str(tmp_path / "no-repo"))
        assert stats["entry_count"] == 0
        assert stats["total_size_bytes"] == 0

    def test_with_lance_dir_no_table(self, tmp_path):
        lance_dir = tmp_path / ".deepwiki" / "llm_cache.lance"
        lance_dir.mkdir(parents=True)
        (lance_dir / "dummy.dat").write_text("data")

        mock_db = MagicMock()
        mock_db.table_names.return_value = []

        with patch("lancedb.connect", return_value=mock_db):
            stats = _get_llm_stats(str(tmp_path))

        assert stats["entry_count"] == 0

    def test_with_lance_table(self, tmp_path):
        lance_dir = tmp_path / ".deepwiki" / "llm_cache.lance"
        lance_dir.mkdir(parents=True)
        (lance_dir / "dummy.dat").write_text("data")

        mock_table = MagicMock()
        mock_table.count_rows.return_value = 42
        mock_db = MagicMock()
        mock_db.table_names.return_value = ["llm_cache"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db):
            stats = _get_llm_stats(str(tmp_path))

        assert stats["entry_count"] == 42


class TestCmdStats:
    def test_shows_table(self, capsys):
        args = argparse.Namespace(repo=".")
        with (
            patch(
                "local_deepwiki.cli.cache_cli._get_embedding_stats",
                return_value={
                    "entry_count": 10,
                    "total_size_bytes": 1024,
                    "oldest_entry": "2025-01-01 00:00",
                    "newest_entry": "2025-01-02 00:00",
                },
            ),
            patch(
                "local_deepwiki.cli.cache_cli._get_llm_stats",
                return_value={"entry_count": 5, "total_size_bytes": 2048},
            ),
        ):
            result = cmd_stats(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Embedding" in captured.out
        assert "LLM" in captured.out


class TestCmdClear:
    def test_clear_both_when_no_flags(self, tmp_path):
        # Create a test embedding DB
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE embeddings (
                key TEXT, embedding TEXT, model TEXT,
                created_at REAL, last_accessed REAL
            )"""
        )
        conn.execute("INSERT INTO embeddings VALUES ('k1', '[1]', 'test', 0, 0)")
        conn.commit()
        conn.close()

        args = argparse.Namespace(repo=str(tmp_path), llm=False, embedding=False)

        with patch("local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB", db_path):
            result = cmd_clear(args)

        assert result == 0

        # Verify embedding entries removed
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        conn.close()
        assert count == 0

    def test_clear_embedding_only(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE embeddings (
                key TEXT, embedding TEXT, model TEXT,
                created_at REAL, last_accessed REAL
            )"""
        )
        conn.execute("INSERT INTO embeddings VALUES ('k1', '[1]', 'test', 0, 0)")
        conn.commit()
        conn.close()

        args = argparse.Namespace(repo=str(tmp_path), llm=False, embedding=True)

        with patch("local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB", db_path):
            result = cmd_clear(args)

        assert result == 0

    def test_clear_llm_only(self, tmp_path):
        lance_dir = tmp_path / ".deepwiki" / "llm_cache.lance"
        lance_dir.mkdir(parents=True)
        (lance_dir / "data.lance").write_text("data")

        args = argparse.Namespace(repo=str(tmp_path), llm=True, embedding=False)
        result = cmd_clear(args)

        assert result == 0
        assert not lance_dir.exists()

    def test_clear_nonexistent_cache(self, tmp_path, capsys):
        args = argparse.Namespace(repo=str(tmp_path), llm=True, embedding=True)

        with patch(
            "local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB",
            tmp_path / "nonexistent.db",
        ):
            result = cmd_clear(args)

        assert result == 0


class TestCmdCleanup:
    def test_removes_expired_entries(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE embeddings (
                key TEXT, embedding TEXT, model TEXT,
                created_at REAL, last_accessed REAL
            )"""
        )
        now = time.time()
        # Old entry (8 days ago)
        conn.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)",
            ("old", "[1]", "test", now - 691200, now - 691200),
        )
        # Fresh entry
        conn.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)",
            ("new", "[2]", "test", now - 3600, now),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(repo=".")

        with patch("local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB", db_path):
            result = cmd_cleanup(args)

        assert result == 0

        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        conn.close()
        assert count == 1  # Only the fresh entry remains

    def test_no_expired_entries(self, tmp_path, capsys):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE embeddings (
                key TEXT, embedding TEXT, model TEXT,
                created_at REAL, last_accessed REAL
            )"""
        )
        conn.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)",
            ("new", "[1]", "test", time.time(), time.time()),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(repo=".")

        with patch("local_deepwiki.cli.cache_cli.EMBEDDING_CACHE_DB", db_path):
            result = cmd_cleanup(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No expired" in captured.out


class TestMainEntryPoint:
    def test_no_command_shows_help(self, capsys):
        with patch("sys.argv", ["deepwiki-cache"]):
            result = main()
        assert result == 0

    def test_stats_command(self):
        with patch("sys.argv", ["deepwiki-cache", "stats"]):
            with patch(
                "local_deepwiki.cli.cache_cli.cmd_stats", return_value=0
            ) as mock:
                result = main()
        assert result == 0
        mock.assert_called_once()

    def test_clear_command(self):
        with patch("sys.argv", ["deepwiki-cache", "clear", "--llm"]):
            with patch(
                "local_deepwiki.cli.cache_cli.cmd_clear", return_value=0
            ) as mock:
                result = main()
        assert result == 0
        mock.assert_called_once()

    def test_cleanup_command(self):
        with patch("sys.argv", ["deepwiki-cache", "cleanup"]):
            with patch(
                "local_deepwiki.cli.cache_cli.cmd_cleanup", return_value=0
            ) as mock:
                result = main()
        assert result == 0
        mock.assert_called_once()
