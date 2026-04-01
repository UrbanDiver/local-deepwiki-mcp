# File: `src/local_deepwiki/handlers/_shared.py`

## File Overview

This file serves as a **backward-compatibility re-export shim** for symbols that were previously defined directly in the `_shared` module. It re-exports a wide variety of functions, classes, and constants from other focused modules within the `local_deepwiki.handlers` package and related core modules.

The purpose of this file is to maintain compatibility with external consumers who may have imported directly from `_shared`. It ensures that existing code using these imports continues to work without modification, while the actual implementation has been refactored into more modular and purpose-specific locations.

This shim is a temporary solution and is marked for removal in a future release.

## Key Concepts

### Modular Refactoring
The symbols previously defined in this file have been moved to more focused modules to improve code organization and maintainability:

- **Error Handling**: Moved to `_error_handling`
- **Export Validation**: Moved to `_export_validation`
- **Index Helpers**: Moved to `_index_helpers`
- **Progress Management**: Moved to `_progress`
- **Response Building**: Moved to `_response`

This modular approach aligns with the principle of single responsibility and improves testability and clarity.

### Re-Exports and Imports
This module aggregates and re-exports symbols from various submodules, ensuring that external consumers of the library do not need to update their import paths. The re-exports include:
- Utility functions for handling errors and tool responses
- Constants for forbidden directories and validation
- Models and arguments for various operations (e.g., indexing, research, export)
- Progress tracking and notification mechanisms
- Access control and authentication utilities

These re-exports are not only for convenience but also to ensure that all components required for handler logic are available in a consistent interface.

## Integration

This file is part of the `local_deepwiki.handlers` module hierarchy and integrates with the following key areas of the codebase:

- **Handlers**: The module is used by various handler modules (e.g., `_error_handling`, `_index_helpers`) to provide shared utilities.
- **Core Modules**: It imports from `local_deepwiki.core` modules like `audit`, `path_utils`, `rate_limiter`, and `vectorstore`, indicating its role in integrating core functionalities with handler logic.
- **CLI and Plugins**: The file is indirectly referenced by CLI tools and plugin systems, which rely on the shared interfaces and utilities for consistent behavior.
- **Error Handling and Validation**: It integrates with error handling and validation modules, ensuring that errors are consistently formatted and managed.

Because this module is a re-export shim, it acts as a bridge between legacy code and refactored internal components, allowing the system to evolve without breaking existing integrations.

## Design Notes

### Why a Shim?
The use of a re-export shim is a **transitional strategy** to support backward compatibility. It allows developers to refactor code into more modular and maintainable structures without breaking existing consumers. The long-term goal is to remove this file entirely.

### Symbols and Their Origins
Many of the re-exported symbols originate from:
- **`_error_handling`**: For consistent error handling across tools and operations.
- **`_export_validation`**: To validate export paths and prevent writing to forbidden directories.
- **`_index_helpers`**: For vector store creation, research result formatting, and index status loading.
- **`_progress`**: For progress tracking and notification, which is critical in long-running operations.
- **`_response`**: To build consistent tool responses and resource URIs.

These are foundational utilities for the DeepWiki system's operation and are critical to the integrity of tool workflows.

### Imports and Dependencies
The file imports from:
- Core utilities (`audit`, `path_utils`, `rate_limiter`, `vectorstore`)
- Error handling and validation modules
- Models and arguments for operations (e.g., [`AskQuestionArgs`](../models/tool_args.md), [`ExportWikiHtmlArgs`](../models/tool_args.md))
- Progress and notification systems
- Security and access control components

This wide range of dependencies underscores the central role of `_shared` in integrating various subsystems of the DeepWiki system.

### Temporary Nature
This module is not intended for direct use by new code. All new code should import directly from the respective modules (e.g., `_error_handling`, `_index_helpers`, etc.) to ensure that future compatibility is maintained and the codebase remains clean and modular.

## Relevant Source Files

- `src/local_deepwiki/handlers/_shared.py`
