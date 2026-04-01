"""Extract usage examples from test files and docstrings for documentation.

This module scans test files and docstrings to find real-world usage examples of
documented functions and classes, then formats them for inclusion
in wiki documentation.

Extraction is split across three modules:
- ``docstring_examples``: Docstring parsing (doctest + Google-style)
- ``example_extractor``: Vector-search-based extraction and markdown formatting
- ``test_examples`` (this file): Test-file extraction and orchestration
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.examples.discovery import (
    _find_test_functions,
    _get_docstring,
    _get_function_body,
    _get_function_name,
    _is_mock_heavy,
    find_test_files,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import Language

if TYPE_CHECKING:
    from tree_sitter import Node

__all__ = [
    "UsageExample",
    "_extract_usage_snippet",
    "extract_examples_for_entities",
    "format_examples_markdown",
    "get_file_examples",
]

logger = get_logger(__name__)


@dataclass(slots=True)
class UsageExample:
    """A usage example extracted from a test file."""

    entity_name: str  # Name of the function/class being demonstrated
    test_name: str  # Name of the test function
    test_file: str  # Path to the test file
    code: str  # Extracted code snippet
    description: str | None  # From test docstring


def _skip_docstring_lines(lines: list[str]) -> int:
    """Return the index of the first non-docstring line in *lines*.

    Scans from the top and skips over any leading docstring block.

    Args:
        lines: Lines of a function body.

    Returns:
        Index of the first code line after any docstring.
    """
    in_docstring = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('"""', "'''")):
            if in_docstring:
                in_docstring = False
                continue
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                continue
            in_docstring = True
            continue
        if in_docstring:
            continue
        return i
    return 0


def _should_start_capture(
    line: str, entity_name: str, capturing: bool
) -> tuple[bool, bool]:
    """Return (new_capturing, dedent_block) after checking if capture should start."""
    dedent_block = False
    if "dedent(" in line or 'dedent("""' in line:
        dedent_block = True
        capturing = True
    if entity_name in line and not capturing:
        capturing = True
    return capturing, dedent_block


def _collect_relevant_lines(
    lines: list[str],
    entity_name: str,
    max_lines: int,
) -> list[str]:
    """Collect lines from *lines* that demonstrate usage of *entity_name*.

    Starts capturing at the first occurrence of the entity name (or at a
    ``dedent(`` block) and stops after two assertions or *max_lines* lines.

    Args:
        lines: Code lines with docstring already skipped.
        entity_name: Name of the entity to capture usage of.
        max_lines: Maximum number of lines to include.

    Returns:
        Relevant lines or empty list if none found.
    """
    relevant_lines: list[str] = []
    capturing = False
    dedent_block = False
    paren_depth = 0
    assertions_found = 0

    for line in lines:
        stripped = line.strip()
        paren_depth += line.count("(") - line.count(")")

        capturing, new_dedent = _should_start_capture(line, entity_name, capturing)
        dedent_block = dedent_block or new_dedent

        if capturing:
            relevant_lines.append(line)

            if stripped.startswith("assert") and paren_depth <= 0:
                assertions_found += 1
                if assertions_found >= 2:
                    break

            if len(relevant_lines) >= max_lines:
                break

        if dedent_block and '"""' in line and len(relevant_lines) > 1:
            dedent_block = False

    return relevant_lines


def _extract_usage_snippet(
    func_node: Node,
    source: bytes,
    entity_name: str,
    max_lines: int = 25,
) -> str | None:
    """Extract a clean usage snippet from a test function.

    Looks for code that demonstrates usage of the entity,
    including setup, the call, and assertions.

    Args:
        func_node: The function AST node.
        source: Source code bytes.
        entity_name: Name of the entity to find usage of.
        max_lines: Maximum lines to include.

    Returns:
        Extracted code snippet or None if not suitable.
    """
    body = _get_function_body(func_node, source)
    lines = body.split("\n")

    start_idx = _skip_docstring_lines(lines)
    lines = lines[start_idx:]

    relevant_lines = _collect_relevant_lines(lines, entity_name, max_lines)

    if not relevant_lines:
        return None

    # For short tests, include the full body (more useful)
    if len(relevant_lines) < 5 and len(lines) <= max_lines:
        result = "\n".join(lines)
    else:
        result = "\n".join(relevant_lines)

    # Clean up indentation
    try:
        result = dedent(result)
    except TypeError:
        logger.debug("Failed to dedent extracted usage snippet", exc_info=True)

    return result.strip()


def extract_examples_for_entities(
    test_file: Path,
    entity_names: list[str],
    max_examples_per_entity: int = 2,
) -> list[UsageExample]:
    """Extract usage examples from a test file for given entities.

    Args:
        test_file: Path to the test file.
        entity_names: Names of functions/classes to find examples for.
        max_examples_per_entity: Maximum examples per entity.

    Returns:
        List of UsageExample objects.
    """
    parser = CodeParser()

    try:
        source = test_file.read_bytes()
    except OSError as e:
        logger.debug("Failed to read test file %s: %s", test_file, e)
        return []

    root = parser.parse_source(source, Language.PYTHON)

    test_functions = _find_test_functions(root)
    examples: list[UsageExample] = []
    entity_counts: dict[str, int] = {}

    for func_node, class_name in test_functions:
        body = _get_function_body(func_node, source)

        # Skip mock-heavy tests
        if _is_mock_heavy(body):
            continue

        for entity_name in entity_names:
            # Check if we've hit the limit for this entity
            if entity_counts.get(entity_name, 0) >= max_examples_per_entity:
                continue

            # Check if entity is used in this test
            if entity_name not in body:
                continue

            # Extract the usage snippet
            snippet = _extract_usage_snippet(func_node, source, entity_name)
            if not snippet or len(snippet) < 10:
                continue

            test_name = _get_function_name(func_node, source)
            docstring = _get_docstring(func_node, source)

            # Format test name with class if from a test class
            full_test_name = f"{class_name}::{test_name}" if class_name else test_name

            examples.append(
                UsageExample(
                    entity_name=entity_name,
                    test_name=full_test_name,
                    test_file=str(test_file.name),
                    code=snippet,
                    description=docstring,
                )
            )

            entity_counts[entity_name] = entity_counts.get(entity_name, 0) + 1

    return examples


def format_examples_markdown(
    examples: list[UsageExample],
    max_examples: int = 5,
) -> str:
    """Format usage examples as markdown.

    Args:
        examples: List of UsageExample objects.
        max_examples: Maximum examples to include.

    Returns:
        Formatted markdown string.
    """
    if not examples:
        return ""

    # Limit total examples
    examples = examples[:max_examples]

    sections = ["## Usage Examples\n"]
    sections.append("*Examples extracted from test files*\n")

    for example in examples:
        # Use docstring as title if available, otherwise use entity name
        if example.description:
            # Clean up docstring for use as title
            title = example.description.split("\n")[0].strip(".")
            sections.append(f"### {title}\n")
        else:
            sections.append(f"### Example: `{example.entity_name}`\n")

        sections.append(f"From `{example.test_file}::{example.test_name}`:\n")
        sections.append(f"```python\n{example.code}\n```\n")

    return "\n".join(sections)


def get_file_examples(
    source_file: Path,
    repo_root: Path,
    entity_names: list[str],
    max_examples: int = 5,
) -> str | None:
    """Get formatted usage examples for a source file.

    This is the main entry point for the wiki generator.
    Searches all matching test files for usage examples.

    Args:
        source_file: Path to the source file being documented.
        repo_root: Root directory of the repository.
        entity_names: Names of functions/classes in the source file.
        max_examples: Maximum examples to include.

    Returns:
        Formatted markdown string with examples, or None if no examples found.
    """
    # Only support Python for now
    if not source_file.suffix == ".py":
        return None

    # Find all corresponding test files
    test_files = find_test_files(source_file, repo_root)
    if not test_files:
        logger.debug("No test files found for %s", source_file)
        return None

    # Filter to meaningful entity names (skip short ones)
    entity_names = [name for name in entity_names if name and len(name) > 2]
    if not entity_names:
        return None

    # Extract examples from all test files
    all_examples: list[UsageExample] = []
    for test_file in test_files:
        examples = extract_examples_for_entities(
            test_file=test_file,
            entity_names=entity_names,
            max_examples_per_entity=2,
        )
        all_examples.extend(examples)

    if not all_examples:
        logger.debug("No examples found in %s test file(s)", len(test_files))
        return None

    # Deduplicate by entity_name + code (same example from different sources)
    seen: set[tuple[str, str]] = set()
    unique_examples: list[UsageExample] = []
    for ex in all_examples:
        key = (ex.entity_name, ex.code)
        if key not in seen:
            seen.add(key)
            unique_examples.append(ex)

    test_names = [tf.name for tf in test_files]
    logger.info(
        "Found %d usage examples from %s", len(unique_examples), ", ".join(test_names)
    )

    return format_examples_markdown(unique_examples, max_examples=max_examples)
