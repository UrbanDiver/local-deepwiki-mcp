# File: `src/local_deepwiki/tool_defs/analysis.py`

## File Overview

This file defines a collection of MCP (Model Control Protocol) tools related to analysis and search functionalities within the DeepWiki system. These tools enable querying and understanding the structure, content, and relationships of a codebase or documentation project.

The purpose of this module is to expose a set of analysis capabilities through the MCP protocol, allowing external tools or agents to perform tasks such as searching documentation, retrieving project metadata, analyzing code complexity, and understanding architectural dependencies.

The design rationale behind this file is to centralize and standardize the definition of these analysis tools using the `Tool` type from the MCP library. It also leverages a read-only annotation (`_READ_ONLY`) to ensure that these tools are marked appropriately for access control and safety.

## Key Concepts

### Tool Definitions via `mcp.types.Tool`

Each analysis function is defined as a `Tool` object, which encapsulates the tool's name, description, and input schema. This abstraction ensures that tools are consistently structured and can be easily integrated into MCP-compatible systems.

### Read-Only Access Control

The use of `_READ_ONLY` annotation indicates that all tools defined in this module are intended for read-only operations. This design choice ensures that no tool in this file can modify data, aligning with the security and integrity principles of the DeepWiki system.

### Modular and Extensible Design

The tools defined here are modular and cover a wide range of analysis needs, including:
- Search and retrieval (`search_wiki`, `fuzzy_search`)
- Project metadata (`get_project_manifest`, `get_wiki_stats`)
- Code and documentation understanding (`explain_entity`, `analyze_diff`)
- Complexity and architecture insights (`get_complexity_metrics`, `get_architecture_summary`)

These tools are designed to be composable and can be invoked independently or in combination to support more complex workflows.

## Integration

This file is part of the `local_deepwiki.tool_defs` module and integrates with the broader DeepWiki system by providing standardized tool definitions for use in MCP-based workflows.

### Imports

- `from mcp.types import Tool`: Used to define each tool with a consistent structure.
- `from local_deepwiki.tool_defs.annotations import _READ_ONLY`: Applied to all tools to enforce read-only access.

### Related Files

This file is closely related to:
- `src/local_deepwiki/cli/config_validator.py`: Likely uses these tools to validate configurations or check project health.
- `src/local_deepwiki/cli/main.py`: May integrate these tools into the CLI's command set.
- `src/local_deepwiki/generators/analysis/module_health.py`: Could provide backend logic for some of the analysis tools.
- `src/local_deepwiki/handlers/session_state.py`: May use these tools to manage or respond to user requests during a session.
- `src/local_deepwiki/plugins/__init__.py`: Could be used to dynamically register or load these tools as plugins.

## Design Notes

### Tool Consistency

All tools in this module are defined using the same structure and schema, which promotes consistency and ease of integration with MCP-compatible systems. This also allows for predictable behavior when tools are invoked from external agents.

### Read-Only Enforcement

The `_READ_ONLY` annotation is a design choice to prevent unintended writes or modifications to the system state. It ensures that all tools defined in this file are safe to execute and aligns with the principle of least privilege.

### Modularization of Analysis Capabilities

The tools are organized to support a wide range of analysis tasks, from basic search and retrieval to advanced complexity and impact analysis. This modularization allows for both granular and holistic views of the project, enabling flexible and powerful querying capabilities.

### Future Extensibility

While the current implementation defines a set of core analysis tools, the structure of the file is designed to support future additions. New tools can be added by following the same pattern, ensuring that the module remains maintainable and scalable.

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

- `src/local_deepwiki/tool_defs/analysis.py`
