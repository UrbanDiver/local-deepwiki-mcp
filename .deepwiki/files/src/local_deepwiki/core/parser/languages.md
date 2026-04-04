# File: `src/local_deepwiki/core/parser/languages.py`

## File Overview

This file defines the language detection configuration and mappings for Tree-sitter parser modules used within the `local_deepwiki` project. It serves as a configuration layer that maps language identifiers to their respective Tree-sitter modules, enabling dynamic loading of language-specific parsers.

The primary responsibility of this file is to provide a centralized and extensible way to manage language-specific parser modules. It leverages Python's import mechanisms to dynamically load Tree-sitter modules at runtime, based on language identifiers defined in the [`Language`](../../models/foundation.md) enum.

## Key Concepts

### Language Enum Integration
The file imports [`Language`](../../models/foundation.md) from `local_deepwiki.models`, which likely defines a set of supported languages. This enum is used as a key to map to Tree-sitter modules, ensuring type safety and consistency across the parser system.

### Dynamic Module Loading
The file uses `importlib` to dynamically load Tree-sitter modules for each supported language. This approach enables flexibility in parser selection and allows for easy extension of supported languages without hardcoding module paths.

### Tree-sitter Module Mappings
The design rationale behind mapping languages to Tree-sitter modules is to abstract the parser implementation. This abstraction allows the core parser logic to remain language-agnostic while delegating language-specific parsing tasks to Tree-sitter, which provides efficient and accurate parsing for various programming and markup languages.

## Integration

This file is part of the core parsing infrastructure and integrates with:
- `local_deepwiki/__init__.py`: Likely initializes or configures the parser system.
- `local_deepwiki/cli/init_cli.py`: May use this file to determine supported languages during CLI initialization.
- `local_deepwiki/core/chunk_extractors.py`: Could utilize language-specific parsers for content extraction.
- `local_deepwiki/generators/context_builder.py`: Might require language detection to build context appropriately.
- `local_deepwiki/generators/wiki/term_validator.py`: Could use language-specific parsers for term validation.

The [`get_logger`](../../logging.md) import suggests this module is part of a logging-aware system, likely to track parser loading or language detection events. The [`Language`](../../models/foundation.md) enum integration implies this module is used in conjunction with other components that require language-aware processing.

## Design Notes

### Extensibility
The use of `importlib` and a mapping approach makes this module highly extensible. Adding support for a new language only requires adding a new entry in the mapping, assuming the Tree-sitter module is available.

### Runtime Loading
Tree-sitter modules are loaded at runtime rather than compile time. This approach allows for more flexible deployments where only necessary language modules are loaded, reducing memory footprint and startup time.

### Error Handling
While not shown in the provided code, the dynamic loading pattern implies that this module likely includes error handling for cases where a Tree-sitter module for a given language is not available or cannot be imported.

### Type Safety
By using the [`Language`](../../models/foundation.md) enum as a key, the design ensures that only valid language identifiers are used, preventing runtime errors from invalid language strings.

## Relevant Source Files

- `src/local_deepwiki/core/parser/languages.py`
