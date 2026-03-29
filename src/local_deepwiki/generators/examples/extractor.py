"""Extract code examples from source code using vector search.

This module provides the CodeExampleExtractor class which uses semantic
search to find test cases and docstring examples for functions and classes
in a codebase, plus a markdown formatter for CodeExample objects.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

from local_deepwiki.generators.examples.docstring import (
    CodeExample,
    parse_docstring_examples,
)
from local_deepwiki.generators.examples.discovery import _is_mock_heavy

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore


class CodeExampleExtractor:
    """Extract usage examples from tests and docstrings using vector search.

    This class provides semantic search capabilities to find relevant test cases
    and docstring examples for functions and classes in a codebase.

    Example:
        >>> extractor = CodeExampleExtractor(vector_store)
        >>> examples = await extractor.extract_examples_for_function("process_data")
        >>> for ex in examples:
        ...     print(f"From {ex.source}: {ex.code[:50]}...")
    """

    def __init__(self, vector_store: "VectorStore", repo_path: Path | None = None):
        """Initialize the extractor.

        Args:
            vector_store: VectorStore instance for semantic search.
            repo_path: Optional repository root path for test file discovery.
        """
        self._store = vector_store
        self._repo_path = repo_path

    async def extract_examples_for_function(
        self,
        func_name: str,
        max_examples: int = 3,
    ) -> list[CodeExample]:
        """Find test cases and docstring examples for a function.

        Searches the vector store for:
        1. Test functions that call or reference the target function
        2. Docstrings containing examples for the function

        Args:
            func_name: Name of the function to find examples for.
            max_examples: Maximum number of examples to return.

        Returns:
            List of CodeExample objects.
        """
        if len(func_name) <= 2:
            return []

        examples: list[CodeExample] = []

        # Search for tests that use this function
        test_examples = await self._search_test_examples(func_name, max_examples)
        examples.extend(test_examples)

        # Search for docstring examples
        docstring_examples = await self._search_docstring_examples(
            func_name, max_examples
        )
        examples.extend(docstring_examples)

        # Deduplicate and limit
        seen_codes: set[str] = set()
        unique: list[CodeExample] = []
        for ex in examples:
            code_key = ex.code.strip()[:100]  # Compare first 100 chars
            if code_key not in seen_codes:
                seen_codes.add(code_key)
                unique.append(ex)
                if len(unique) >= max_examples:
                    break

        return unique

    async def extract_examples_for_class(
        self,
        class_name: str,
        max_examples: int = 3,
    ) -> list[CodeExample]:
        """Find test cases and docstring examples for a class.

        Searches for tests that instantiate or use the class, as well as
        docstring examples in the class definition.

        Args:
            class_name: Name of the class to find examples for.
            max_examples: Maximum number of examples to return.

        Returns:
            List of CodeExample objects.
        """
        if len(class_name) <= 2:
            return []

        examples: list[CodeExample] = []

        # Search for tests that use this class
        test_examples = await self._search_test_examples(class_name, max_examples)
        examples.extend(test_examples)

        # Search for class docstring examples
        docstring_examples = await self._search_docstring_examples(
            class_name, max_examples
        )
        examples.extend(docstring_examples)

        # Deduplicate and limit
        seen_codes: set[str] = set()
        unique: list[CodeExample] = []
        for ex in examples:
            code_key = ex.code.strip()[:100]
            if code_key not in seen_codes:
                seen_codes.add(code_key)
                unique.append(ex)
                if len(unique) >= max_examples:
                    break

        return unique

    async def _search_test_examples(
        self,
        entity_name: str,
        max_results: int = 5,
    ) -> list[CodeExample]:
        """Search for test functions that use the given entity.

        Args:
            entity_name: Name of the function/class to search for.
            max_results: Maximum search results.

        Returns:
            List of CodeExample objects from test files.
        """
        examples: list[CodeExample] = []

        # Search for test functions mentioning this entity
        query = f"test {entity_name}"
        results = await self._store.search(
            query=query,
            limit=max_results * 2,  # Get extra to filter
            chunk_type="function",
        )

        for result in results:
            chunk = result.chunk

            # Only consider test functions
            if not chunk.name or not chunk.name.startswith("test"):
                continue

            # Check if entity is actually used in the code
            if entity_name not in chunk.content:
                continue

            # Skip mock-heavy tests
            if _is_mock_heavy(chunk.content):
                continue

            # Extract relevant snippet
            snippet = self._extract_relevant_snippet(chunk.content, entity_name)
            if snippet and len(snippet) >= 10:
                examples.append(
                    CodeExample(
                        source="test",
                        code=snippet,
                        description=chunk.docstring,
                        test_file=chunk.file_path,
                        language=chunk.language.value if chunk.language else "python",
                        entity_name=entity_name,
                    )
                )

            if len(examples) >= max_results:
                break

        return examples

    async def _search_docstring_examples(
        self,
        entity_name: str,
        max_results: int = 3,
    ) -> list[CodeExample]:
        """Search for docstring examples for the given entity.

        Args:
            entity_name: Name of the function/class to search for.
            max_results: Maximum results.

        Returns:
            List of CodeExample objects from docstrings.
        """
        examples: list[CodeExample] = []

        # Search for the entity's definition
        results = await self._store.search(
            query=entity_name,
            limit=5,
        )

        for result in results:
            chunk = result.chunk

            # Look for the exact entity
            if chunk.name != entity_name:
                continue

            # Parse docstring examples
            if chunk.docstring:
                docstring_examples = parse_docstring_examples(chunk.docstring)
                for doc_ex in docstring_examples[:max_results]:
                    examples.append(
                        dataclasses.replace(doc_ex, entity_name=entity_name)
                    )

            if len(examples) >= max_results:
                break

        return examples

    def _collect_snippet_lines(
        self,
        lines: list[str],
        entity_name: str,
        max_lines: int,
    ) -> list[str]:
        """Collect the lines that demonstrate entity usage from *lines*."""
        relevant: list[str] = []
        capturing = False
        paren_depth = 0
        assertions_found = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('"""', "'''")):
                continue
            paren_depth += line.count("(") - line.count(")")
            if entity_name in line and not capturing:
                capturing = True
            if capturing:
                relevant.append(line)
                if stripped.startswith("assert") and paren_depth <= 0:
                    assertions_found += 1
                    if assertions_found >= 2:
                        break
                if len(relevant) >= max_lines:
                    break

        return relevant

    def _extract_relevant_snippet(
        self,
        content: str,
        entity_name: str,
        max_lines: int = 20,
    ) -> str | None:
        """Extract the most relevant code snippet from test content.

        Args:
            content: Full test function content.
            entity_name: Entity to find usage of.
            max_lines: Maximum lines to include.

        Returns:
            Extracted snippet or None.
        """
        lines = content.split("\n")
        relevant = self._collect_snippet_lines(lines, entity_name, max_lines)

        if not relevant:
            return None

        try:
            result = dedent("\n".join(relevant)).strip()
        except (TypeError, ValueError):
            result = "\n".join(relevant).strip()

        return result if len(result) >= 10 else None


def format_code_examples_markdown(
    examples: list[CodeExample],
    max_examples: int = 5,
) -> str:
    """Format CodeExample objects as markdown.

    Args:
        examples: List of CodeExample objects.
        max_examples: Maximum examples to include.

    Returns:
        Formatted markdown string.
    """
    if not examples:
        return ""

    examples = examples[:max_examples]

    sections = ["## Examples\n"]

    for i, example in enumerate(examples, 1):
        # Create section header
        if example.description:
            sections.append(f"### {example.description}\n")
        elif example.entity_name:
            sections.append(f"### Example {i}: `{example.entity_name}`\n")
        else:
            sections.append(f"### Example {i}\n")

        # Add source info
        if example.source == "test" and example.test_file:
            sections.append(f"*From test file: `{example.test_file}`*\n")
        elif example.source == "docstring":
            sections.append("*From docstring*\n")

        # Add code block
        lang = example.language or "python"
        sections.append(f"```{lang}\n{example.code}\n```\n")

        # Add expected output if available
        if example.expected_output:
            sections.append(f"Output:\n```\n{example.expected_output}\n```\n")

    return "\n".join(sections)
