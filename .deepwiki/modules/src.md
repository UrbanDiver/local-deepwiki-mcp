# Module: local_deepwiki

## Module Purpose

The `local_deepwiki` module provides core functionality for analyzing and understanding code repositories. It includes tools for static analysis, architecture evaluation, dependency mapping, and coupling metrics computation. The module is designed to work as part of an MCP (Model Context Protocol) server, offering analysis capabilities through tool definitions and handlers.

## Key Classes and Functions

### Analysis Architecture Handlers

- [`handle_get_layer_dependencies`](../files/src/local_deepwiki/handlers/analysis_architecture.md) - Processes tool calls for analyzing architectural layer dependencies in Python files
- `_collect_file_metrics` - Scans Python files to compute file-level metrics like line counts and file sizes
- [`handle_get_architecture_summary`](../files/src/local_deepwiki/handlers/analysis_architecture.md) - Deprecated handler that delegates to [`handle_get_architecture_health`](../files/src/local_deepwiki/handlers/analysis_architecture.md) with full detail
- [`handle_get_hotspots`](../files/src/local_deepwiki/handlers/analysis_architecture.md) - Ranks functions by complexity metrics (cyclomatic complexity, parameter count, etc.)
- `_count_smells_by_type` - Counts occurrences of design smells grouped by type
- `_count_module_edges` - Counts total edge appearances per module name in dependency graphs
- [`handle_get_cross_module_dependencies`](../files/src/local_deepwiki/handlers/analysis_architecture.md) - Builds inter-module import graphs and returns module nodes and edges
- [`handle_get_coupling_metrics`](../files/src/local_deepwiki/handlers/analysis_architecture.md) - Computes Robert C. Martin coupling metrics (Ca, Ce, I, A, D) per module

### Coupling Metrics Functions

- `_count_classes_in_file` - Counts total and abstract classes in a Python file using AST parsing
- `_is_abstract_node` - Determines if a class node is abstract based on inheritance or decorators
- `_walk` - Recursively walks AST nodes to find classes
- `_candidate_labels` - Generates candidate module labels for file paths
- `_take2` - Helper function to take first two path parts for module labeling
- `_compute_abstractness` - Computes abstractness scores for modules
- `_compute_ca_ce` - Calculates afferent and efferent coupling counts
- `_is_test_module` - Identifies if a module name looks like a test module
- [`analyze_coupling_metrics`](../files/src/local_deepwiki/generators/analysis/coupling.md) - Main function that computes all coupling metrics for modules

### Tool Definitions

- `search_wiki` - Tool for searching the wiki
- `get_project_manifest` - Tool for retrieving project manifest information
- `get_file_context` - Tool for getting context around a specific file
- `fuzzy_search` - Tool for fuzzy searching in the repository
- `get_wiki_stats` - Tool for retrieving wiki statistics
- `explain_entity` - Tool for explaining code entities
- `impact_analysis` - Tool for performing impact analysis
- `get_complexity_metrics` - Tool for getting complexity metrics
- `analyze_diff` - Tool for analyzing code differences
- `ask_about_diff` - Tool for asking questions about code differences
- `get_layer_dependencies` - Tool for getting layer dependencies
- `get_architecture_summary` - Tool for getting architecture summary

## How Components Interact

The module components work together through a layered architecture:

1. **Core Analysis**: The [`analyze_coupling_metrics`](../files/src/local_deepwiki/generators/analysis/coupling.md) function orchestrates coupling analysis by:
   - Using [`analyze_cross_module_dependencies`](../files/src/local_deepwiki/generators/analysis/module_dependencies.md) to build dependency graphs
   - Computing afferent/efferent coupling via `_compute_ca_ce`
   - Calculating abstractness scores with `_compute_abstractness`
   - Determining instability and distance metrics

2. **File Processing**: Functions like `_count_classes_in_file` and `_walk` process individual Python files using AST parsing via [`CodeParser`](../files/src/local_deepwiki/core/parser/code_parser.md) and `tree-sitter` to extract class information.

3. **Architecture Analysis**: Handlers like [`handle_get_layer_dependencies`](../files/src/local_deepwiki/handlers/analysis_architecture.md) and [`handle_get_cross_module_dependencies`](../files/src/local_deepwiki/handlers/analysis_architecture.md) provide MCP tool interfaces that:
   - Validate input arguments using pydantic models
   - Call analysis functions with appropriate parameters
   - Format results into tool responses using [`make_tool_text_content`](../files/src/local_deepwiki/handlers/_response.md)

4. **Dependency Management**: The module uses `module_dependencies` functions to analyze inter-module relationships and `source_filter` to identify Python files for analysis.

## Usage Examples

```python
# Analyze coupling metrics for a repository
from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
from pathlib import Path

result = analyze_coupling_metrics(
    repo_path=Path("/path/to/repo"),
    module_filter="local_deepwiki",
    exclude_tests=True
)
print(result["metrics"])
```

```python
# Get cross-module dependencies
from local_deepwiki.handlers.analysis_architecture import handle_get_cross_module_dependencies
from local_deepwiki.models import GetCrossModuleDependenciesArgs

args = GetCrossModuleDependenciesArgs(
    repo_path="/path/to/repo",
    summary_only=False,
    top_n=10
)
result = handle_get_cross_module_dependencies(args)
```

```python
# Analyze layer dependencies
from local_deepwiki.handlers.analysis_architecture import handle_get_layer_dependencies
from local_deepwiki.models import GetLayerDependenciesArgs

args = GetLayerDependenciesArgs(
    repo_path="/path/to/repo",
    summary_only=False
)
result = handle_get_layer_dependencies(args)
```

## Dependencies

This module depends on several core components:

- `mcp.types` - For tool definitions and types
- `local_deepwiki.core.parser` - For code parsing using AST
- `local_deepwiki.generators.analysis.module_dependencies` - For cross-module dependency analysis
- `local_deepwiki.generators.analysis.source_filter` - For identifying Python source files
- `local_deepwiki.logging` - For logging functionality
- `local_deepwiki.models` - For argument validation using pydantic
- `local_deepwiki.handlers._error_handling` - For error handling
- `local_deepwiki.handlers._response` - For response formatting
- `local_deepwiki.security` - For permission control
- `tree-sitter` - For AST parsing
- `pydantic` - For data validation
- `pathlib` - For path operations
- `typing` - For type hints

The module also imports various analysis generators including:
- `local_deepwiki.generators.analysis.layer_analysis`
- `local_deepwiki.generators.analysis.hotspots`
- `local_deepwiki.generators.analysis.design_smells`
- `local_deepwiki.generators.analysis.architecture_health`
- `local_deepwiki.generators.analysis.architecture_compare`
- `local_deepwiki.generators.analysis.architecture_composite`
- `local_deepwiki.generators.analysis.onboarding`
- `local_deepwiki.generators.analysis.recommendations`
- `local_deepwiki.generators.analysis.module_health`
- `local_deepwiki.generators.analysis.tours`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/tool_defs/analysis.py`](../files/src/local_deepwiki/tool_defs/analysis.md)
- [`src/local_deepwiki/generators/analysis/coupling.py:48-90`](../files/src/local_deepwiki/generators/analysis/coupling.md)
- [`src/local_deepwiki/handlers/analysis_architecture.py:43-94`](../files/src/local_deepwiki/handlers/analysis_architecture.md)
- [`src/local_deepwiki/models/tool_args.py:15-49`](../files/src/local_deepwiki/models/tool_args.md)
- [`src/local_deepwiki/generators/analysis/design_smells.py:162-163`](../files/src/local_deepwiki/generators/analysis/design_smells.md)
- [`src/local_deepwiki/logging.py:28-83`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:92-94`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](../files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](../files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`


*Showing 10 of 263 source files.*
