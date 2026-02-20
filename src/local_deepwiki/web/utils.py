"""Shared utilities for web route blueprints."""

from __future__ import annotations

from pathlib import Path


def get_wiki_path() -> Path | None:
    """Retrieve the current WIKI_PATH, preferring Flask app config.

    Checks current_app.config first (set by create_app), which works even
    when the server is launched via ``python -m`` where __main__ and the
    importable module are separate objects.  Falls back to the module-level
    global for backward compatibility with tests that monkeypatch it directly.
    """
    from flask import current_app

    path = current_app.config.get("WIKI_PATH")
    if path is not None:
        return path

    from local_deepwiki.web import app as _app_module

    return _app_module.WIKI_PATH
