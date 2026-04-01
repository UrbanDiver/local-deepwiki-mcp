# File: `src/local_deepwiki/tool_defs/annotations.py`

## File Overview

This file defines shared constants for MCP (Model Control Protocol) tool annotations used throughout the `local_deepwiki` project. It serves as a centralized location for defining and reusing tool annotation structures, ensuring consistency across different tools and handlers.

The file is minimal in scope, focusing solely on importing and exposing the `ToolAnnotations` type from the `mcp.types` module. This design promotes type safety and clarity when defining tools that interact with the MCP protocol.

## Key Concepts

The core abstraction in this file is the `ToolAnnotations` type, which represents structured metadata about tools in the MCP ecosystem. This type is imported directly from `mcp.types` and serves as a foundational element for defining how tools are described and communicated within the system.

The choice to centralize this import in a dedicated file aligns with the project's goal of maintaining clean, modular code. By defining shared types in a single location, the codebase avoids duplication and ensures that all tools use consistent annotation structures.

## Integration

This file integrates with the broader `local_deepwiki` codebase by providing a shared import point for `ToolAnnotations`. It is likely used by other modules in the `tool_defs` directory, such as those in `src/local_deepwiki/tools/__init__.py`, to define tool metadata.

The import chain shows that this module depends on `mcp.types`, indicating that it is part of a larger system that adheres to the MCP protocol. The related files, such as `src/local_deepwiki/handlers/session_state.py` and `src/local_deepwiki/generators/analysis/module_health.py`, may consume or extend these annotations to define their own tools or handlers.

## Design Notes

This file's minimal implementation reflects a design decision to keep the tool definition layer lightweight and focused. Rather than defining new annotation structures, it reuses existing ones from `mcp.types`, which ensures compatibility with the MCP protocol and reduces the chance of introducing inconsistencies.

The file does not handle any edge cases or complex logic, as its purpose is purely to expose a type. This simplicity is intentional, as it allows the file to serve as a stable dependency for other modules without introducing potential points of failure or complexity.

## Relevant Source Files

- `src/local_deepwiki/tool_defs/annotations.py`
