"""Wiki service: wiki structure reading, page reading, and export.

Extracted from handlers/core.py handle_read_wiki_structure,
handle_read_wiki_page, handle_export_wiki_html, handle_export_wiki_pdf.
RBAC permission checks and audit logging remain in the handler layer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config
from local_deepwiki.core.path_utils import validate_sub_path
from local_deepwiki.errors import ValidationError, path_not_found_error
from local_deepwiki.logging import get_logger
from local_deepwiki.validation import MAX_WIKI_PAGE_SIZE

from .models import ExportResult

logger = get_logger(__name__)


class WikiService:
    """Encapsulates wiki reading and export operations.

    Depends only on Config; does not interact with LLM or vector store.
    """

    __slots__ = ("_config",)

    def __init__(self, config: Config) -> None:
        self._config = config

    async def read_structure(self, wiki_path: Path) -> dict[str, Any]:
        """Read wiki table of contents and structure.

        Checks for toc.json first, then falls back to dynamic generation
        by scanning markdown files. Supports lazy generation via entity
        registry.

        Args:
            wiki_path: Resolved path to the wiki directory.

        Returns:
            Dict with 'pages' and optionally 'sections' keys.

        Raises:
            DeepWikiError: If wiki_path does not exist and has no
                entity registry for lazy generation.
        """
        if not wiki_path.exists():
            entity_reg = wiki_path / "entity_registry.json"
            index_status_file = wiki_path / "index_status.json"
            if entity_reg.exists() or index_status_file.exists():
                from local_deepwiki.generators.lazy_generator import (
                    get_lazy_generator,
                )

                generator = get_lazy_generator(wiki_path)
                return generator.get_virtual_structure()
            raise path_not_found_error(str(wiki_path), "wiki")

        toc_path = wiki_path / "toc.json"
        if toc_path.exists():
            try:
                toc_content = await asyncio.to_thread(toc_path.read_text)
                toc_data = json.loads(toc_content)
                return toc_data if isinstance(toc_data, dict) else {"pages": toc_data}
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("toc.json could not be read, falling back: %s", e)

        return await self._build_structure_from_files(wiki_path)

    async def read_page(self, wiki_path: Path, page: str) -> str:
        """Read a single wiki page's content.

        Args:
            wiki_path: Resolved path to the wiki directory.
            page: Relative path to the page within the wiki.

        Returns:
            The page content as a string.

        Raises:
            DeepWikiError: If the page does not exist.
            ValidationError: If the page exceeds size limits.
        """
        page_path = validate_sub_path(
            wiki_path,
            page,
            field="page",
            hint="The page path must be within the wiki directory.",
        )

        if not page_path.exists():
            entity_reg = wiki_path / "entity_registry.json"
            index_status_file = wiki_path / "index_status.json"
            if entity_reg.exists() or index_status_file.exists():
                from local_deepwiki.generators.lazy_generator import (
                    get_lazy_generator,
                )

                generator = get_lazy_generator(wiki_path)
                page_relative = str(page_path.relative_to(wiki_path))
                return await generator.get_page(page_relative)
            raise path_not_found_error(page, "wiki page")

        file_size = page_path.stat().st_size
        if file_size > MAX_WIKI_PAGE_SIZE:
            raise ValidationError(
                message=f"Page too large: {file_size:,} bytes",
                hint=f"Maximum allowed size is {MAX_WIKI_PAGE_SIZE:,} bytes. "
                "Consider splitting the content.",
                field="page",
                value=page,
                context={"file_size": file_size, "max_size": MAX_WIKI_PAGE_SIZE},
            )

        return await asyncio.to_thread(page_path.read_text)

    async def export_html(
        self,
        wiki_path: Path,
        output: Path,
    ) -> ExportResult:
        """Export wiki to static HTML.

        Args:
            wiki_path: Resolved path to the wiki directory.
            output: Validated output directory path.

        Returns:
            ExportResult with output path and page count.

        Raises:
            DeepWikiError: If wiki_path does not exist.
        """
        if not wiki_path.exists():
            raise path_not_found_error(str(wiki_path), "wiki")

        from local_deepwiki.export.html import export_to_html
        from local_deepwiki.export.streaming import WikiPageIterator

        iterator = WikiPageIterator(wiki_path)
        page_count = iterator.get_page_count()

        export_to_html(wiki_path, output)

        return ExportResult(
            output_path=str(output),
            pages_exported=page_count,
            format="html",
        )

    async def export_pdf(
        self,
        wiki_path: Path,
        output: Path,
        *,
        single_file: bool = True,
    ) -> ExportResult:
        """Export wiki to PDF.

        Args:
            wiki_path: Resolved path to the wiki directory.
            output: Validated output path.
            single_file: Combine all pages into a single PDF.

        Returns:
            ExportResult with output path and page count.

        Raises:
            DeepWikiError: If wiki_path does not exist.
        """
        if not wiki_path.exists():
            raise path_not_found_error(str(wiki_path), "wiki")

        from local_deepwiki.export.pdf import export_to_pdf
        from local_deepwiki.export.streaming import WikiPageIterator

        iterator = WikiPageIterator(wiki_path)
        page_count = iterator.get_page_count()

        export_to_pdf(wiki_path, output, single_file=single_file)

        return ExportResult(
            output_path=str(output),
            pages_exported=page_count,
            format="pdf",
        )

    @staticmethod
    async def _build_structure_from_files(wiki_path: Path) -> dict[str, Any]:
        """Build wiki structure by scanning markdown files."""
        pages: list[dict[str, str]] = []
        for md_file in wiki_path.rglob("*.md"):
            rel_path = str(md_file.relative_to(wiki_path))
            try:
                file_content = await asyncio.to_thread(md_file.read_text)
                first_line = file_content.split("\n", 1)[0].strip()
                title = (
                    first_line.lstrip("#").strip()
                    if first_line.startswith("#")
                    else rel_path
                )
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Could not read title from %s: %s", md_file, e)
                title = rel_path

            pages.append({"path": rel_path, "title": title})

        structure: dict[str, Any] = {"pages": [], "sections": {}}

        for page in sorted(pages, key=lambda p: p["path"]):
            parts = Path(page["path"]).parts
            if len(parts) == 1:
                structure["pages"].append(page)
            else:
                section = parts[0]
                if section not in structure["sections"]:
                    structure["sections"][section] = []
                structure["sections"][section].append(page)

        return structure
