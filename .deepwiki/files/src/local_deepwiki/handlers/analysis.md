# File: `src/local_deepwiki/handlers/analysis.py`

## File Overview

This file serves as a **re-export shim** for backward compatibility, aggregating and exposing a wide range of analysis-related handler functions from their respective submodules. It is designed to provide a unified interface to the analysis functionality while supporting a modular internal structure.

The module is part of the `local_deepwiki.handlers` package and is intended to be imported by other modules or CLI components that rely on these analysis handlers. It does not contain any logic of its own but acts as a bridge between the old monolithic interface and the newly refactored, more granular handler modules.

## Key Concepts

### Modularization and Separation of Concerns

The handlers in this module have been **split into focused submodules** to improve maintainability and clarity:

- `analysis_search`: For search-related functionality.
- `analysis_entity`: For entity-specific operations like explanation and impact analysis.
- `analysis_diff`: For handling diffs and related queries.
- `analysis_metadata`: For retrieving metadata and project information.
- `analysis_architecture`: For architecture-level insights, health checks, and trends.

This modularization follows the **Single Responsibility Principle**, allowing developers to locate and modify specific analysis logic without affecting unrelated parts of the system.

### Re-export Pattern

This module uses a **re-export pattern**, where it imports functions from other modules and exposes them at the top level. This is a common technique for maintaining backward compatibility when refactoring code into smaller, more focused units. It ensures that existing code that depends on the old interface continues to work without modification.

## Integration

### Imports and Dependencies

This file imports from several other modules within the `local_deepwiki.handlers` package:

- `local_deepwiki.handlers.analysis_architecture`
- `local_deepwiki.handlers.analysis_diff`
- `local_deepwiki.handlers.analysis_entity`
- `local_deepwiki.handlers.analysis_metadata`
- `local_deepwiki.handlers.analysis_search`

These imports are used to gather handler functions and expose them for consumption by other parts of the application.

### Relationship to Other Files

This file is likely consumed by:

- `src/local_deepwiki/cli/main.py`: The main CLI entrypoint that routes commands to appropriate handlers.
- `src/local_deepwiki/cli/config_validator.py`: May use these handlers for validation or reporting.
- Other internal modules that depend on the analysis interface.

The re-export pattern allows the CLI and other consumers to continue using the old import style while the internal structure is modernized.

## Design Notes

### Backward Compatibility

This module was introduced to **preserve backward compatibility** during a refactor. It ensures that code that previously imported handlers directly from `local_deepwiki.handlers.analysis` continues to function without needing updates.

### Function Granularity

Each submodule is responsible for a specific domain of analysis:

- **Search**: Text-based lookups within the wiki.
- **Entity**: Understanding and analyzing specific entities (e.g., classes, functions).
- **Diff**: Comparing changes in code or documentation.
- **Metadata**: Project-level insights and stats.
- **Architecture**: High-level architectural health and dependency analysis.

This granular design supports both **scalability** and **testability**, allowing developers to test and develop each domain in isolation.

### Trade-offs

- **Import Overhead**: While this module provides a convenient single import, it increases the number of imports in the top-level namespace.
- **Maintenance**: Changes in the submodule interface require updates in this file to maintain compatibility.

This design is a pragmatic compromise between **modern code organization** and **legacy compatibility**.

## Usage Examples

*Examples extracted from test files*

### get_design_smells with top_n=5 returns at most 5 smells

From `test_analysis_architecture.py::TestHandleGetDesignSmellsOverflow::test_top_n_limits_smells`:

```python
"local_deepwiki.generators.analysis.design_smells.analyze_design_smells",
    return_value=fake_result,
):
    result = await handle_get_design_smells(
        {"repo_path": str(tmp_path), "top_n": 5}
    )

data = json.loads(result[0].text)
assert len(data["smells"]) == 5
```

### get_cross_module_dependencies with top_n=20 limits modules to 20

From `test_analysis_architecture.py::TestHandleGetCrossModuleDependenciesOverflow::test_top_n_limits_nodes`:

```python
"imports": [],
    }
    for i in range(49)
]
fake_result = {
    "status": "success",
    "modules": fake_modules,
    "edges": fake_edges,
    "mermaid": "graph LR",
    "stats": {"total_modules": 50, "total_edges": 49},
}
with patch(
    "local_deepwiki.generators.analysis.module_dependencies.analyze_cross_module_dependencies",
    return_value=fake_result,
):
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(tmp_path), "top_n": 20}
    )

data = json.loads(result[0].text)
assert len(data["modules"]) == 20
```

## Relevant Source Files

- `src/local_deepwiki/handlers/analysis.py`
