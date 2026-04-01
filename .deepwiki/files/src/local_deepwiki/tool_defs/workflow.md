# File: `src/local_deepwiki/tool_defs/workflow.py`

## File Overview

This file defines the set of MCP (Model Control Protocol) tools used for managing workflows within the local_deepwiki system. These tools are responsible for codebase analysis, entity explanation, codemap generation, and web server operations. The module centralizes the definition of these tools, making them available for use in the CLI and other integrations.

The design rationale behind this file is to provide a clean separation of tool definitions from their implementations, enabling modular and extensible functionality. Each tool is defined with appropriate metadata, including read-only or side-effect annotations, to help systems understand the impact of invoking each tool.

## Key Concepts

The core abstraction in this file is the `Tool` type from the `mcp.types` module, which defines a standardized interface for tools within the MCP ecosystem. This allows for consistent tool registration, execution, and interaction across different components.

The tools defined in this file are grouped into several functional categories:
- **Code Analysis Tools**: [`generate_codemap`](../generators/codemap/generator.md), `suggest_codemap_topics`, `query_codebase`, `find_tools`
- **Workflow Execution Tools**: `run_workflow`, `batch_explain_entities`
- **Web Server Tools**: `serve_wiki`, `stop_wiki_server`

These tools leverage annotations such as `_READ_ONLY` and `_SIDE_EFFECT` to indicate whether a tool modifies state or only reads from it, which is critical for system safety and predictability.

## Integration

This file is part of the `local_deepwiki.tool_defs` module and imports from `mcp.types` and `local_deepwiki.tool_defs.annotations`. It is designed to be consumed by other modules in the project, such as:

- `src/local_deepwiki/cli/main.py` — likely uses these tools to register CLI commands.
- `src/local_deepwiki/cli/config_validator.py` — may validate tool definitions or dependencies.
- `src/local_deepwiki/handlers/session_state.py` — could use these tools to manage session-specific workflows.
- `src/local_deepwiki/generators/analysis/module_health.py` — may integrate with `query_codebase` or `find_tools` for analysis.

By defining tools here, this file acts as a central registry, making it easier to extend or modify tool behavior without affecting other parts of the system.

## Design Notes

- The use of `_READ_ONLY` and `_SIDE_EFFECT` annotations ensures that tools are categorized properly for execution environments that may enforce strict access policies or audit requirements.
- The tool definitions are kept in a single file to promote clarity and ease of maintenance, especially as more tools are added to support advanced workflows.
- The tools are designed to be modular and composable, supporting both interactive and batch execution flows.
- No complex or non-obvious logic is present in this file; it is purely a definition layer for MCP tools.

## Relevant Source Files

- `src/local_deepwiki/tool_defs/workflow.py`
