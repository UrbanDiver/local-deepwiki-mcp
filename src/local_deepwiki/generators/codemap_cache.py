"""Persistent cache for codemap results.

Stores generated codemaps as JSON files in `.deepwiki/codemaps/{hash}.json`
with a configurable TTL (default 1 hour). Provides cache key generation,
read/write, and listing of recent cached codemaps.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

CODEMAP_CACHE_TTL = 3600


def get_cache_dir(wiki_path: Path | None) -> Path | None:
    """Get the codemap cache directory, creating it if needed."""
    if wiki_path is None:
        return None
    cache_dir = wiki_path / "codemaps"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def cache_key(query: str, focus: str, max_depth: int, max_nodes: int) -> str:
    """Generate a cache key from codemap parameters."""
    raw = f"{query}|{focus}|{max_depth}|{max_nodes}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def read_cache(wiki_path: Path | None, key: str) -> dict | None:
    """Read a cached codemap result if it exists and hasn't expired."""
    cache_dir = get_cache_dir(wiki_path)
    if cache_dir is None:
        return None

    cache_file = cache_dir / f"{key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > CODEMAP_CACHE_TTL:
            cache_file.unlink(missing_ok=True)
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(wiki_path: Path | None, key: str, result: dict) -> None:
    """Write a codemap result to the cache."""
    cache_dir = get_cache_dir(wiki_path)
    if cache_dir is None:
        return

    cache_data = {**result, "cached_at": time.time(), "cache_key": key}
    cache_file = cache_dir / f"{key}.json"
    try:
        cache_file.write_text(json.dumps(cache_data))
    except OSError:
        logger.debug(f"Failed to write codemap cache: {key}")


def list_cached_codemaps(wiki_path: Path | None) -> list[dict]:
    """List all cached codemaps with metadata."""
    cache_dir = get_cache_dir(wiki_path)
    if cache_dir is None:
        return []

    results = []
    now = time.time()
    for f in sorted(
        cache_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(f.read_text())
            cached_at = data.get("cached_at", 0)
            if now - cached_at > CODEMAP_CACHE_TTL:
                f.unlink(missing_ok=True)
                continue
            results.append(
                {
                    "cache_key": data.get("cache_key", f.stem),
                    "query": data.get("query", ""),
                    "focus": data.get("focus", ""),
                    "total_nodes": data.get("total_nodes", 0),
                    "total_edges": data.get("total_edges", 0),
                    "cached_at": cached_at,
                }
            )
        except (json.JSONDecodeError, OSError):
            continue

    return results[:20]
