"""Parse code examples from docstrings.

This module extracts code examples from docstrings in two styles:
1. Python doctest-style (>>> prompts)
2. Google-style Examples sections

These parsers are used by the example extraction pipeline to find
usage examples embedded in documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from textwrap import dedent


@dataclass(frozen=True, slots=True)
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


def _extract_examples_section(docstring: str) -> str | None:
    """Extract the raw text of the Examples section from a Google-style docstring.

    Args:
        docstring: Full docstring text.

    Returns:
        Text of the Examples section, or None if no section found.
    """
    example_pattern = re.compile(
        r"^\s*(Examples?)\s*:\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = example_pattern.search(docstring)
    if not match:
        return None

    start_idx = match.end()

    section_pattern = re.compile(
        r"^\s*(Args?|Returns?|Raises?|Yields?|Attributes?|Note|Notes|Warning|Warnings|See Also|References?)\s*:",
        re.MULTILINE | re.IGNORECASE,
    )
    end_match = section_pattern.search(docstring, start_idx)
    if end_match:
        return docstring[start_idx : end_match.start()]
    return docstring[start_idx:]


def _flush_example(
    code_lines: list[str],
    description: str | None,
) -> CodeExample | None:
    """Build a CodeExample from accumulated lines, or None if nothing to flush."""
    if not code_lines:
        return None
    code = dedent("\n".join(code_lines)).strip()
    if not code:
        return None
    return CodeExample(
        source="docstring",
        code=code,
        description=description,
        language="python",
    )


def _is_description_marker(stripped: str, indent: int, base_indent: int) -> bool:
    """Return True when a line is a description header like 'Basic usage:'."""
    return (
        indent == base_indent
        and stripped.endswith(":")
        and not stripped.startswith((">>>", "..."))
    )


def _parse_example_block(
    lines: list[str],
) -> list[CodeExample]:
    """Parse an Examples section into a list of CodeExample objects.

    Handles descriptions (lines ending with ``:``) followed by indented
    code blocks.

    Args:
        lines: Lines of the Examples section text.

    Returns:
        List of CodeExample objects.
    """
    examples: list[CodeExample] = []
    current_description: str | None = None
    current_code_lines: list[str] = []
    base_indent: int | None = None

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Skip leading empty lines before any code has started
        if not stripped and not current_code_lines:
            continue

        # Record the indentation level of the first non-empty line
        if base_indent is None and stripped:
            base_indent = indent

        # Empty line inside an active code block — preserve as blank line
        if not stripped:
            current_code_lines.append("")
            continue

        # Description marker at base indent: flush current block, start new description
        if base_indent is not None and _is_description_marker(
            stripped, indent, base_indent
        ):
            example = _flush_example(current_code_lines, current_description)
            if example is not None:
                examples.append(example)
            current_description = stripped.rstrip(":")
            current_code_lines = []
            continue

        # All other non-empty lines go into the code block
        current_code_lines.append(line)

    example = _flush_example(current_code_lines, current_description)
    if example is not None:
        examples.append(example)
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

    examples_text = _extract_examples_section(docstring)
    if examples_text is None:
        return []

    return _parse_example_block(examples_text.split("\n"))


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
