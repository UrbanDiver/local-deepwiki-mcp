"""Wiki and diagram generators."""

from __future__ import annotations

from local_deepwiki.generators.analysis import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphGenerator,
    DependencyNode,
    generate_dependency_graph_page,
)
from local_deepwiki.generators.examples import (
    CodeExample,
    CodeExampleExtractor,
    ExamplesWikiGenerator,
    UsageExample,
    extract_examples_for_entities,
    format_code_examples_markdown,
    format_examples_markdown,
    get_examples_for_api_page,
    get_file_examples,
    parse_docstring_examples,
    parse_doctest_examples,
    parse_google_style_examples,
)
from local_deepwiki.generators.protocols import (
    AnalysisGeneratorProtocol,
    DiagramGeneratorProtocol,
)

__all__ = [
    # Protocols
    "AnalysisGeneratorProtocol",
    "DiagramGeneratorProtocol",
    # Dependency graph
    "DependencyEdge",
    "DependencyGraph",
    "DependencyGraphGenerator",
    "DependencyNode",
    "generate_dependency_graph_page",
    # Data classes
    "CodeExample",
    "UsageExample",
    # Extractors
    "CodeExampleExtractor",
    # Test file extraction
    "extract_examples_for_entities",
    "get_file_examples",
    "format_examples_markdown",
    # Docstring parsing
    "parse_docstring_examples",
    "parse_doctest_examples",
    "parse_google_style_examples",
    # Formatting
    "format_code_examples_markdown",
    # Wiki plugin
    "ExamplesWikiGenerator",
    "get_examples_for_api_page",
]
