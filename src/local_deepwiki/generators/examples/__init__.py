"""Example extraction from test files, docstrings, and vector search."""

from __future__ import annotations

from local_deepwiki.generators.examples.docstring import (
    CodeExample,
    parse_docstring_examples,
    parse_doctest_examples,
    parse_google_style_examples,
)
from local_deepwiki.generators.examples.extractor import (
    CodeExampleExtractor,
    format_code_examples_markdown,
)
from local_deepwiki.generators.examples.orchestrator import (
    UsageExample,
    extract_examples_for_entities,
    format_examples_markdown,
    get_file_examples,
)
from local_deepwiki.generators.examples.plugin import (
    ExamplesWikiGenerator,
    get_examples_for_api_page,
)

__all__ = [
    "CodeExample",
    "CodeExampleExtractor",
    "ExamplesWikiGenerator",
    "UsageExample",
    "extract_examples_for_entities",
    "format_code_examples_markdown",
    "format_examples_markdown",
    "get_examples_for_api_page",
    "get_file_examples",
    "parse_docstring_examples",
    "parse_doctest_examples",
    "parse_google_style_examples",
]
