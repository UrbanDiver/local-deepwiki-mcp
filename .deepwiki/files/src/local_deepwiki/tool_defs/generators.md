# File: `src/local_deepwiki/tool_defs/generators.py`

## File Overview

This file defines the MCP (Model Control Protocol) tool definitions for various generator functionalities within the `local_deepwiki` project. These tools are responsible for providing access to research-related data and operations such as diagrams, glossaries, call graphs, coverage reports, and more. The tools are marked with annotations like `_READ_ONLY` and `_STATEFUL` to indicate their behavior and interaction patterns with the session state.

The design rationale of this file is to centralize the definition of all generator-related MCP tools, ensuring consistency and ease of integration into the broader CLI and session handling mechanisms.

## Key Concepts

The core abstraction in this file is the use of `Tool` from the `mcp.types` module to define MCP tools. Each tool definition encapsulates:
- A unique name
- A description of its purpose
- Input parameters and their types
- Output schema

These definitions are intended to be used by the CLI (`main.py`) and session handlers (`session_state.py`) to provide a standardized interface for interacting with the underlying generator capabilities, such as [`DiagramGeneratorProtocol`](../generators/protocols.md) and others defined in related modules like `module_health.py`.

The annotations `_READ_ONLY` and `_STATEFUL` are used to indicate whether a tool should be allowed to modify state or is purely for reading. This allows for better session management and access control.

## Integration

This file integrates with the following components in the codebase:

- **CLI Entry Point**: Tools defined here are registered and made available via `src/local_deepwiki/cli/main.py`, enabling end-users to invoke generator tools through the command-line interface.
- **Session State Handling**: The tools are consumed by `src/local_deepwiki/handlers/session_state.py`, which manages tool execution in the context of a session, respecting the stateful or read-only nature of each tool.
- **Generator Implementations**: The actual logic for these tools is implemented in modules like `src/local_deepwiki/generators/analysis/module_health.py` and others, which are called by the tool handlers.

The import of `Tool` from `mcp.types` indicates that this file is part of a system that adheres to the Model Control Protocol, making it compatible with tools and clients that expect MCP-compliant tool definitions.

## Design Notes

- The file is structured to define all generator tools in one place, promoting discoverability and maintainability.
- Tools are defined using a consistent schema, making it easier to extend or modify them in the future.
- The use of `_READ_ONLY` and `_STATEFUL` annotations allows for fine-grained control over how tools interact with session state, which is critical in a multi-user or multi-session environment.
- Tool definitions are intentionally kept minimal and declarative, delegating the actual implementation to other modules, following a separation of concerns pattern.
- The list of tools defined here corresponds to the capabilities exposed by the `local_deepwiki` system, such as retrieving diagrams, changelogs, test examples, and detecting stale documentation. This ensures that only supported operations are exposed via the MCP interface.

## Relevant Source Files

- `src/local_deepwiki/tool_defs/generators.py`
