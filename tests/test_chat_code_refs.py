"""Tests for chat code reference API endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_deepwiki.web.app import create_app


@pytest.fixture
def client(tmp_path):
    """Flask test client with a mock wiki path."""
    wiki_path = tmp_path / ".deepwiki"
    wiki_path.mkdir()
    app = create_app(str(wiki_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def wiki_with_search_json(tmp_path):
    """Wiki path with a search.json containing entities."""
    wiki_path = tmp_path / ".deepwiki"
    wiki_path.mkdir()
    search_data = {
        "pages": [],
        "entities": [
            {
                "type": "entity",
                "entity_type": "function",
                "name": "batch_embed",
                "path": "files/src/core/vectorstore/embedding.md",
                "file": "src/core/vectorstore/embedding.py",
            },
            {
                "type": "entity",
                "entity_type": "class",
                "name": "WikiGenerator",
                "path": "files/src/generators/wiki/generator.md",
                "file": "src/generators/wiki/generator.py",
            },
            {
                "type": "entity",
                "entity_type": "function",
                "name": "__init__",
                "path": "files/src/core/indexer.md",
                "file": "src/core/indexer.py",
            },
        ],
        "meta": {},
    }
    (wiki_path / "search.json").write_text(json.dumps(search_data))
    app = create_app(str(wiki_path))
    app.config["TESTING"] = True
    return app.test_client()


class TestEntityIndex:
    def test_returns_entity_map(self, wiki_with_search_json):
        resp = wiki_with_search_json.get("/api/entity-index")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "entities" in data
        assert "batch_embed" in data["entities"]
        assert (
            data["entities"]["batch_embed"]["page"]
            == "files/src/core/vectorstore/embedding.md"
        )
        assert data["entities"]["batch_embed"]["type"] == "function"

    def test_excludes_dunder_names(self, wiki_with_search_json):
        resp = wiki_with_search_json.get("/api/entity-index")
        data = resp.get_json()
        assert "__init__" not in data["entities"]

    def test_missing_search_json(self, client):
        resp = client.get("/api/entity-index")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["entities"] == {}

    def test_response_is_cached(self, wiki_with_search_json):
        resp = wiki_with_search_json.get("/api/entity-index")
        assert resp.headers.get("Cache-Control") == "public, max-age=300"


class TestCodeSnippet:
    def test_reads_file_with_line_range(self, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        src_file = tmp_path / "src" / "example.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        app = create_app(str(wiki_path))
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/api/code-snippet?file=src/example.py&start=2&end=4")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content"] == "line2\nline3\nline4"
        assert data["start"] == 2
        assert data["end"] == 4
        assert data["source"] == "file"
        assert data["language"] == "python"

    def test_returns_whole_file_without_range(self, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        src_file = tmp_path / "src" / "example.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("line1\nline2\nline3\n")

        app = create_app(str(wiki_path))
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/api/code-snippet?file=src/example.py")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "line1" in data["content"]

    def test_rejects_path_traversal(self, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        app = create_app(str(wiki_path))
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/api/code-snippet?file=../../etc/passwd")
        assert resp.status_code == 400

    def test_missing_file_param(self, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        app = create_app(str(wiki_path))
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/api/code-snippet")
        assert resp.status_code == 400

    def test_nonexistent_file(self, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        app = create_app(str(wiki_path))
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/api/code-snippet?file=src/nonexistent.py")
        assert resp.status_code == 404
