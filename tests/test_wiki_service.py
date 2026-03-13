"""Tests for WikiService: wiki structure, page reading, and export."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch  # noqa: F401 (patch.dict uses 'sys.modules')

import pytest

from local_deepwiki.errors import ValidationError
from local_deepwiki.services.models import ExportResult
from local_deepwiki.services.wiki_service import WikiService


def _make_config(tmp_path: Path) -> MagicMock:
    config = MagicMock()
    config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    return config


class TestReadStructure:
    async def test_reads_toc_json(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        toc = {"pages": [{"path": "index.md", "title": "Overview"}], "sections": {}}
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        svc = WikiService(_make_config(tmp_path))
        result = await svc.read_structure(wiki_path)

        assert result["pages"][0]["path"] == "index.md"

    async def test_toc_json_as_list(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        toc_list = [{"path": "a.md", "title": "A"}]
        (wiki_path / "toc.json").write_text(json.dumps(toc_list))

        svc = WikiService(_make_config(tmp_path))
        result = await svc.read_structure(wiki_path)

        assert "pages" in result
        assert result["pages"][0]["path"] == "a.md"

    async def test_falls_back_to_file_scan(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        (wiki_path / "index.md").write_text("# Overview")
        sub = wiki_path / "modules"
        sub.mkdir()
        (sub / "core.md").write_text("# Core Module")

        svc = WikiService(_make_config(tmp_path))
        result = await svc.read_structure(wiki_path)

        assert "pages" in result
        assert "sections" in result
        top_paths = [p["path"] for p in result["pages"]]
        assert "index.md" in top_paths
        assert "modules" in result["sections"]

    async def test_nonexistent_wiki_raises(self, tmp_path: Path):
        wiki_path = tmp_path / "nonexistent"

        svc = WikiService(_make_config(tmp_path))
        with pytest.raises(ValidationError):
            await svc.read_structure(wiki_path)


class TestReadPage:
    async def test_reads_existing_page(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        (wiki_path / "index.md").write_text("# Hello World")

        svc = WikiService(_make_config(tmp_path))
        content = await svc.read_page(wiki_path, "index.md")

        assert content == "# Hello World"

    async def test_missing_page_raises(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)

        svc = WikiService(_make_config(tmp_path))
        with pytest.raises(ValidationError):
            await svc.read_page(wiki_path, "missing.md")

    async def test_oversized_page_raises(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        huge = wiki_path / "huge.md"

        with patch("local_deepwiki.services.wiki_service.MAX_WIKI_PAGE_SIZE", 100):
            huge.write_text("x" * 200)
            svc = WikiService(_make_config(tmp_path))
            with pytest.raises(ValidationError, match="Page too large"):
                await svc.read_page(wiki_path, "huge.md")


class TestExportHtml:
    async def test_exports_and_returns_result(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        (wiki_path / "index.md").write_text("# Test")
        output = tmp_path / "html_out"

        svc = WikiService(_make_config(tmp_path))

        mock_export = MagicMock()
        mock_iter = MagicMock()
        mock_iter.get_page_count.return_value = 5
        mock_iter_cls = MagicMock(return_value=mock_iter)

        with (
            patch.dict(
                "sys.modules",
                {
                    "local_deepwiki.export.html": MagicMock(export_to_html=mock_export),
                    "local_deepwiki.export.streaming": MagicMock(
                        WikiPageIterator=mock_iter_cls
                    ),
                },
            ),
        ):
            result = await svc.export_html(wiki_path, output)

        assert isinstance(result, ExportResult)
        assert result.pages_exported == 5
        assert result.format == "html"
        assert result.output_path == str(output)
        mock_export.assert_called_once_with(wiki_path, output)

    async def test_nonexistent_wiki_raises(self, tmp_path: Path):
        svc = WikiService(_make_config(tmp_path))
        with pytest.raises(ValidationError):
            await svc.export_html(tmp_path / "nope", tmp_path / "out")


class TestExportPdf:
    async def test_exports_single_file_pdf(self, tmp_path: Path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir(parents=True)
        (wiki_path / "index.md").write_text("# Test")
        output = tmp_path / "wiki.pdf"

        svc = WikiService(_make_config(tmp_path))

        mock_export = MagicMock()
        mock_iter = MagicMock()
        mock_iter.get_page_count.return_value = 3
        mock_iter_cls = MagicMock(return_value=mock_iter)

        with (
            patch.dict(
                "sys.modules",
                {
                    "local_deepwiki.export.pdf": MagicMock(export_to_pdf=mock_export),
                    "local_deepwiki.export.streaming": MagicMock(
                        WikiPageIterator=mock_iter_cls
                    ),
                },
            ),
        ):
            result = await svc.export_pdf(wiki_path, output, single_file=True)

        assert isinstance(result, ExportResult)
        assert result.pages_exported == 3
        assert result.format == "pdf"
        mock_export.assert_called_once_with(wiki_path, output, single_file=True)

    async def test_nonexistent_wiki_raises(self, tmp_path: Path):
        svc = WikiService(_make_config(tmp_path))
        with pytest.raises(ValidationError):
            await svc.export_pdf(tmp_path / "nope", tmp_path / "out.pdf")
