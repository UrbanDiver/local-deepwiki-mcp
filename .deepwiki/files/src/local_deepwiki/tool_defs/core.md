# File: `src/local_deepwiki/tool_defs/core.py`

## File Overview

This file defines the core MCP (Model Control Protocol) tool definitions used within the `local_deepwiki` project. These tools form the foundational interface for interacting with a local knowledge base, enabling operations such as indexing repositories, querying information, and exporting documentation.

The purpose of this module is to standardize and expose a set of tools that can be used by an LLM or other agents to perform tasks like searching code, reading wiki pages, and conducting deep research. These definitions are built using the `mcp.types.Tool` class and are annotated with metadata to indicate their behavior (read-only, stateful, write-safe).

## Key Concepts

### Tool Definitions
The module exports a set of core tools, each represented as an instance of `mcp.types.Tool`. These tools are designed to be consumed by an MCP-compatible agent to perform operations like reading wiki content, searching code, and exporting documentation. Each tool is defined with a name, description, and parameters.

### Annotations
The tools are annotated with `_READ_ONLY`, `_STATEFUL`, and `_WRITE_SAFE` to indicate their operational characteristics:
- `_READ_ONLY`: Tools that only read data without modifying it.
- `_STATEFUL`: Tools that may maintain or modify state during execution.
- `_WRITE_SAFE`: Tools that are safe to execute in write contexts.

These annotations help agents understand the behavior and safety profile of each tool, allowing for better orchestration and security.

## Integration

This file is part of the `local_deepwiki.tool_defs` module and integrates with the broader `local_deepwiki` project by providing standardized tool definitions that can be used by the CLI, session handlers, and other components.

### Dependencies
- `mcp.types.Tool`: The base class used to define tools in the MCP protocol.
- `local_deepwiki.tool_defs.annotations`: Provides annotations to classify tool behavior.

### Related Files
This module is closely related to:
- `src/local_deepwiki/cli/main.py`: Likely consumes these tool definitions to register them with the CLI.
- `src/local_deepwiki/handlers/session_state.py`: May use these tools to manage or update session state.
- `src/local_deepwiki/plugins/__init__.py`: May integrate these tools as part of a plugin system.

These integrations suggest that `core.py` acts as a central definition point for tools, which are then consumed by various parts of the system to provide functionality.

## Design Notes

### Tool Abstraction
The design of tools in this file reflects a modular and extensible approach. Each tool is defined independently, which allows for easy modification or replacement without affecting other tools. This abstraction also aligns with the MCP protocol's design, where tools are defined as separate entities that can be dynamically registered and invoked.

### Annotation Strategy
The use of annotations (`_READ_ONLY`, `_STATEFUL`, `_WRITE_SAFE`) is a deliberate design choice to support safe and predictable tool execution. These annotations help agents make informed decisions about when and how to execute tools, especially in environments where security and state consistency are critical.

### Minimal Implementation
This file currently only includes imports and does not contain the full tool definitions. The actual implementation of the tools (e.g., `index_repository`, `ask_question`) is likely in other modules, and this file serves as an interface or definition layer. This approach supports a clean separation of concerns, where tool definitions are decoupled from their implementation, improving maintainability and testability.

## Relevant Source Files

- `src/local_deepwiki/tool_defs/core.py`
