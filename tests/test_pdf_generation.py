"""Tests for PDF generation: PdfExporter, export_to_pdf, and edge cases."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock weasyprint before importing pdf module if native libraries aren't available
_weasyprint_mock = None
_weasyprint_available = False

try:
    from weasyprint import CSS as _CSS, HTML as _HTML  # noqa: F401

    _weasyprint_available = True
except (ImportError, OSError):
    _weasyprint_mock = MagicMock()
    _weasyprint_mock.HTML = MagicMock
    _weasyprint_mock.CSS = MagicMock
    sys.modules["weasyprint"] = _weasyprint_mock


def _check_weasyprint_functional() -> bool:
    """Check if WeasyPrint can actually create PDFs."""
    if not _weasyprint_available:
        return False
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from weasyprint import HTML; HTML(string='<html></html>').write_pdf()",
            ],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


_WEASYPRINT_FUNCTIONAL: bool | None = None


def weasyprint_functional() -> bool:
    """Check if WeasyPrint can actually generate PDFs."""
    global _WEASYPRINT_FUNCTIONAL
    if _WEASYPRINT_FUNCTIONAL is None:
        _WEASYPRINT_FUNCTIONAL = _check_weasyprint_functional()
    return _WEASYPRINT_FUNCTIONAL


from local_deepwiki.export.pdf import (
    PdfExporter,
    export_to_pdf,
)


class TestPdfExporter:
    """Tests for PdfExporter class."""

    @pytest.fixture
    def sample_wiki(self, tmp_path: Path) -> Path:
        """Create a sample wiki structure for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Overview\n\nWelcome to the wiki.")
        (wiki_path / "architecture.md").write_text("# Architecture\n\nSystem design.")

        modules_dir = wiki_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "index.md").write_text("# Modules\n\nModule overview.")
        (modules_dir / "core.md").write_text("# Core Module\n\nCore functionality.")

        toc = {
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
                {
                    "number": "3",
                    "title": "Modules",
                    "path": "modules/index.md",
                    "children": [
                        {
                            "number": "3.1",
                            "title": "Core Module",
                            "path": "modules/core.md",
                        }
                    ],
                },
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    def test_collect_pages_in_order(self, sample_wiki: Path, tmp_path: Path):
        """Test that pages are collected in TOC order."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(sample_wiki, output_path)

        toc_path = sample_wiki / "toc.json"
        toc_data = json.loads(toc_path.read_text())
        exporter.toc_entries = toc_data.get("entries", [])

        pages = exporter._collect_pages_in_order()

        assert len(pages) == 4
        assert pages[0].name == "index.md"
        assert pages[1].name == "architecture.md"

    def test_extract_paths_from_toc(self, sample_wiki: Path, tmp_path: Path):
        """Test extracting paths from nested TOC."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(sample_wiki, output_path)

        toc_entries = [
            {"title": "A", "path": "a.md"},
            {
                "title": "B",
                "path": "b.md",
                "children": [
                    {"title": "B1", "path": "b/b1.md"},
                    {"title": "B2", "path": "b/b2.md"},
                ],
            },
        ]

        paths: list[str] = []
        exporter._extract_paths_from_toc(toc_entries, paths)

        assert paths == ["a.md", "b.md", "b/b1.md", "b/b2.md"]

    def test_build_toc_html(self, sample_wiki: Path, tmp_path: Path):
        """Test building TOC HTML."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(sample_wiki, output_path)

        pages = [
            sample_wiki / "index.md",
            sample_wiki / "architecture.md",
        ]

        toc_html = exporter._build_toc_html(pages)

        assert '<div class="toc">' in toc_html
        assert '<div class="toc-item">' in toc_html
        assert "Overview" in toc_html
        assert "Architecture" in toc_html

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_single_creates_pdf(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_single creates a PDF file."""
        output_path = tmp_path / "output.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_path)
        result = exporter.export_single()

        assert result == output_path
        mock_html_class.assert_called_once()
        mock_html_instance.write_pdf.assert_called_once()

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_single_with_directory_output(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test export_single with directory as output path."""
        output_dir = tmp_path / "output_dir"
        output_dir.mkdir()

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_dir)
        result = exporter.export_single()

        assert result == output_dir / "documentation.pdf"

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_separate_creates_multiple_pdfs(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_separate creates multiple PDF files."""
        output_path = tmp_path / "pdfs"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_path)
        results = exporter.export_separate()

        assert len(results) == 4
        assert mock_html_instance.write_pdf.call_count == 4

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_separate_preserves_directory_structure(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_separate preserves directory structure."""
        output_path = tmp_path / "pdfs"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_path)
        results = exporter.export_separate()

        result_names = [p.name for p in results]
        assert "index.pdf" in result_names
        assert "architecture.pdf" in result_names
        assert "core.pdf" in result_names

        assert any("modules" in str(p) for p in results)


class TestExportToPdf:
    """Tests for the export_to_pdf convenience function."""

    @pytest.fixture
    def simple_wiki(self, tmp_path: Path) -> Path:
        """Create a simple wiki for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test\n\nHello world.")
        (wiki_path / "toc.json").write_text('{"entries": []}')
        return wiki_path

    def test_raises_for_nonexistent_wiki(self, tmp_path: Path):
        """Test that export raises for nonexistent wiki path."""
        with pytest.raises(ValueError, match="does not exist"):
            export_to_pdf(tmp_path / "nonexistent")

    @patch("local_deepwiki.export.pdf.HTML")
    def test_default_output_path_single(self, mock_html_class, simple_wiki: Path):
        """Test default output path for single file mode."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        result = export_to_pdf(simple_wiki, single_file=True)

        assert "Exported wiki to PDF" in result
        expected_path = simple_wiki.parent / ".deepwiki.pdf"
        assert str(expected_path) in result

    @patch("local_deepwiki.export.pdf.HTML")
    def test_default_output_path_separate(self, mock_html_class, simple_wiki: Path):
        """Test default output path for separate file mode."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        result = export_to_pdf(simple_wiki, single_file=False)

        assert "Exported 1 pages to PDFs" in result
        expected_path = simple_wiki.parent / ".deepwiki_pdfs"
        assert str(expected_path) in result

    @patch("local_deepwiki.export.pdf.HTML")
    def test_custom_output_path(
        self, mock_html_class, simple_wiki: Path, tmp_path: Path
    ):
        """Test custom output path."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        custom_output = tmp_path / "custom.pdf"
        result = export_to_pdf(simple_wiki, custom_output)

        assert "Exported wiki to PDF" in result
        assert str(custom_output) in result

    @patch("local_deepwiki.export.pdf.HTML")
    def test_string_paths_accepted(
        self, mock_html_class, simple_wiki: Path, tmp_path: Path
    ):
        """Test that string paths are accepted."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        custom_output = tmp_path / "output.pdf"
        result = export_to_pdf(str(simple_wiki), str(custom_output))

        assert "Exported wiki to PDF" in result


class TestPdfExporterEdgeCases:
    """Tests for PdfExporter edge cases."""

    @pytest.fixture
    def wiki_with_empty_paths(self, tmp_path: Path) -> Path:
        """Create a wiki with TOC entries that have empty paths."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Index")
        (wiki_path / "page.md").write_text("# Page")

        toc = {
            "entries": [
                {"number": "1", "title": "Index", "path": "index.md"},
                {"number": "2", "title": "Section Header", "path": ""},
                {"number": "3", "title": "Page", "path": "page.md"},
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    def test_handles_empty_toc_paths(self, wiki_with_empty_paths: Path, tmp_path: Path):
        """Test that empty TOC paths are skipped."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_with_empty_paths, output_path)

        toc_path = wiki_with_empty_paths / "toc.json"
        toc_data = json.loads(toc_path.read_text())
        exporter.toc_entries = toc_data.get("entries", [])

        paths: list[str] = []
        exporter._extract_paths_from_toc(exporter.toc_entries, paths)

        assert "" not in paths
        assert "index.md" in paths
        assert "page.md" in paths

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_separate_with_pdf_suffix_output(
        self, mock_html_class, tmp_path: Path
    ):
        """Test export_separate when output path has .pdf suffix."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        output_path = tmp_path / "output.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(wiki_path, output_path)
        results = exporter.export_separate()

        assert len(results) == 1
        assert results[0].parent.name == "output"
        assert results[0].suffix == ".pdf"

    def test_collect_pages_with_no_toc(self, tmp_path: Path):
        """Test collecting pages when no TOC exists."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "a.md").write_text("# A")
        (wiki_path / "b.md").write_text("# B")

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_path, output_path)

        pages = exporter._collect_pages_in_order()

        assert len(pages) == 2
        page_names = [p.name for p in pages]
        assert "a.md" in page_names
        assert "b.md" in page_names

    @patch("local_deepwiki.export.pdf.HTML")
    def test_build_combined_html_with_mermaid(self, mock_html_class, tmp_path: Path):
        """Test building combined HTML with mermaid diagrams."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text(
            "# Index\n\n```mermaid\ngraph TD\nA-->B\n```"
        )

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_path, output_path)

        pages = [wiki_path / "index.md"]
        html = exporter._build_combined_html(pages)

        assert "<!DOCTYPE html>" in html
        assert "<title>Documentation</title>" in html
        assert "Table of Contents" in html

    def test_toc_entries_with_missing_children_key(self, tmp_path: Path):
        """Test TOC entries without children key."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_path, output_path)

        toc_entries = [
            {"title": "A", "path": "a.md"},
            {"title": "B", "path": "b.md"},
        ]

        paths: list[str] = []
        exporter._extract_paths_from_toc(toc_entries, paths)

        assert paths == ["a.md", "b.md"]


class TestExportToPdfEdgeCases:
    """Additional edge case tests for export_to_pdf."""

    @patch("local_deepwiki.export.pdf.HTML")
    def test_accepts_path_as_string(self, mock_html_class, tmp_path: Path):
        """Test that wiki_path can be a string."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        result = export_to_pdf(str(wiki_path))
        assert "Exported wiki to PDF" in result


@pytest.mark.skipif(
    not weasyprint_functional(), reason="WeasyPrint not fully functional"
)
class TestPdfExportIntegration:
    """Integration tests that actually create PDF files."""

    @pytest.fixture
    def wiki_with_content(self, tmp_path: Path) -> Path:
        """Create a wiki with various content types for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("""# Documentation Overview

Welcome to the project documentation.

## Features

- Feature 1: Does something useful
- Feature 2: Does something else

## Quick Start

```python
from myproject import main
main()
```

| Column A | Column B |
|----------|----------|
| Value 1  | Value 2  |
""")

        (wiki_path / "architecture.md").write_text("""# Architecture

This document describes the system architecture.

## Components

The system consists of several components:

1. **Frontend**: User interface
2. **Backend**: API server
3. **Database**: Data storage

> Note: This is an important architecture decision.
""")

        modules_dir = wiki_path / "modules"
        modules_dir.mkdir()

        (modules_dir / "index.md").write_text("""# Modules

Overview of all modules in the project.
""")

        (modules_dir / "core.md").write_text("""# Core Module

The core module provides essential functionality.

## Functions

### `process_data(data: dict) -> dict`

Processes input data and returns results.

```python
def process_data(data: dict) -> dict:
    return {"processed": True, **data}
```
""")

        toc = {
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
                {
                    "number": "3",
                    "title": "Modules",
                    "path": "modules/index.md",
                    "children": [
                        {
                            "number": "3.1",
                            "title": "Core Module",
                            "path": "modules/core.md",
                        }
                    ],
                },
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    def test_export_single_creates_valid_pdf(
        self, wiki_with_content: Path, tmp_path: Path
    ):
        """Test that export_single creates a valid PDF file."""
        output_path = tmp_path / "output.pdf"

        exporter = PdfExporter(wiki_with_content, output_path)
        result = exporter.export_single()

        assert result.exists(), f"PDF file was not created at {result}"

        file_size = result.stat().st_size
        assert file_size > 0, "PDF file is empty"

        with open(result, "rb") as f:
            magic_bytes = f.read(8)
            assert magic_bytes[:5] == b"%PDF-", (
                f"Invalid PDF magic bytes: {magic_bytes!r}"
            )

        assert file_size > 1024, f"PDF seems too small: {file_size} bytes"

    def test_export_separate_creates_multiple_pdfs(
        self, wiki_with_content: Path, tmp_path: Path
    ):
        """Test that export_separate creates valid PDF files for each page."""
        output_dir = tmp_path / "pdfs"

        exporter = PdfExporter(wiki_with_content, output_dir)
        results = exporter.export_separate()

        assert len(results) == 4, f"Expected 4 PDFs, got {len(results)}"

        for pdf_path in results:
            assert pdf_path.exists(), f"PDF not created: {pdf_path}"
            assert pdf_path.stat().st_size > 0, f"PDF is empty: {pdf_path}"

            with open(pdf_path, "rb") as f:
                magic_bytes = f.read(5)
                assert magic_bytes == b"%PDF-", f"Invalid PDF at {pdf_path}"

    def test_export_to_pdf_function_creates_pdf(
        self, wiki_with_content: Path, tmp_path: Path
    ):
        """Test the convenience function creates a valid PDF."""
        output_path = tmp_path / "wiki.pdf"

        result_msg = export_to_pdf(wiki_with_content, output_path)

        assert "Exported wiki to PDF" in result_msg
        assert output_path.exists()
        assert output_path.stat().st_size > 1024

        with open(output_path, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_pdf_contains_expected_content(
        self, wiki_with_content: Path, tmp_path: Path
    ):
        """Test that the PDF contains expected text content."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_with_content, output_path)

        toc_path = wiki_with_content / "toc.json"
        toc_data = json.loads(toc_path.read_text())
        exporter.toc_entries = toc_data.get("entries", [])

        pages = exporter._collect_pages_in_order()
        html = exporter._build_combined_html(pages)

        assert "Documentation Overview" in html
        assert "Architecture" in html
        assert "Core Module" in html
        assert "process_data" in html
        assert "<table>" in html
        assert "<code" in html

    def test_pdf_with_special_characters(self, tmp_path: Path):
        """Test PDF generation with special characters in content."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("""# Special Characters Test

## Unicode Characters

- Arrows: \u2192 \u2190 \u2191 \u2193
- Greek: \u03b1 \u03b2 \u03b3 \u03b4
- Math: \u2211 \u222b \u221a \u221e
- Emoji: \U0001f680 \U0001f4dd \u2705

## Code with Special Chars

```python
def greet(name: str) -> str:
    return f"Hello, {name}! \U0001f44b"
```

## Quotes and Symbols

"Double quotes" and 'single quotes'

Copyright \u00a9 2024 \u2014 All rights reserved.
""")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "special.pdf"
        exporter = PdfExporter(wiki_path, output_path)
        result = exporter.export_single()

        assert result.exists()
        assert result.stat().st_size > 0
        with open(result, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_pdf_with_long_content(self, tmp_path: Path):
        """Test PDF generation with longer content (multiple pages)."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        long_content = "# Long Document\n\n"
        for i in range(50):
            long_content += f"## Section {i + 1}\n\n"
            long_content += (
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10
            )
            long_content += "\n\n"
            long_content += "```python\n"
            long_content += f"def function_{i}():\n"
            long_content += f"    return {i}\n"
            long_content += "```\n\n"

        (wiki_path / "index.md").write_text(long_content)
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "long.pdf"
        exporter = PdfExporter(wiki_path, output_path)
        result = exporter.export_single()

        assert result.exists()

        file_size = result.stat().st_size
        assert file_size > 50 * 1024, (
            f"PDF seems too small for long content: {file_size} bytes"
        )

        with open(result, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_pdf_with_empty_wiki(self, tmp_path: Path):
        """Test PDF generation with minimal content."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Empty\n")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "empty.pdf"
        exporter = PdfExporter(wiki_path, output_path)
        result = exporter.export_single()

        assert result.exists()
        assert result.stat().st_size > 0
        with open(result, "rb") as f:
            assert f.read(5) == b"%PDF-"
