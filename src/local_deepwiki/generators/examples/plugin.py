"""Wiki generator plugin for code examples.

This plugin generates an Examples page that aggregates usage examples
from test files and docstrings across the codebase.
"""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import Any

from local_deepwiki.generators.examples.orchestrator import (
    CodeExample,
    CodeExampleExtractor,
    format_code_examples_markdown,
    parse_docstring_examples,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, IndexStatus, WikiPage
from local_deepwiki.plugins.base import (
    PluginMetadata,
    WikiGeneratorPlugin,
    WikiGeneratorResult,
)

logger = get_logger(__name__)


class ExamplesWikiGenerator(WikiGeneratorPlugin):
    """Generate Examples sections for API documentation.

    This plugin:
    1. Scans all function and class chunks for docstring examples
    2. Searches test files for usage examples
    3. Generates a comprehensive Examples page
    4. Optionally adds examples to individual API doc pages
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name="examples-generator",
            version="1.0.0",
            description="Generate code examples from tests and docstrings",
            author="local-deepwiki",
        )

    @property
    def generator_name(self) -> str:
        """Get the generator name."""
        return "examples"

    @property
    def priority(self) -> int:
        """Run after main generators but before cross-linking."""
        return 50

    @property
    def run_after(self) -> list[str]:
        """Run after the api_docs generator if present."""
        return []

    async def _collect_function_examples(
        self,
        function_results: list[Any],
        extractor: CodeExampleExtractor,
        all_examples: dict[str, list[CodeExample]],
    ) -> None:
        """Collect examples for function chunks, updating *all_examples* in-place."""
        for result in function_results:
            chunk = result.chunk
            if not chunk.name or len(chunk.name) <= 2:
                continue
            if chunk.name.startswith(("test_", "_")):
                continue

            examples = await extractor.extract_examples_for_function(
                chunk.name, max_examples=2
            )
            if chunk.docstring:
                doc_examples = parse_docstring_examples(chunk.docstring)
                examples.extend(
                    dataclasses.replace(ex, entity_name=chunk.name)
                    for ex in doc_examples
                )
            if examples:
                all_examples[chunk.name] = examples[:3]

    async def _collect_class_examples(
        self,
        class_results: list[Any],
        extractor: CodeExampleExtractor,
        all_examples: dict[str, list[CodeExample]],
    ) -> None:
        """Collect examples for class chunks, updating *all_examples* in-place."""
        for result in class_results:
            chunk = result.chunk
            if not chunk.name or len(chunk.name) <= 2:
                continue
            if chunk.name.startswith("_"):
                continue

            examples = await extractor.extract_examples_for_class(
                chunk.name, max_examples=2
            )
            if chunk.docstring:
                doc_examples = parse_docstring_examples(chunk.docstring)
                examples.extend(
                    dataclasses.replace(ex, entity_name=chunk.name)
                    for ex in doc_examples
                )
            if examples:
                all_examples[chunk.name] = examples[:3]

    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages with code examples.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with vector_store, llm, config, existing_pages.

        Returns:
            WikiGeneratorResult with generated examples page.
        """
        vector_store = context.get("vector_store")
        if vector_store is None:
            logger.debug("No vector_store in context, skipping examples generation")
            return WikiGeneratorResult(pages=[])

        repo_path = Path(index_status.repo_path)
        extractor = CodeExampleExtractor(vector_store, repo_path)
        all_examples: dict[str, list[CodeExample]] = {}

        try:
            function_results = await vector_store.search(
                query="function definition", limit=100, chunk_type="function"
            )
            class_results = await vector_store.search(
                query="class definition", limit=50, chunk_type="class"
            )
            await self._collect_function_examples(
                function_results, extractor, all_examples
            )
            await self._collect_class_examples(class_results, extractor, all_examples)
        except Exception as e:  # noqa: BLE001 — plugin isolation
            logger.debug("Error extracting examples: %s", e)
            return WikiGeneratorResult(pages=[])

        if not all_examples:
            logger.debug("No examples found in codebase")
            return WikiGeneratorResult(pages=[])

        content = self._generate_examples_page(all_examples, index_status)
        page = WikiPage(
            path="examples.md",
            title="Code Examples",
            content=content,
            generated_at=time.time(),
        )

        logger.info("Generated examples page with %s entities", len(all_examples))
        return WikiGeneratorResult(
            pages=[page],
            metadata={"total_entities": len(all_examples)},
        )

    @staticmethod
    def _add_test_examples_section(
        lines: list[str],
        test_examples: dict[str, list[CodeExample]],
    ) -> None:
        """Append the 'Examples from Tests' section to *lines* in-place."""
        lines.extend(
            [
                "## Examples from Tests",
                "",
                "Real-world usage patterns extracted from test files.",
                "",
            ]
        )
        for entity_name in sorted(test_examples):
            lines.append(f"### `{entity_name}`\n")
            for ex in test_examples[entity_name][:2]:
                if ex.description:
                    lines.append(f"*{ex.description}*\n")
                if ex.test_file:
                    lines.append(f"From `{ex.test_file}`:\n")
                lang = ex.language or "python"
                lines.append(f"```{lang}\n{ex.code}\n```\n")

    @staticmethod
    def _add_docstring_examples_section(
        lines: list[str],
        docstring_examples: dict[str, list[CodeExample]],
    ) -> None:
        """Append the 'Examples from Documentation' section to *lines* in-place."""
        lines.extend(
            [
                "## Examples from Documentation",
                "",
                "Examples extracted from docstrings.",
                "",
            ]
        )
        for entity_name in sorted(docstring_examples):
            lines.append(f"### `{entity_name}`\n")
            for ex in docstring_examples[entity_name][:2]:
                if ex.description:
                    lines.append(f"*{ex.description}*\n")
                lang = ex.language or "python"
                lines.append(f"```{lang}\n{ex.code}\n```\n")
                if ex.expected_output:
                    lines.append(f"Output:\n```\n{ex.expected_output}\n```\n")

    @staticmethod
    def _generate_examples_page(
        examples_by_entity: dict[str, list[CodeExample]],
        index_status: IndexStatus,
    ) -> str:
        """Generate the examples page content.

        Args:
            examples_by_entity: Mapping of entity name to examples.
            index_status: Index status for repo info.

        Returns:
            Markdown content for the examples page.
        """
        lines = [
            "# Code Examples",
            "",
            "This page contains usage examples extracted from test files and docstrings.",
            "",
            f"**Total entities with examples:** {len(examples_by_entity)}",
            "",
        ]

        test_examples: dict[str, list[CodeExample]] = {}
        docstring_examples: dict[str, list[CodeExample]] = {}
        for entity_name, examples in examples_by_entity.items():
            for ex in examples:
                if ex.source == "test":
                    test_examples.setdefault(entity_name, []).append(ex)
                else:
                    docstring_examples.setdefault(entity_name, []).append(ex)

        if test_examples:
            ExamplesWikiGenerator._add_test_examples_section(lines, test_examples)
        if docstring_examples:
            ExamplesWikiGenerator._add_docstring_examples_section(
                lines, docstring_examples
            )

        return "\n".join(lines)


def get_examples_for_api_page(
    entity_name: str,
    extractor: CodeExampleExtractor,
    docstring: str | None = None,
) -> str:
    """Get formatted examples section for an API documentation page.

    This is a helper function for integrating examples into existing
    API documentation pages.

    Args:
        entity_name: Name of the function/class.
        extractor: CodeExampleExtractor instance.
        docstring: Optional docstring to extract examples from.

    Returns:
        Markdown string with examples section, or empty string.
    """
    import asyncio

    examples: list[CodeExample] = []

    # Get examples from extractor (runs async)
    try:
        asyncio.get_running_loop()
        logger.debug("Event loop already running, skipping async example extraction")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            extracted = loop.run_until_complete(
                extractor.extract_examples_for_function(entity_name, max_examples=3)
            )
            examples.extend(extracted)
        except (RuntimeError, OSError, ValueError, TypeError) as e:
            logger.debug("Failed to extract examples for %s: %s", entity_name, e)
        finally:
            loop.close()

    # Add docstring examples
    if docstring:
        doc_examples = parse_docstring_examples(docstring)
        examples.extend(
            dataclasses.replace(ex, entity_name=entity_name) for ex in doc_examples
        )

    if not examples:
        return ""

    return format_code_examples_markdown(examples, max_examples=3)
