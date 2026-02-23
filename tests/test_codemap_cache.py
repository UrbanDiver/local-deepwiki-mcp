"""Tests for the codemap cache module."""

import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.generators.codemap.cache import (
    CODEMAP_CACHE_TTL,
    cache_key,
    get_cache_dir,
    list_cached_codemaps,
    read_cache,
    write_cache,
)


class TestGetCacheDir:
    """Test suite for get_cache_dir."""

    def test_returns_none_when_wiki_path_is_none(self):
        """Should return None when wiki_path is None."""
        result = get_cache_dir(None)
        assert result is None

    def test_returns_codemaps_subdirectory(self, tmp_path):
        """Should return a path ending in 'codemaps'."""
        result = get_cache_dir(tmp_path)
        assert result == tmp_path / "codemaps"

    def test_creates_directory_if_not_exists(self, tmp_path):
        """Should create the codemaps directory when it does not exist."""
        codemaps_dir = tmp_path / "codemaps"
        assert not codemaps_dir.exists()

        get_cache_dir(tmp_path)

        assert codemaps_dir.exists()
        assert codemaps_dir.is_dir()

    def test_succeeds_when_directory_already_exists(self, tmp_path):
        """Should not raise when the codemaps directory already exists."""
        codemaps_dir = tmp_path / "codemaps"
        codemaps_dir.mkdir()

        result = get_cache_dir(tmp_path)
        assert result == codemaps_dir

    def test_returns_path_object(self, tmp_path):
        """Should return a Path instance."""
        result = get_cache_dir(tmp_path)
        assert isinstance(result, Path)


class TestCacheKey:
    """Test suite for cache_key."""

    def test_returns_string(self):
        """Should return a string value."""
        result = cache_key("query", "execution_flow", 3, 20)
        assert isinstance(result, str)

    def test_returns_16_character_hex(self):
        """Should return a 16-character hex string."""
        result = cache_key("test", "execution_flow", 5, 30)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic_output(self):
        """Should return the same key for the same inputs."""
        key_a = cache_key("query", "data_flow", 3, 20)
        key_b = cache_key("query", "data_flow", 3, 20)
        assert key_a == key_b

    def test_different_queries_produce_different_keys(self):
        """Should produce different keys for different query strings."""
        key_a = cache_key("auth flow", "execution_flow", 3, 20)
        key_b = cache_key("database init", "execution_flow", 3, 20)
        assert key_a != key_b

    def test_different_focus_produces_different_keys(self):
        """Should produce different keys for different focus values."""
        key_a = cache_key("query", "execution_flow", 3, 20)
        key_b = cache_key("query", "data_flow", 3, 20)
        assert key_a != key_b

    def test_different_depth_produces_different_keys(self):
        """Should produce different keys for different max_depth values."""
        key_a = cache_key("query", "execution_flow", 3, 20)
        key_b = cache_key("query", "execution_flow", 5, 20)
        assert key_a != key_b

    def test_different_nodes_produces_different_keys(self):
        """Should produce different keys for different max_nodes values."""
        key_a = cache_key("query", "execution_flow", 3, 20)
        key_b = cache_key("query", "execution_flow", 3, 40)
        assert key_a != key_b

    def test_matches_expected_sha256_prefix(self):
        """Should match the first 16 chars of the SHA256 of the formatted input."""
        raw = "test_query|execution_flow|3|20"
        expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
        result = cache_key("test_query", "execution_flow", 3, 20)
        assert result == expected

    def test_empty_query_does_not_raise(self):
        """Should handle empty query string without error."""
        result = cache_key("", "execution_flow", 0, 0)
        assert len(result) == 16


class TestWriteCache:
    """Test suite for write_cache."""

    def test_writes_json_file(self, tmp_path):
        """Should create a JSON file in the cache directory."""
        write_cache(tmp_path, "abc123", {"query": "test"})

        cache_file = tmp_path / "codemaps" / "abc123.json"
        assert cache_file.exists()

    def test_written_file_contains_valid_json(self, tmp_path):
        """Should write valid JSON that can be parsed back."""
        write_cache(tmp_path, "abc123", {"query": "test", "nodes": 5})

        cache_file = tmp_path / "codemaps" / "abc123.json"
        data = json.loads(cache_file.read_text())
        assert data["query"] == "test"
        assert data["nodes"] == 5

    def test_adds_cached_at_timestamp(self, tmp_path):
        """Should add a cached_at field with the current timestamp."""
        before = time.time()
        write_cache(tmp_path, "abc123", {"query": "test"})
        after = time.time()

        cache_file = tmp_path / "codemaps" / "abc123.json"
        data = json.loads(cache_file.read_text())
        assert before <= data["cached_at"] <= after

    def test_adds_cache_key_field(self, tmp_path):
        """Should add the cache_key to the stored data."""
        write_cache(tmp_path, "mykey99", {"query": "test"})

        cache_file = tmp_path / "codemaps" / "mykey99.json"
        data = json.loads(cache_file.read_text())
        assert data["cache_key"] == "mykey99"

    def test_does_not_mutate_original_result(self, tmp_path):
        """Should not modify the original result dict passed in."""
        original = {"query": "test"}
        write_cache(tmp_path, "abc123", original)
        assert "cached_at" not in original
        assert "cache_key" not in original

    def test_returns_none_when_wiki_path_is_none(self):
        """Should return None and not raise when wiki_path is None."""
        result = write_cache(None, "abc123", {"query": "test"})
        assert result is None

    def test_handles_write_error_gracefully(self, tmp_path):
        """Should catch OSError and not raise on write failure."""
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            # Should not raise
            write_cache(tmp_path, "abc123", {"query": "test"})


class TestReadCache:
    """Test suite for read_cache."""

    def test_returns_cached_data(self, tmp_path):
        """Should return the cached data for a valid, fresh entry."""
        write_cache(tmp_path, "key1", {"query": "hello", "total_nodes": 10})

        result = read_cache(tmp_path, "key1")
        assert result is not None
        assert result["query"] == "hello"
        assert result["total_nodes"] == 10

    def test_returns_none_when_wiki_path_is_none(self):
        """Should return None when wiki_path is None."""
        result = read_cache(None, "key1")
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path):
        """Should return None when the cache file does not exist."""
        get_cache_dir(tmp_path)  # Ensure directory exists
        result = read_cache(tmp_path, "nonexistent_key")
        assert result is None

    def test_returns_none_for_expired_entry(self, tmp_path):
        """Should return None and delete the file when TTL has expired."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "expired.json"

        expired_time = time.time() - CODEMAP_CACHE_TTL - 100
        data = {"query": "old", "cached_at": expired_time}
        cache_file.write_text(json.dumps(data))

        result = read_cache(tmp_path, "expired")
        assert result is None
        assert not cache_file.exists()

    def test_returns_data_when_within_ttl(self, tmp_path):
        """Should return data when cached_at is within the TTL window."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "fresh.json"

        fresh_time = time.time() - 10  # 10 seconds ago
        data = {"query": "recent", "cached_at": fresh_time}
        cache_file.write_text(json.dumps(data))

        result = read_cache(tmp_path, "fresh")
        assert result is not None
        assert result["query"] == "recent"

    def test_returns_none_for_corrupted_json(self, tmp_path):
        """Should return None for a file with invalid JSON."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "bad.json"
        cache_file.write_text("this is not json {{{")

        result = read_cache(tmp_path, "bad")
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        """Should return None for an empty file."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "empty.json"
        cache_file.write_text("")

        result = read_cache(tmp_path, "empty")
        assert result is None

    def test_ttl_boundary_exactly_at_expiry(self, tmp_path):
        """Should expire when time difference is exactly CODEMAP_CACHE_TTL + 1."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "boundary.json"

        now = 1700000000.0
        data = {"query": "boundary", "cached_at": now - CODEMAP_CACHE_TTL - 1}
        cache_file.write_text(json.dumps(data))

        with patch("local_deepwiki.generators.codemap.cache.time") as mock_time:
            mock_time.time.return_value = now
            result = read_cache(tmp_path, "boundary")

        assert result is None

    def test_ttl_boundary_just_before_expiry(self, tmp_path):
        """Should return data when time difference is less than CODEMAP_CACHE_TTL."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "justfresh.json"

        now = 1700000000.0
        data = {"query": "justfresh", "cached_at": now - CODEMAP_CACHE_TTL + 1}
        cache_file.write_text(json.dumps(data))

        with patch("local_deepwiki.generators.codemap.cache.time") as mock_time:
            mock_time.time.return_value = now
            result = read_cache(tmp_path, "justfresh")

        assert result is not None
        assert result["query"] == "justfresh"

    def test_missing_cached_at_field_treats_as_expired(self, tmp_path):
        """Should treat entries missing cached_at as expired (defaults to 0)."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()
        cache_file = cache_dir / "nocachedat.json"

        data = {"query": "no timestamp"}
        cache_file.write_text(json.dumps(data))

        result = read_cache(tmp_path, "nocachedat")
        assert result is None


class TestListCachedCodemaps:
    """Test suite for list_cached_codemaps."""

    def test_returns_empty_list_when_wiki_path_is_none(self):
        """Should return an empty list when wiki_path is None."""
        result = list_cached_codemaps(None)
        assert result == []

    def test_returns_empty_list_for_empty_cache(self, tmp_path):
        """Should return an empty list when no cache files exist."""
        result = list_cached_codemaps(tmp_path)
        assert result == []

    def test_lists_single_entry(self, tmp_path):
        """Should list a single valid cached codemap."""
        write_cache(
            tmp_path,
            "key1",
            {
                "query": "test",
                "focus": "execution_flow",
                "total_nodes": 5,
                "total_edges": 4,
            },
        )

        result = list_cached_codemaps(tmp_path)
        assert len(result) == 1
        assert result[0]["query"] == "test"
        assert result[0]["focus"] == "execution_flow"
        assert result[0]["total_nodes"] == 5
        assert result[0]["total_edges"] == 4

    def test_lists_multiple_entries(self, tmp_path):
        """Should list multiple valid cached codemaps."""
        write_cache(tmp_path, "key1", {"query": "first"})
        write_cache(tmp_path, "key2", {"query": "second"})
        write_cache(tmp_path, "key3", {"query": "third"})

        result = list_cached_codemaps(tmp_path)
        assert len(result) == 3

    def test_excludes_expired_entries(self, tmp_path):
        """Should exclude and delete expired cache entries."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()

        # Write a fresh entry via the API
        write_cache(tmp_path, "fresh", {"query": "still valid"})

        # Write an expired entry directly
        expired_file = cache_dir / "old.json"
        expired_data = {"query": "expired", "cached_at": 0, "cache_key": "old"}
        expired_file.write_text(json.dumps(expired_data))

        result = list_cached_codemaps(tmp_path)

        queries = [r["query"] for r in result]
        assert "still valid" in queries
        assert "expired" not in queries
        assert not expired_file.exists()

    def test_skips_corrupted_json_files(self, tmp_path):
        """Should skip files with invalid JSON without raising."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()

        bad_file = cache_dir / "corrupt.json"
        bad_file.write_text("not valid json!!!")

        write_cache(tmp_path, "good", {"query": "valid"})

        result = list_cached_codemaps(tmp_path)
        assert len(result) == 1
        assert result[0]["query"] == "valid"

    def test_limits_results_to_20(self, tmp_path):
        """Should return at most 20 entries."""
        now = time.time()
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()

        for i in range(25):
            data = {
                "query": f"query_{i}",
                "cached_at": now - i,
                "cache_key": f"key_{i}",
            }
            cache_file = cache_dir / f"key_{i}.json"
            cache_file.write_text(json.dumps(data))

        result = list_cached_codemaps(tmp_path)
        assert len(result) == 20

    def test_uses_cache_key_from_data_or_stem(self, tmp_path):
        """Should use cache_key from JSON data, falling back to file stem."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()

        # Entry with cache_key in data
        data_with_key = {
            "query": "has key",
            "cached_at": time.time(),
            "cache_key": "explicit_key",
        }
        (cache_dir / "explicit_key.json").write_text(json.dumps(data_with_key))

        # Entry without cache_key in data (falls back to f.stem)
        data_no_key = {
            "query": "no key",
            "cached_at": time.time(),
        }
        (cache_dir / "stem_fallback.json").write_text(json.dumps(data_no_key))

        result = list_cached_codemaps(tmp_path)
        keys = [r["cache_key"] for r in result]
        assert "explicit_key" in keys
        assert "stem_fallback" in keys

    def test_returns_default_values_for_missing_fields(self, tmp_path):
        """Should fill in defaults for missing query, focus, total_nodes, total_edges."""
        cache_dir = tmp_path / "codemaps"
        cache_dir.mkdir()

        data = {"cached_at": time.time()}
        (cache_dir / "minimal.json").write_text(json.dumps(data))

        result = list_cached_codemaps(tmp_path)
        assert len(result) == 1
        entry = result[0]
        assert entry["query"] == ""
        assert entry["focus"] == ""
        assert entry["total_nodes"] == 0
        assert entry["total_edges"] == 0


class TestRoundTrip:
    """Integration tests for write -> read -> list cycle."""

    def test_write_then_read_returns_same_data(self, tmp_path):
        """Should be able to write and immediately read back the same data."""
        original = {"query": "auth", "focus": "execution_flow", "total_nodes": 12}
        key = cache_key("auth", "execution_flow", 3, 20)

        write_cache(tmp_path, key, original)
        result = read_cache(tmp_path, key)

        assert result is not None
        assert result["query"] == "auth"
        assert result["focus"] == "execution_flow"
        assert result["total_nodes"] == 12

    def test_write_then_list_includes_entry(self, tmp_path):
        """Should list an entry that was just written."""
        key = cache_key("db init", "data_flow", 5, 30)
        write_cache(tmp_path, key, {"query": "db init", "focus": "data_flow"})

        entries = list_cached_codemaps(tmp_path)
        assert any(e["query"] == "db init" for e in entries)
