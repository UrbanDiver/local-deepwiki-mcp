"""Extract usage examples from test files and docstrings for documentation.

This module scans test files and docstrings to find real-world usage examples of
documented functions and classes, then formats them for inclusion
in wiki documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

from tree_sitter import Node

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, Language

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore

logger = get_logger(__name__)


@dataclass
class CodeExample:
    """A code example extracted from tests or docstrings.

    This is the unified data class for examples from any source.
    """

    source: str  # "test" or "docstring"
    code: str  # The actual code snippet
    description: str | None = None  # Description or context
    test_file: str | None = None  # Path to test file (for test examples)
    language: str = "python"  # Programming language
    expected_output: str | None = None  # Expected output (for doctest examples)
    entity_name: str | None = None  # Name of the function/class being demonstrated


@dataclass
class UsageExample:
    """A usage example extracted from a test file."""

    entity_name: str  # Name of the function/class being demonstrated
    test_name: str  # Name of the test function
    test_file: str  # Path to the test file
    code: str  # Extracted code snippet
    description: str | None  # From test docstring


def find_test_files(source_file: Path, repo_root: Path) -> list[Path]:
    """Find all corresponding test files for a source file.

    Tries multiple strategies:
    1. Direct match: src/.../foo.py -> tests/test_foo.py
    2. Coverage tests: src/.../foo.py -> tests/test_foo_coverage.py
    3. Suffix variants: tests/test_foo_*.py
    4. Alternative naming: tests/foo_test.py

    Args:
        source_file: Path to the source file.
        repo_root: Root directory of the repository.

    Returns:
        List of test file paths found (may be empty).
    """
    # Get base filename without extension
    base_name = source_file.stem  # e.g., "api_docs"

    # Skip test files themselves
    if base_name.startswith("test_"):
        return []

    test_files: list[Path] = []

    # Common test directories to check
    test_dirs = [
        repo_root / "tests",
        repo_root / "test",
    ]

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue

        # Try direct match: test_<basename>.py
        test_file = test_dir / f"test_{base_name}.py"
        if test_file.exists():
            test_files.append(test_file)

        # Try coverage variant: test_<basename>_coverage.py
        coverage_file = test_dir / f"test_{base_name}_coverage.py"
        if coverage_file.exists():
            test_files.append(coverage_file)

        # Try glob for other variants: test_<basename>_*.py
        for variant in test_dir.glob(f"test_{base_name}_*.py"):
            if variant not in test_files:
                test_files.append(variant)

        # Try alternative naming: <basename>_test.py
        alt_file = test_dir / f"{base_name}_test.py"
        if alt_file.exists() and alt_file not in test_files:
            test_files.append(alt_file)

    if test_files:
        logger.debug("Found %s test file(s) for %s", len(test_files), source_file.name)

    return test_files


def find_test_file(source_file: Path, repo_root: Path) -> Path | None:
    """Find the corresponding test file for a source file.

    Legacy function for backwards compatibility.
    Returns the first test file found, or None.

    Args:
        source_file: Path to the source file.
        repo_root: Root directory of the repository.

    Returns:
        Path to the test file if found, None otherwise.
    """
    test_files = find_test_files(source_file, repo_root)
    return test_files[0] if test_files else None


def _get_node_text(node: Node, source: bytes) -> str:
    """Get the text content of a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _find_test_functions(root: Node) -> list[tuple[Node, str | None]]:
    """Find all test function definitions in the AST.

    Finds both standalone test functions and test methods in test classes.

    Args:
        root: Root node of the parsed test file.

    Returns:
        List of (function_definition_node, class_name) tuples.
        class_name is None for standalone functions.
    """
    test_functions: list[tuple[Node, str | None]] = []

    def walk(node: Node, current_class: str | None = None) -> None:
        if node.type == "class_definition":
            # Get class name
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = name_node.text.decode("utf-8") if name_node.text else ""
                # Check if it's a test class
                if class_name.startswith("Test"):
                    # Walk children with this class context
                    for child in node.children:
                        walk(child, class_name)
                    return

        if node.type == "function_definition":
            # Get the function name
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8") if name_node.text else ""
                if name.startswith("test_"):
                    test_functions.append((node, current_class))

        for child in node.children:
            walk(child, current_class)

    walk(root)
    return test_functions


def _get_function_name(func_node: Node, source: bytes) -> str:
    """Get the name of a function from its AST node."""
    name_node = func_node.child_by_field_name("name")
    if name_node:
        return _get_node_text(name_node, source)
    return "unknown"


def _get_docstring(func_node: Node, source: bytes) -> str | None:
    """Extract docstring from a function node if present."""
    body = func_node.child_by_field_name("body")
    if not body or not body.children:
        return None

    # First statement in body might be a docstring
    first_stmt = body.children[0]
    if first_stmt.type == "expression_statement":
        expr = first_stmt.children[0] if first_stmt.children else None
        if expr and expr.type == "string":
            docstring = _get_node_text(expr, source)
            # Clean up the docstring
            docstring = docstring.strip("\"'")
            if docstring.startswith('""'):
                docstring = (
                    docstring[2:-2] if docstring.endswith('""') else docstring[2:]
                )
            return docstring.strip()

    return None


def _get_function_body(func_node: Node, source: bytes) -> str:
    """Get the body of a function as a string."""
    body = func_node.child_by_field_name("body")
    if body:
        return _get_node_text(body, source)
    return ""


def _is_mock_heavy(body: str) -> bool:
    """Check if a test body uses mocking extensively.

    We want to exclude heavily mocked tests as they don't show
    real usage patterns.
    """
    mock_indicators = [
        "MagicMock",
        "AsyncMock",
        "@patch",
        "patch(",
        "mock_",
        "mocker.",
    ]
    mock_count = sum(1 for indicator in mock_indicators if indicator in body)
    return mock_count >= 2


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

    # Skip the docstring if present
    start_idx = 0
    in_docstring = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Detect docstring boundaries
        if stripped.startswith(('"""', "'''")):
            if in_docstring:
                in_docstring = False
                continue
            # Check for single-line docstring
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                continue
            in_docstring = True
            continue
        if in_docstring:
            continue
        start_idx = i
        break

    lines = lines[start_idx:]

    # Find lines relevant to the entity
    relevant_lines: list[str] = []
    capturing = False
    dedent_block = False
    paren_depth = 0
    assertions_found = 0

    for line in lines:
        stripped = line.strip()

        # Track parentheses for multi-line calls
        paren_depth += line.count("(") - line.count(")")

        # Start capturing when we see dedent (common test pattern) or the entity
        if "dedent(" in line or 'dedent("""' in line:
            dedent_block = True
            capturing = True

        if entity_name in line and not capturing:
            capturing = True

        if capturing:
            relevant_lines.append(line)

            # Track assertions to capture a complete test
            if stripped.startswith("assert") and paren_depth <= 0:
                assertions_found += 1
                # Allow up to 2 assertions for better context
                if assertions_found >= 2:
                    break

            if len(relevant_lines) >= max_lines:
                break

        # End dedent block
        if dedent_block and '"""' in line and len(relevant_lines) > 1:
            dedent_block = False

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
        pass

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
    except (OSError, IOError) as e:
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


# =============================================================================
# Docstring Parsing Functions
# =============================================================================


def parse_doctest_examples(docstring: str) -> list[CodeExample]:
    """Extract >>> doctest examples from a docstring.

    Parses Python doctest-style examples with >>> prompts and expected output.

    Args:
        docstring: The docstring to parse.

    Returns:
        List of CodeExample objects extracted from doctests.

    Example:
        >>> parse_doctest_examples('''
        ... >>> add(1, 2)
        ... 3
        ... >>> add(-1, 1)
        ... 0
        ... ''')
        [CodeExample(source='docstring', code='add(1, 2)', expected_output='3', ...)]
    """
    if not docstring:
        return []

    examples: list[CodeExample] = []
    lines = docstring.split("\n")

    current_code_lines: list[str] = []
    current_output_lines: list[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()

        # Check for >>> prompt (start of code)
        if stripped.startswith(">>>"):
            # If we have accumulated code from before, save it
            if current_code_lines:
                code = "\n".join(current_code_lines)
                output = (
                    "\n".join(current_output_lines) if current_output_lines else None
                )
                examples.append(
                    CodeExample(
                        source="docstring",
                        code=code,
                        expected_output=output,
                        language="python",
                    )
                )
                current_code_lines = []
                current_output_lines = []

            # Start new code block
            code_part = stripped[3:].strip()  # Remove >>>
            if code_part:
                current_code_lines.append(code_part)
            in_code = True

        # Check for ... continuation
        elif stripped.startswith("...") and in_code:
            cont_part = stripped[3:].strip()  # Remove ...
            current_code_lines.append(cont_part)

        # Expected output (non-empty line after code, not starting with >>> or ...)
        elif in_code and stripped and not stripped.startswith((">>>", "...")):
            current_output_lines.append(stripped)

        # Empty line may end the example
        elif in_code and not stripped and current_code_lines:
            # Save the accumulated example
            code = "\n".join(current_code_lines)
            output = "\n".join(current_output_lines) if current_output_lines else None
            examples.append(
                CodeExample(
                    source="docstring",
                    code=code,
                    expected_output=output,
                    language="python",
                )
            )
            current_code_lines = []
            current_output_lines = []
            in_code = False

    # Don't forget the last example
    if current_code_lines:
        code = "\n".join(current_code_lines)
        output = "\n".join(current_output_lines) if current_output_lines else None
        examples.append(
            CodeExample(
                source="docstring",
                code=code,
                expected_output=output,
                language="python",
            )
        )

    return examples


def parse_google_style_examples(docstring: str) -> list[CodeExample]:
    """Extract examples from Google-style docstring Examples section.

    Parses the Examples: section of a Google-style docstring, extracting
    code blocks and their descriptions.

    Args:
        docstring: The docstring to parse.

    Returns:
        List of CodeExample objects from the Examples section.

    Example:
        >>> doc = '''
        ... Examples:
        ...     Basic usage:
        ...         result = process("input")
        ...         print(result)
        ...
        ...     With options:
        ...         result = process("input", verbose=True)
        ... '''
        >>> examples = parse_google_style_examples(doc)
        >>> len(examples)
        2
    """
    if not docstring:
        return []

    examples: list[CodeExample] = []

    # Find the Examples: section
    # Match "Examples:", "Example:", with optional leading whitespace
    example_pattern = re.compile(
        r"^\s*(Examples?)\s*:\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    match = example_pattern.search(docstring)
    if not match:
        return []

    # Extract from Examples: to end or next section
    start_idx = match.end()

    # Find the next section (Args:, Returns:, Raises:, etc.)
    section_pattern = re.compile(
        r"^\s*(Args?|Returns?|Raises?|Yields?|Attributes?|Note|Notes|Warning|Warnings|See Also|References?)\s*:",
        re.MULTILINE | re.IGNORECASE,
    )

    end_match = section_pattern.search(docstring, start_idx)
    if end_match:
        examples_text = docstring[start_idx : end_match.start()]
    else:
        examples_text = docstring[start_idx:]

    # Parse the examples section
    lines = examples_text.split("\n")
    current_description: str | None = None
    current_code_lines: list[str] = []
    base_indent: int | None = None

    def save_current_example() -> None:
        """Save the current accumulated example."""
        nonlocal current_description, current_code_lines
        if current_code_lines:
            code = dedent("\n".join(current_code_lines)).strip()
            if code:
                examples.append(
                    CodeExample(
                        source="docstring",
                        code=code,
                        description=current_description,
                        language="python",
                    )
                )
        current_description = None
        current_code_lines = []

    for line in lines:
        # Skip empty lines at the start
        if not line.strip() and not current_code_lines:
            continue

        # Calculate indentation
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Detect base indent level
        if base_indent is None and stripped:
            base_indent = indent

        if not stripped:
            # Empty line might separate examples
            if current_code_lines:
                current_code_lines.append("")
            continue

        # Line at base indent level might be a description
        if base_indent is not None and indent == base_indent:
            # Check if it looks like a description (ends with :)
            if stripped.endswith(":") and not stripped.startswith((">>>", "...")):
                # Save previous example if any
                save_current_example()
                current_description = stripped.rstrip(":")
                continue

        # Code line (more indented than base)
        if base_indent is not None and indent > base_indent:
            current_code_lines.append(line)
        elif stripped:
            # At base level, could be code if we're already collecting
            if current_code_lines:
                current_code_lines.append(line)
            else:
                # Could be description or start of code
                current_code_lines.append(line)

    # Save the last example
    save_current_example()

    return examples


def parse_docstring_examples(docstring: str) -> list[CodeExample]:
    """Extract all examples from a docstring (doctests and Google-style).

    Combines doctest-style (>>>) examples and Google-style Examples section
    into a unified list.

    Args:
        docstring: The docstring to parse.

    Returns:
        List of CodeExample objects from all sources.
    """
    if not docstring:
        return []

    examples: list[CodeExample] = []

    # Extract doctest examples
    doctest_examples = parse_doctest_examples(docstring)
    examples.extend(doctest_examples)

    # Extract Google-style examples (only if no doctests found, to avoid duplication)
    if not doctest_examples:
        google_examples = parse_google_style_examples(docstring)
        examples.extend(google_examples)

    return examples


# =============================================================================
# CodeExampleExtractor Class
# =============================================================================


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
                    doc_ex.entity_name = entity_name
                    examples.append(doc_ex)

            if len(examples) >= max_results:
                break

        return examples

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
        relevant: list[str] = []
        capturing = False
        paren_depth = 0
        assertions_found = 0

        for line in lines:
            stripped = line.strip()

            # Skip docstrings
            if stripped.startswith(('"""', "'''")):
                continue

            # Track parentheses
            paren_depth += line.count("(") - line.count(")")

            # Start capturing at entity usage
            if entity_name in line and not capturing:
                capturing = True

            if capturing:
                relevant.append(line)

                # Stop after assertions
                if stripped.startswith("assert") and paren_depth <= 0:
                    assertions_found += 1
                    if assertions_found >= 2:
                        break

                if len(relevant) >= max_lines:
                    break

        if not relevant:
            return None

        try:
            result = dedent("\n".join(relevant)).strip()
        except (TypeError, ValueError):
            # TypeError: dedent received non-string input
            # ValueError: unexpected indentation issues
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
