# Module: local_deepwiki

## Module Purpose

The `local_deepwiki` module provides core functionality for analyzing code repositories, generating documentation, and supporting AI-powered code understanding tools. It includes components for parsing source code, computing cohesion metrics, detecting secrets, managing tool handlers, and integrating with the MCP (Model Context Protocol) server.

## Key Classes and Functions

### Classes

- **_UnionFind**: Disjoint-set data structure with path compression, used for computing LCOM4 cohesion metrics.

### Functions

- **[setup_logging](../files/src/local_deepwiki/logging.md)**: Configures logging for the local-deepwiki package with customizable level, format, and output destinations.
- **[get_logger](../files/src/local_deepwiki/logging.md)**: Retrieves a logger instance for a specific module, ensuring proper namespace handling.
- **[list_tools](../files/src/local_deepwiki/server.md)**: Lists available tools for the MCP server.
- **[analyze_cohesion](../files/src/local_deepwiki/generators/analysis/cohesion.md)**: Runs both class and module cohesion analyses on a repository, computing LCOM4 and internal-import ratios.
- **[analyze_class_cohesion](../files/src/local_deepwiki/generators/analysis/cohesion.md)**: Computes LCOM4 for classes in Python files using tree-sitter AST walking.
- **[compute_module_cohesion](../files/src/local_deepwiki/generators/analysis/cohesion.md)**: Calculates internal-import ratio per module directory.
- **[compute_lcom4](../files/src/local_deepwiki/generators/analysis/cohesion.md)**: Computes Lack of Cohesion of Methods (LCOM4) for a single class node.
- **_extract_self_fields**: Walks a method node and returns names of `self.<field>` accesses.
- **_extract_base_name**: Extracts the final identifier from a base class node.
- **_has_abstractmethod_decorator**: Checks if a method node has an `@abstractmethod` [decorator](../files/src/local_deepwiki/providers/retry.md).
- **_extract_keyword_base**: Extracts the base name from a keyword argument like `metaclass=ABCMeta`.
- **_find_base_class_pattern**: Checks base classes for ABC or Protocol inheritance.
- **_is_mostly_abstract**: Determines if at least half of the class methods are abstract.
- **_classify_class_pattern**: Classifies a class as a known OOP pattern where LCOM4 is misleading.
- **_extract_imports**: Returns full dotted module paths from all import statements.
- **_module_label**: Converts a relative file path to a dotted module label.
- **_parent_module**: Returns the parent module label (everything up to the last dot).
- **walk**: Internal helper function for traversing AST nodes.

## How Components Interact

The module components work together to provide comprehensive code analysis capabilities:

1. **Logging System**: The [`setup_logging`](../files/src/local_deepwiki/logging.md) and [`get_logger`](../files/src/local_deepwiki/logging.md) functions provide consistent logging across the package, ensuring that all modules can easily obtain properly configured loggers.

2. **Cohesion Analysis**: The cohesion analysis functions ([`analyze_cohesion`](../files/src/local_deepwiki/generators/analysis/cohesion.md), [`analyze_class_cohesion`](../files/src/local_deepwiki/generators/analysis/cohesion.md), [`compute_module_cohesion`](../files/src/local_deepwiki/generators/analysis/cohesion.md)) work together to provide insights into code structure. They use the `_UnionFind` class for efficient set operations during LCOM4 computation, and AST walking utilities from `local_deepwiki.core.parser.ast_utils` to parse code.

3. **Tool Integration**: The [`list_tools`](../files/src/local_deepwiki/server.md) function and various handler functions in `local_deepwiki.handlers` provide the interface for the MCP server to expose capabilities like code analysis, documentation generation, and secret detection.

4. **Code Parsing**: The cohesion analysis relies on [`CodeParser`](../files/src/local_deepwiki/core/parser/code_parser.md) from `local_deepwiki.core.parser.code_parser` and AST utilities from `local_deepwiki.core.parser.ast_utils` to parse and analyze source code.

## Usage Examples

### Setting up logging

```python
from local_deepwiki.logging import setup_logging

# Configure logging with default settings
logger = setup_logging()

# Configure logging with custom level and file output
logger = setup_logging(
    level="DEBUG",
    log_file="deepwiki.log"
)
```

### Analyzing code cohesion

```python
from pathlib import Path
from local_deepwiki.generators.analysis.cohesion import analyze_cohesion

# Analyze cohesion for a repository
repo_path = Path("/path/to/repo")
result = analyze_cohesion(repo_path, top_n=10)

print(f"Total classes: {result['stats']['total_classes']}")
print(f"Average LCOM4: {result['stats']['avg_lcom']}")
```

### Listing available tools

```python
from local_deepwiki.server import list_tools

# Get list of available tools
tools = list_tools()
for tool in tools:
    print(tool.name)
```

## Dependencies

This module depends on:
- `argparse`, `asyncio`, `collections`, `concurrent`, `contextlib`, `contextvars`, `dataclasses`, `datetime`, `enum`, `fnmatch`, `hashlib`, `importlib`, `itertools`, `json`, `LanceDB`, `local_deepwiki`, `logging`, `mcp`, `operator`, `os`, `sys`
- `local_deepwiki.core.chunk_extractors`
- `local_deepwiki.core.parser.ast_utils`
- `local_deepwiki.core.parser.code_parser`
- `local_deepwiki.generators.analysis.source_filter`
- `local_deepwiki.models`
- `local_deepwiki.handlers`
- `local_deepwiki.tool_defs`
- `local_deepwiki.prompts`
- `local_deepwiki.validation`
- `local_deepwiki.error_factories`
- `local_deepwiki.errors`
- `local_deepwiki.events`
- `local_deepwiki.progress`
- `local_deepwiki.core.audit`
- `local_deepwiki.core.chunker`
- `local_deepwiki.core.llm_cache`
- `local_deepwiki.core.parsing_pipeline`
- `local_deepwiki.core.protocols`
- `local_deepwiki.core.reranker`
- `local_deepwiki.core.secret_detector`
- `local_deepwiki.core.tracing`
- `local_deepwiki.watchers`
- `local_deepwiki.cli_progress`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](../files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/logging.py:28-83`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:98-100`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](../files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](../files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](../files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](../files/src/local_deepwiki/error_factories.md)
- [`src/local_deepwiki/errors.py:53-118`](../files/src/local_deepwiki/errors.md)
- [`src/local_deepwiki/watcher.py:40-46`](../files/src/local_deepwiki/watcher.md)


*Showing 10 of 269 source files.*
