# File: `src/local_deepwiki/tool_defs/analysis.py`

## File Overview

This file defines a collection of MCP (Model Context Protocol) tools related to analysis and search functionalities within the local DeepWiki system. These tools are designed to provide structured access to wiki data, enabling users to search, analyze, and understand the content and structure of a knowledge base.

The file serves as a central definition point for various analysis-related tools that can be invoked by an LLM or other system components to perform tasks such as searching for entities, retrieving project metadata, analyzing code complexity, and understanding architectural dependencies.

## Key Concepts

The core abstraction in this file is the definition of `Tool` instances from the `mcp.types` module, which represent discrete capabilities that can be exposed to a language model or agent. Each tool is defined with a specific name, description, and input/output schema, enabling precise interaction with the underlying system.

These tools are marked with `_READ_ONLY` annotations, indicating that they are intended for read-only operations, which aligns with the system's design to prevent unintended modifications to the wiki content or structure during analysis tasks.

The tools are purposefully grouped around common analysis workflows:
- **Search and retrieval**: `search_wiki`, `fuzzy_search`, `explain_entity`
- **Project and content understanding**: `get_project_manifest`, `get_wiki_stats`, `get_file_context`
- **Code and architecture analysis**: `get_complexity_metrics`, `impact_analysis`, `get_layer_dependencies`, `get_architecture_summary`
- **Diff and change analysis**: `analyze_diff`, `ask_about_diff`

This grouping reflects a modular approach to analysis, allowing for fine-grained access to different aspects of the wiki system, and supports a wide range of use cases from simple entity lookup to complex architectural impact analysis.

## Integration

This file is imported by:
- `src/local_deepwiki/cli/init_cli.py` — Likely used to register the tools with the CLI interface
- `src/local_deepwiki/handlers/session_state.py` — Possibly used to dynamically configure or provide tools during session handling
- `src/local_deepwiki/plugins/__init__.py` — Used to initialize or load analysis tools as part of plugin system
- `src/local_deepwiki/plugins/base.py` — Potentially used to define base tool behavior or extend plugin capabilities
- `src/local_deepwiki/server.py` — Likely used to expose the tools via the server's API or tool registry

The integration with `mcp.types.Tool` and `local_deepwiki.tool_defs.annotations._READ_ONLY` suggests that this file is part of a larger system that supports MCP-compliant tool definitions and enforces read-only access patterns, which is critical for ensuring system integrity and preventing accidental data modification during analysis.

## Design Notes

- **Read-only enforcement**: The use of `_READ_ONLY` annotations indicates a strong design decision to enforce immutability during analysis operations, likely to prevent unintended side effects or data corruption.
- **Tool Schema Consistency**: All tools are defined using the same foundational `Tool` type, which ensures consistency in how tools are structured and consumed across the system.
- **Modular Tool Design**: The tools are grouped logically, enabling a clear separation of concerns and making it easier to extend or modify individual functionalities without affecting others.
- **MCP Compliance**: The use of `mcp.types.Tool` implies that this module is part of a system designed to be compatible with Model Context Protocol, supporting interoperability with LLMs or agents that understand this standard.

This file does not include any complex logic or algorithms; its primary role is to define the interface and behavior of analysis tools, making it a critical component in enabling the system's analytical capabilities.

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
