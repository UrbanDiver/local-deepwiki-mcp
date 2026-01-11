# Dependencies Overview

## External Dependencies

### Core Libraries
- `yaml` - For YAML configuration parsing
- `pydantic` - For configuration and data model validation
- `tree_sitter` - For code parsing and AST traversal
- `sentence_transformers` - For local embedding generation
- `openai` - For OpenAI API integration
- `ollama` - For Ollama LLM integration
- `anthropic` - For Anthropic Claude API integration
- `lancedb` - For vector database operations
- `pytest` - For testing framework (development dependency)

### Language Parsers
- `tree_sitter_python`
- `tree_sitter_javascript`
- `tree_sitter_typescript`
- `tree_sitter_go`
- `tree_sitter_rust`
- `tree_sitter_java`
- `tree_sitter_c`
- `tree_sitter_cpp`
- `tree_sitter_swift`

## Internal Module Dependencies

### Core Modules
- `local_deepwiki.config` - Configuration management
- `local_deepwiki.models` - Data models and enums
- `local_deepwiki.core.chunker` - Code chunking functionality
- `local_deepwiki.core.parser` - Code parsing utilities
- `local_deepwiki.core.vectorstore` - Vector database operations

### Providers
- `local_deepwiki.providers.base` - Abstract provider interfaces
- `local_deepwiki.providers.embeddings` - Embedding provider implementations
- `local_deepwiki.providers.llm` - LLM provider implementations

### Generators
- `local_deepwiki.generators.crosslinks` - Cross-link generation
- `local_deepwiki.generators.diagrams` - Diagram generation
- `local_deepwiki.generators.see_also` - "See also" section generation
- `local_deepwiki.generators.search` - Search functionality

## Notable Dependency Patterns

### Configuration Management
- Uses `pydantic` BaseModel for structured configuration
- Centralized configuration via `get_config()` function
- Configurable embedding and chunking parameters

### Provider Pattern
- Abstract base classes (`EmbeddingProvider`, `LLMProvider`) with concrete implementations
- Dependency injection through provider factories
- Support for multiple embedding backends (local, OpenAI)

### Code Parsing
- Dynamic language support via tree-sitter language parsers
- Language-specific parsing with unified interface
- AST-based code analysis and chunking

### Data Flow
- Data models defined in `models.py` used across modules
- Chunking → Parsing → Embedding → Vector Store pipeline
- Cross-module data sharing through shared models and configuration

### Testing
- Test modules follow same import patterns as source modules
- Comprehensive test coverage of core functionality
- Integration testing with actual providers and parsers

## Module Dependency Graph

The following diagram shows internal module dependencies:

```mermaid
flowchart TD
    M0[config]
    M1[chunker]
    M2[indexer]
    M3[parser]
    M4[vectorstore]
    M5[crosslinks]
    M6[diagrams]
    M7[search]
    M8[see_also]
    M9[models]
    M10[base]
    M11[local]
    M12[openai]
    M13[anthropic]
    M14[ollama]
    M15[openai]
    M16[test_chunker]
    M17[test_config]
    M18[test_crosslinks]
    M19[test_parser]
    M20[test_see_also]
    M1 --> M0
    M1 --> M3
    M1 --> M9
    M2 --> M0
    M2 --> M1
    M2 --> M3
    M2 --> M4
    M2 --> M9
    M3 --> M9
    M4 --> M9
    M4 --> M10
    M5 --> M9
    M6 --> M9
    M7 --> M9
    M8 --> M9
    M11 --> M10
    M12 --> M10
    M13 --> M10
    M14 --> M10
    M15 --> M10
    M16 --> M1
    M16 --> M9
    M17 --> M0
    M18 --> M5
    M18 --> M9
    M19 --> M3
    M19 --> M9
    M20 --> M8
    M20 --> M9
```