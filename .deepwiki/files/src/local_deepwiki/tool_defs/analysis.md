# File: `src/local_deepwiki/tool_defs/analysis.py`

## File Overview

This file defines a collection of **MCP (Model Control Protocol) tools** used for performing various analysis and search operations within the local DeepWiki system. These tools are designed to enable a language model to query and interact with a knowledge base or documentation repository, offering capabilities such as searching, retrieving context, and analyzing code or project structures.

The tools defined in this module are intended for use in a **read-only** context, as indicated by the import of `_READ_ONLY` from `local_deepwiki.tool_defs.annotations`. This suggests that these tools are meant to fetch or analyze data, rather than modify it.

## Key Concepts

The core abstraction in this file is the **MCP Tool**, which is a standardized way to define actions that a language model can perform. Each tool in this file is defined using the `Tool` class from `mcp.types`, ensuring compatibility with the MCP protocol.

The design rationale behind this structure is to provide a **modular and extensible** interface for interacting with the knowledge base. Tools are grouped by functionality — such as searching, retrieving statistics, or analyzing diffs — allowing for clear separation of concerns and ease of integration with language models or other systems that consume MCP tools.

The use of `_READ_ONLY` suggests a **security and data integrity** concern, ensuring that the tools defined here are not used for write operations, which is important in a controlled environment like a local documentation system.

## Integration

This file is part of the `local_deepwiki.tool_defs` module and is imported by several key components in the larger system:

- It is likely used by the **session state handler** (`src/local_deepwiki/handlers/session_state.py`) to define the set of tools available during a session.
- It may be referenced by the **CLI initialization** (`src/local_deepwiki/cli/init_cli.py`) to register tools for command-line interaction.
- It could also be integrated into the **server logic** (`src/local_deepwiki/server.py`) to expose these tools via an API or protocol.

The import of `Tool` from `mcp.types` indicates that this module is part of a system that adheres to the **MCP standard**, which is used to define tools that can be invoked by LLMs or other agents. The `_READ_ONLY` annotation is a hint that this module is meant to enforce read-only access to data, possibly as a safeguard in environments where modification is not allowed.

## Design Notes

- The tools defined here are **focused on retrieval and analysis**, not modification. This is enforced by the `_READ_ONLY` import, which likely affects how tools are registered or executed.
- The tools are **designed to be stateless**, as they are meant to be invoked as standalone functions with inputs and outputs, aligning with the MCP protocol’s expectations.
- The **modular approach** to tool definition allows for easy expansion or modification of capabilities without affecting the rest of the system.
- There is no indication of complex logic or data transformation within this file — it primarily defines the **tool interfaces**. The actual implementation of these tools is likely found in other modules or plugins, such as those in `src/local_deepwiki/plugins/`.

This file acts as a **contract** for what tools are available for use in the DeepWiki system, ensuring that the tools are consistent with the MCP protocol and adhere to the intended access patterns (read-only).

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
