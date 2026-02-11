"""Wiki generator plugin for code examples.

This plugin generates an Examples page that aggregates usage examples
from test files and docstrings across the codebase.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from local_deepwiki.generators.test_examples import (
    CodeExample,
    CodeExampleExtractor,
    format_code_examples_markdown,
    parse_docstring_examples,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, IndexStatus, WikiPage
from local_deepwiki.plugins.base import PluginMetadata, WikiGeneratorPlugin, WikiGeneratorResult

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

        # Create the extractor
        extractor = CodeExampleExtractor(vector_store, repo_path)

        # Collect examples from all documented entities
        all_examples: dict[str, list[CodeExample]] = {}

        # Get all function and class chunks
        try:
            # Search for functions and classes
            function_results = await vector_store.search(
                query="function definition",
                limit=100,
                chunk_type="function",
            )
            class_results = await vector_store.search(
                query="class definition",
                limit=50,
                chunk_type="class",
            )

            # Extract examples for functions
            for result in function_results:
                chunk = result.chunk
                if not chunk.name or len(chunk.name) <= 2:
                    continue

                # Skip test functions and private functions
                if chunk.name.startswith(("test_", "_")):
                    continue

                # Get examples for this function
                examples = await extractor.extract_examples_for_function(
                    chunk.name, max_examples=2
                )

                # Also extract from docstring directly
                if chunk.docstring:
                    doc_examples = parse_docstring_examples(chunk.docstring)
                    for ex in doc_examples:
                        ex.entity_name = chunk.name
                    examples.extend(doc_examples)

                if examples:
                    all_examples[chunk.name] = examples[:3]  # Limit per entity

            # Extract examples for classes
            for result in class_results:
                chunk = result.chunk
                if not chunk.name or len(chunk.name) <= 2:
                    continue

                # Skip private classes
                if chunk.name.startswith("_"):
                    continue

                examples = await extractor.extract_examples_for_class(
                    chunk.name, max_examples=2
                )

                if chunk.docstring:
                    doc_examples = parse_docstring_examples(chunk.docstring)
                    for ex in doc_examples:
                        ex.entity_name = chunk.name
                    examples.extend(doc_examples)

                if examples:
                    all_examples[chunk.name] = examples[:3]

        except Exception as e:
            logger.debug("Error extracting examples: %s", e)
            return WikiGeneratorResult(pages=[])

        if not all_examples:
            logger.debug("No examples found in codebase")
            return WikiGeneratorResult(pages=[])

        # Generate the examples page
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

    def _generate_examples_page(
        self,
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

        # Group by source (test vs docstring)
        test_examples: dict[str, list[CodeExample]] = {}
        docstring_examples: dict[str, list[CodeExample]] = {}

        for entity_name, examples in examples_by_entity.items():
            for ex in examples:
                if ex.source == "test":
                    test_examples.setdefault(entity_name, []).append(ex)
                else:
                    docstring_examples.setdefault(entity_name, []).append(ex)

        # Section for test examples
        if test_examples:
            lines.extend(
                [
                    "## Examples from Tests",
                    "",
                    "Real-world usage patterns extracted from test files.",
                    "",
                ]
            )

            for entity_name in sorted(test_examples.keys()):
                examples = test_examples[entity_name]
                lines.append(f"### `{entity_name}`\n")

                for ex in examples[:2]:
                    if ex.description:
                        lines.append(f"*{ex.description}*\n")
                    if ex.test_file:
                        lines.append(f"From `{ex.test_file}`:\n")

                    lang = ex.language or "python"
                    lines.append(f"```{lang}\n{ex.code}\n```\n")

        # Section for docstring examples
        if docstring_examples:
            lines.extend(
                [
                    "## Examples from Documentation",
                    "",
                    "Examples extracted from docstrings.",
                    "",
                ]
            )

            for entity_name in sorted(docstring_examples.keys()):
                examples = docstring_examples[entity_name]
                lines.append(f"### `{entity_name}`\n")

                for ex in examples[:2]:
                    if ex.description:
                        lines.append(f"*{ex.description}*\n")

                    lang = ex.language or "python"
                    lines.append(f"```{lang}\n{ex.code}\n```\n")

                    if ex.expected_output:
                        lines.append(f"Output:\n```\n{ex.expected_output}\n```\n")

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
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't use run_until_complete in running loop
            # Return docstring examples only
            logger.debug(
                "Event loop already running, skipping async example extraction"
            )
        else:
            extracted = loop.run_until_complete(
                extractor.extract_examples_for_function(entity_name, max_examples=3)
            )
            examples.extend(extracted)
    except (RuntimeError, OSError, ValueError, TypeError) as e:
        logger.debug("Failed to extract examples for %s: %s", entity_name, e)

    # Add docstring examples
    if docstring:
        doc_examples = parse_docstring_examples(docstring)
        for ex in doc_examples:
            ex.entity_name = entity_name
        examples.extend(doc_examples)

    if not examples:
        return ""

    return format_code_examples_markdown(examples, max_examples=3)
