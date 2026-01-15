# Dependencies Overview

## External Dependencies

The project relies on several third-party libraries for different functionality areas:

### AI and Machine Learning
- **anthropic** (>=0.40) - Anthropic's Claude AI API client
- **openai** (>=1.0) - OpenAI API client for GPT models
- **ollama** (>=0.4) - Local LLM inference server client
- **sentence-transformers** (>=3.0) - Pre-trained models for text embeddings
- **mcp** (>=1.2.0) - Model Context Protocol implementation

### Code Analysis
- **tree-sitter** (>=0.23) - Incremental parsing library for syntax analysis
- **tree-sitter-c** (>=0.23) - C language parser
- **tree-sitter-c-sharp** (>=0.23) - C# language parser
- **tree-sitter-cpp** (>=0.23) - C++ language parser
- **tree-sitter-go** (>=0.23) - Go language parser
- **tree-sitter-java** (>=0.23) - Java language parser
- **tree-sitter-javascript** (>=0.23) - JavaScript language parser
- **tree-sitter-kotlin** (>=0.23) - Kotlin language parser
- **tree-sitter-php** (>=0.23) - PHP language parser
- **tree-sitter-python** (>=0.23) - Python language parser
- **tree-sitter-ruby** (>=0.23) - Ruby language parser
- **tree-sitter-rust** (>=0.23) - Rust language parser
- **tree-sitter-swift** (>=0.0.1) - Swift language parser
- **tree-sitter-typescript** (>=0.23) - TypeScript language parser

### Data Storage and Processing
- **lancedb** (>=0.15) - Vector database for embeddings storage
- **pandas** (>=2.0) - Data manipulation and analysis
- **pydantic** (>=2.0) - Data validation and serialization

### Web and File Processing
- **flask** (>=3.0) - Web framework for server functionality
- **markdown** (>=3.0) - Markdown processing
- **weasyprint** (>=62.0) - HTML to PDF conversion
- **watchdog** (>=4.0) - File system monitoring

### Utilities
- **pyyaml** (>=6.0) - YAML configuration file parsing
- **rich** (>=13.0) - Rich text and beautiful formatting in terminal

## Dev Dependencies

Development and testing tools:

- **black** (>=24.0) - Code formatting
- **isort** (>=5.0) - Import sorting
- **mypy** (>=1.0) - Static type checking
- **pre-commit** (>=3.0) - Git hooks for code quality
- **pytest** (>=8.0) - Testing framework
- **pytest-asyncio** (>=0.24) - Async testing support

## Internal Module Dependencies

Based on the import statements, the internal modules have the following dependency relationships:

### Core Infrastructure
- **[CodeChunker](files/src/local_deepwiki/core/chunker.md)** depends on **[CodeParser](files/src/local_deepwiki/core/parser.md)** for syntax analysis and tree-sitter integration
- **[VectorStore](files/src/local_deepwiki/core/vectorstore.md)** is used by multiple components for embedding storage and retrieval
- **[RepositoryIndexer](files/src/local_deepwiki/core/indexer.md)** orchestrates the indexing process using **[CodeChunker](files/src/local_deepwiki/core/chunker.md)** and configuration

### Generator Components
- **[CrossLinker](files/src/local_deepwiki/generators/crosslinks.md)** and **[EntityRegistry](files/src/local_deepwiki/generators/crosslinks.md)** work together to add cross-references between wiki pages
- **[APIDocExtractor](files/src/local_deepwiki/generators/api_docs.md)** uses **[CodeParser](files/src/local_deepwiki/core/parser.md)** to extract API documentation from code
- **[RelationshipAnalyzer](files/src/local_deepwiki/generators/see_also.md)** and **[FileRelationships](files/src/local_deepwiki/generators/see_also.md)** analyze code relationships for see-also sections
- Multiple generators depend on core models: **[WikiPage](files/src/local_deepwiki/models.md)**, **[CodeChunk](files/src/local_deepwiki/models.md)**, **[ChunkType](files/src/local_deepwiki/models.md)**, and **[Language](files/src/local_deepwiki/models.md)**

### Provider System
- **[EmbeddingProvider](files/src/local_deepwiki/providers/base.md)** serves as the base class for embedding implementations
- **[LocalEmbeddingProvider](files/src/local_deepwiki/providers/embeddings/local.md)** uses sentence-transformers for local embeddings
- **[OpenAIEmbeddingProvider](files/src/local_deepwiki/providers/embeddings/openai.md)** integrates with OpenAI's embedding API
- Provider selection is managed through configuration classes

### Server and Handlers
- Server handlers depend on core indexing, search, and wiki generation functionality
- Multiple test files validate the integration between different components

The architecture follows a layered approach where core parsing and chunking functionality supports higher-level generators, which in turn produce wiki content that can be served through the web interface.

## Module Dependency Graph

The following diagram shows module dependencies. Click on a module to view its documentation. External dependencies are shown with dashed borders.

```mermaid
flowchart TD
    subgraph config[Config]
        M0[config]
    end
    subgraph core[Core]
        M1[chunker]
        M2[deep_research]
        M3[git_utils]
        M4[indexer]
        M5[llm_cache]
        M6[parser]
        M7[vectorstore]
    end
    subgraph export[Export]
        M8[html]
        M9[pdf]
    end
    subgraph generators[Generators]
        M10[api_docs]
        M11[callgraph]
        M12[changelog]
        M13[crosslinks]
        M14[diagrams]
        M15[manifest]
        M16[search]
        M17[see_also]
        M18[source_refs]
        M19[test_examples]
        M20[toc]
        M21[wiki]
    end
    subgraph logging[Logging]
        M22[logging]
    end
    subgraph models[Models]
        M23[models]
    end
    subgraph providers[Providers]
        M24[base]
        M25[embeddings]
        M26[local]
        M27[openai]
        M28[llm]
        M29[anthropic]
        M30[cached]
        M31[ollama]
        M32[openai]
    end
    subgraph server[Server]
        M33[server]
    end
    subgraph web[Web]
        M34[app]
    end
    subgraph external[External Dependencies]
        E0([pathlib]):::external
        E1([typing]):::external
        E2([json]):::external
        E3([re]):::external
        E4([dataclasses]):::external
        E5([collections]):::external
        E6([asyncio]):::external
        E7([os]):::external
        E8([tree_sitter]):::external
        E9([hashlib]):::external
    end
    M1 --> M0
    M1 --> M6
    M1 --> M22
    M1 --> M23
    M2 --> M7
    M2 --> M22
    M2 --> M23
    M2 --> M24
    M3 --> M22
    M4 --> M0
    M4 --> M1
    M4 --> M6
    M4 --> M7
    M4 --> M22
    M4 --> M23
    M4 --> M25
    M5 --> M0
    M5 --> M22
    M5 --> M24
    M6 --> M22
    M6 --> M23
    M7 --> M22
    M7 --> M23
    M7 --> M24
    M8 --> M22
    M9 --> M22
    M10 --> M1
    M10 --> M6
    M10 --> M23
    M11 --> M1
    M11 --> M6
    M11 --> M23
    M12 --> M3
    M12 --> M22
    M13 --> M23
    M14 --> M23
    M15 --> M22
    M16 --> M23
    M17 --> M23
    M18 --> M23
    M21 --> M0
    M21 --> M3
    M21 --> M7
    M21 --> M10
    M21 --> M11
    M21 --> M12
    M21 --> M13
    M21 --> M14
    M21 --> M15
    M21 --> M16
    M21 --> M17
    M21 --> M18
    M21 --> M19
    M21 --> M20
    M21 --> M22
    M21 --> M23
    M21 --> M28
    M26 --> M24
    M27 --> M24
    M29 --> M22
    M29 --> M24
    M30 --> M5
    M30 --> M22
    M30 --> M24
    M31 --> M22
    M31 --> M24
    M32 --> M22
    M32 --> M24
    M33 --> M0
    M33 --> M2
    M33 --> M4
    M33 --> M7
    M33 --> M8
    M33 --> M9
    M33 --> M21
    M33 --> M22
    M33 --> M23
    M33 --> M25
    M33 --> M28
    M34 --> M0
    M34 --> M2
    M34 --> M7
    M34 --> M22
    M34 --> M23
    M34 --> M25
    M34 --> M28
    M0 -.-> E0
    M0 -.-> E1
    M1 -.-> E9
    M1 -.-> E0
    M1 -.-> E8
    M1 -.-> E1
    M2 -.-> E6
    M2 -.-> E5
    M2 -.-> E2
    M2 -.-> E3
    M3 -.-> E4
    M3 -.-> E0
    M3 -.-> E3
    M4 -.-> E2
    M4 -.-> E0
    M5 -.-> E9
    M5 -.-> E0
    M5 -.-> E1
    M6 -.-> E9
    M6 -.-> E0
    M6 -.-> E8
    M6 -.-> E1
    M7 -.-> E2
    M7 -.-> E0
    M7 -.-> E1
    M8 -.-> E2
    M8 -.-> E0
    M9 -.-> E2
    M9 -.-> E0
    M9 -.-> E3
    M10 -.-> E4
    M10 -.-> E0
    M10 -.-> E3
    M10 -.-> E8
    M11 -.-> E0
    M11 -.-> E8
    M12 -.-> E5
    M12 -.-> E4
    M12 -.-> E0
    M13 -.-> E5
    M13 -.-> E4
    M13 -.-> E0
    M13 -.-> E3
    M14 -.-> E4
    M14 -.-> E0
    M14 -.-> E3
    M14 -.-> E1
    M15 -.-> E4
    M15 -.-> E2
    M15 -.-> E0
    M15 -.-> E3
    M15 -.-> E1
    M16 -.-> E2
    M16 -.-> E0
    M16 -.-> E3
    M17 -.-> E5
    M17 -.-> E4
    M17 -.-> E0
    M17 -.-> E3
    M18 -.-> E0
    M18 -.-> E3
    M20 -.-> E4
    M20 -.-> E2
    M20 -.-> E0
    M20 -.-> E1
    M21 -.-> E6
    M21 -.-> E9
    M21 -.-> E2
    M21 -.-> E0
    M21 -.-> E3
    M22 -.-> E7
    M22 -.-> E1
    M23 -.-> E2
    M23 -.-> E0
    M23 -.-> E1
    M24 -.-> E6
    M24 -.-> E1
    M27 -.-> E7
    M29 -.-> E7
    M29 -.-> E1
    M30 -.-> E5
    M31 -.-> E1
    M32 -.-> E7
    M32 -.-> E1
    M33 -.-> E6
    M33 -.-> E2
    M33 -.-> E0
    M33 -.-> E1
    M34 -.-> E6
    M34 -.-> E2
    M34 -.-> E0
    M34 -.-> E1
    click M0 "files/src/local_deepwiki/config.md"
    click M1 "files/src/local_deepwiki/core/chunker.md"
    click M2 "files/src/local_deepwiki/core/deep_research.md"
    click M3 "files/src/local_deepwiki/core/git_utils.md"
    click M4 "files/src/local_deepwiki/core/indexer.md"
    click M5 "files/src/local_deepwiki/core/llm_cache.md"
    click M6 "files/src/local_deepwiki/core/parser.md"
    click M7 "files/src/local_deepwiki/core/vectorstore.md"
    click M8 "files/src/local_deepwiki/export/html.md"
    click M9 "files/src/local_deepwiki/export/pdf.md"
    click M10 "files/src/local_deepwiki/generators/api_docs.md"
    click M11 "files/src/local_deepwiki/generators/callgraph.md"
    click M12 "files/src/local_deepwiki/generators/changelog.md"
    click M13 "files/src/local_deepwiki/generators/crosslinks.md"
    click M14 "files/src/local_deepwiki/generators/diagrams.md"
    click M15 "files/src/local_deepwiki/generators/manifest.md"
    click M16 "files/src/local_deepwiki/generators/search.md"
    click M17 "files/src/local_deepwiki/generators/see_also.md"
    click M18 "files/src/local_deepwiki/generators/source_refs.md"
    click M19 "files/src/local_deepwiki/generators/test_examples.md"
    click M20 "files/src/local_deepwiki/generators/toc.md"
    click M21 "files/src/local_deepwiki/generators/wiki.md"
    click M22 "files/src/local_deepwiki/logging.md"
    click M23 "files/src/local_deepwiki/models.md"
    click M24 "files/src/local_deepwiki/providers/base.md"
    click M25 "files/src/local_deepwiki/providers/embeddings.md"
    click M26 "files/src/local_deepwiki/providers/embeddings/local.md"
    click M27 "files/src/local_deepwiki/providers/embeddings/openai.md"
    click M28 "files/src/local_deepwiki/providers/llm.md"
    click M29 "files/src/local_deepwiki/providers/llm/anthropic.md"
    click M30 "files/src/local_deepwiki/providers/llm/cached.md"
    click M31 "files/src/local_deepwiki/providers/llm/ollama.md"
    click M32 "files/src/local_deepwiki/providers/llm/openai.md"
    click M33 "files/src/local_deepwiki/server.md"
    click M34 "files/src/local_deepwiki/web/app.md"
    classDef external fill:#2d2d3d,stroke:#666,stroke-dasharray: 5 5
```

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/crosslinks.py:16-23`](files/src/local_deepwiki/generators/crosslinks.md)
- [`src/local_deepwiki/generators/diagrams.py:12-21`](files/src/local_deepwiki/generators/diagrams.md)
- `src/local_deepwiki/providers/__init__.py`
- [`src/local_deepwiki/generators/toc.py:10-27`](files/src/local_deepwiki/generators/toc.md)
- [`src/local_deepwiki/logging.py:19-70`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/generators/see_also.py:16-22`](files/src/local_deepwiki/generators/see_also.md)
- [`src/local_deepwiki/providers/embeddings/local.py:8-55`](files/src/local_deepwiki/providers/embeddings/local.md)
- [`src/local_deepwiki/generators/source_refs.py:14-55`](files/src/local_deepwiki/generators/source_refs.md)
- `src/local_deepwiki/providers/embeddings/__init__.py:7-28`
- [`src/local_deepwiki/generators/search.py:14-33`](files/src/local_deepwiki/generators/search.md)


*Showing 10 of 65 source files.*
