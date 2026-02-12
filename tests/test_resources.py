"""Tests for MCP Resource handlers (Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import AnyUrl

from local_deepwiki.errors import ValidationError
from local_deepwiki.handlers.resources import (
    DEEPWIKI_SCHEME,
    _find_wiki_directories,
    build_resource_uri,
    register_resource_handlers,
)


class TestBuildResourceUri:
    """Tests for build_resource_uri helper."""

    def test_basic_uri(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        uri = build_resource_uri(wiki_path, "index.md")
        assert uri == f"deepwiki://{wiki_path}/index.md"

    def test_nested_page(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        uri = build_resource_uri(wiki_path, "modules/core.md")
        assert uri == f"deepwiki://{wiki_path}/modules/core.md"


class TestFindWikiDirectories:
    """Tests for _find_wiki_directories."""

    def test_no_wikis(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = _find_wiki_directories()
        assert result == []

    def test_one_wiki(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        result = _find_wiki_directories()
        assert len(result) == 1
        assert result[0] == wiki_dir.resolve()

    def test_nested_wikis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "project_a" / ".deepwiki").mkdir(parents=True)
        (tmp_path / "project_b" / ".deepwiki").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        result = _find_wiki_directories()
        assert len(result) == 2


class TestRegisterResourceHandlers:
    """Tests for the registered resource handlers."""

    def _make_server_and_handlers(self):
        """Create a mock server and capture registered handlers."""
        handlers = {}

        class FakeServer:
            def list_resource_templates(self_inner):
                def decorator(func):
                    handlers["list_resource_templates"] = func
                    return func

                return decorator

            def list_resources(self_inner):
                def decorator(func):
                    handlers["list_resources"] = func
                    return func

                return decorator

            def read_resource(self_inner):
                def decorator(func):
                    handlers["read_resource"] = func
                    return func

                return decorator

        server = FakeServer()
        register_resource_handlers(server)
        return handlers

    async def test_list_resource_templates(self) -> None:
        handlers = self._make_server_and_handlers()
        templates = await handlers["list_resource_templates"]()
        assert len(templates) == 1
        assert "deepwiki" in templates[0].uriTemplate
        assert templates[0].mimeType == "text/markdown"

    async def test_list_resources_no_wikis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        handlers = self._make_server_and_handlers()
        resources = await handlers["list_resources"]()
        assert resources == []

    async def test_list_resources_with_pages(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()
        (wiki_dir / "index.md").write_text("# My Project\nOverview here.")
        (wiki_dir / "modules").mkdir()
        (wiki_dir / "modules" / "core.md").write_text("# Core Module\nDetails.")

        monkeypatch.chdir(tmp_path)
        handlers = self._make_server_and_handlers()
        resources = await handlers["list_resources"]()

        assert len(resources) == 2
        names = {r.name for r in resources}
        assert "My Project" in names
        assert "Core Module" in names
        for r in resources:
            assert r.mimeType == "text/markdown"

    async def test_read_resource_valid(self, tmp_path: Path) -> None:
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()
        (wiki_dir / "index.md").write_text("# Hello World")

        handlers = self._make_server_and_handlers()
        uri = AnyUrl(f"deepwiki://{wiki_dir}/index.md")
        result = await handlers["read_resource"](uri)
        assert len(result) == 1
        assert result[0].content == "# Hello World"
        assert result[0].mime_type == "text/markdown"

    async def test_read_resource_missing_page(self, tmp_path: Path) -> None:
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()

        handlers = self._make_server_and_handlers()
        uri = AnyUrl(f"deepwiki://{wiki_dir}/nonexistent.md")

        with pytest.raises(FileNotFoundError):
            await handlers["read_resource"](uri)

    async def test_read_resource_path_traversal(self, tmp_path: Path) -> None:
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()
        # Create a file outside the wiki
        (tmp_path / "secret.txt").write_text("secret")

        handlers = self._make_server_and_handlers()
        uri = AnyUrl(f"deepwiki://{wiki_dir}/../secret.txt")

        with pytest.raises(ValidationError):
            await handlers["read_resource"](uri)

    async def test_read_resource_invalid_scheme(self) -> None:
        handlers = self._make_server_and_handlers()
        uri = AnyUrl("https://example.com/index.md")

        with pytest.raises(ValidationError, match="Invalid URI scheme"):
            await handlers["read_resource"](uri)

    async def test_read_resource_no_page_path(self, tmp_path: Path) -> None:
        handlers = self._make_server_and_handlers()
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()
        # URI without a page after .deepwiki/
        uri = AnyUrl(f"deepwiki://{wiki_dir}/")

        # This should fail because page path is empty after strip
        with pytest.raises((ValidationError, FileNotFoundError)):
            await handlers["read_resource"](uri)
