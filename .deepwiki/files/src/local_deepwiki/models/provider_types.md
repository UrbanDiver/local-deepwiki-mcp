# File Overview

This file defines a set of enumerated types used throughout the local_deepwiki project to standardize and validate provider and diagram-related configurations. These enums are used in tool argument models and help enforce type safety and consistency across different components that interact with LLMs, embeddings, diagrams, and codemap generation.

The file is intentionally minimal, focusing only on defining these types to avoid duplication and ensure a consistent interface across the codebase.

# Key Concepts

The core abstraction in this file is the use of `StrEnum` to define strongly-typed enumerations for various provider and diagram types. This choice was made to:

- **Prevent typos and invalid values**: By using enums, we ensure that only predefined string values are accepted for provider types, diagram types, and focus modes.
- **Improve maintainability**: If a new provider or diagram type is added, it must be defined in one place, and all consumers of the type will benefit from the change.
- **Support tool argument models**: These enums are consumed by argument parsers and models that validate and process user inputs, ensuring that only valid options are accepted.

The enums are grouped logically:
- `LLMProviderType` and `EmbeddingProviderType` define supported backends for language and embedding models.
- `DiagramType` defines the kinds of diagrams that can be generated.
- `CodemapFocusType` defines the focus modes for codemap generation, allowing the system to tailor the output based on intent.

# Integration

This file is a foundational part of the project's configuration system. It is imported and used by:

- `EmbeddingProviderType` is used by models to determine which embedding provider to use.
- `DiagramType` is used by `tool_args` to validate and parse diagram generation arguments.
- `CodemapFocusType` is used by `tool_args` and `test_codemap` to control the focus mode during codemap generation.

The enums defined here are consumed by argument parsers and models in the tooling layer, which means this file plays a key role in validating and standardizing inputs before they are passed to more complex components.

# Design Notes

- **Use of StrEnum**: The choice of `StrEnum` over regular `Enum` allows these types to be used directly as strings in contexts where string values are expected, such as configuration or API calls, while still maintaining type safety.

- **Minimalism**: The file only defines the enums and imports, with no additional logic. This keeps the file focused and reduces coupling.

- **Consistency Across Modules**: By centralizing these types, the system avoids having to define similar enums in multiple places, reducing the risk of inconsistencies or divergent definitions.

- **Extensibility**: Adding new provider or diagram types is straightforward and follows a consistent pattern. This supports the project's evolution without requiring changes to consumers of the types.

## API Reference

### class `LLMProviderType`

**Inherits from:** `StrEnum`

Supported LLM providers.


<details>
<summary>View Source (lines 8-13) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/provider_types.py#L8-L13">GitHub</a></summary>

```python
class LLMProviderType(StrEnum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
```

</details>

### class `EmbeddingProviderType`

**Inherits from:** `StrEnum`

Supported embedding providers.


<details>
<summary>View Source (lines 16-20) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/provider_types.py#L16-L20">GitHub</a></summary>

```python
class EmbeddingProviderType(StrEnum):
    """Supported embedding providers."""

    LOCAL = "local"
    OPENAI = "openai"
```

</details>

### class `DiagramType`

**Inherits from:** `StrEnum`

Types of diagrams that can be generated.


<details>
<summary>View Source (lines 23-30) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/provider_types.py#L23-L30">GitHub</a></summary>

```python
class DiagramType(StrEnum):
    """Types of diagrams that can be generated."""

    CLASS = "class"
    DEPENDENCY = "dependency"
    MODULE = "module"
    SEQUENCE = "sequence"
    LANGUAGE_PIE = "language_pie"
```

</details>

### class `CodemapFocusType`

**Inherits from:** `StrEnum`

Focus modes for codemap generation.



<details>
<summary>View Source (lines 33-38) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/provider_types.py#L33-L38">GitHub</a></summary>

```python
class CodemapFocusType(StrEnum):
    """Focus modes for codemap generation."""

    EXECUTION_FLOW = "execution_flow"
    DATA_FLOW = "data_flow"
    DEPENDENCY_CHAIN = "dependency_chain"
```

</details>

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `LLMProviderType` | class | Brian Breidenbach | Feb 20, 2026 | `b807417` refactor: high-priority Pyt... |
| `EmbeddingProviderType` | class | Brian Breidenbach | Feb 20, 2026 | `b807417` refactor: high-priority Pyt... |
| `DiagramType` | class | Brian Breidenbach | Feb 20, 2026 | `b807417` refactor: high-priority Pyt... |
| `CodemapFocusType` | class | Brian Breidenbach | Feb 20, 2026 | `b807417` refactor: high-priority Pyt... |

## Relevant Source Files

- `src/local_deepwiki/models/provider_types.py:8-13`
