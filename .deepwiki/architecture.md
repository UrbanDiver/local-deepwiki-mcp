# System Architecture Documentation

## System Overview

Local DeepWiki is a documentation generation system that creates comprehensive technical documentation from codebases. It combines AST-based code parsing with vector search and LLM generation to produce wiki-style documentation automatically.

The system works in three phases:
1. **Parsing**: Tree-sitter parses source files into ASTs
2. **Indexing**: Code chunks are embedded and stored in LanceDB
3. **Generation**: LLMs generate documentation using RAG (Retrieval-Augmented Generation)

## Key Components

### RepositoryIndexer
The [RepositoryIndexer](files/src/local_deepwiki/core/indexer.md) class orchestrates the indexing pipeline. It coordinates file discovery, parsing, chunking, and vector storage. Supports incremental updates by tracking file hashes.

### CodeParser
The [CodeParser](files/src/local_deepwiki/core/parser.md) class uses tree-sitter to parse source files into ASTs. Supports Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, and Swift.

### CodeChunker
The [CodeChunker](files/src/local_deepwiki/core/chunker.md) class extracts semantic chunks from parsed ASTs - classes, functions, methods with their docstrings and signatures. Maintains metadata about each chunk (file path, line numbers, language).

### VectorStore
The [VectorStore](files/src/local_deepwiki/core/vectorstore.md) class manages the LanceDB vector database. Handles embedding generation, storage, and semantic search queries.

### WikiGenerator
The [WikiGenerator](files/src/local_deepwiki/generators/wiki.md) class produces documentation pages using LLM generation. Queries the vector store for relevant code context, then prompts the LLM to generate markdown documentation.

### LLM Providers
Abstraction layer for LLM providers (Ollama, Anthropic, OpenAI). Located in `providers/llm.py`. Factory function `get_llm_provider()` returns the configured provider.

### Embedding Providers
Abstraction for embedding generation. Supports local sentence-transformers (all-MiniLM-L6-v2) and OpenAI embeddings. Located in `providers/embeddings.py`.

### Diagram Functions
Functions in `generators/diagrams.py` create Mermaid diagrams for architecture visualization, class diagrams, and dependency graphs.

### Config
The [Config](files/src/local_deepwiki/config.md) class manages configuration loaded from `~/.config/local-deepwiki/config.yaml`. Includes LLM settings, embedding settings, and parsing options.

## Data Flow

```mermaid
graph TD
    A[Source Files] --> B[CodeParser]
    B --> C[CodeChunker]
    C --> D[EmbeddingProvider]
    D --> E[VectorStore/LanceDB]

    F[WikiGenerator] --> G[VectorStore Search]
    G --> H[Relevant Chunks]
    H --> I[LLM Provider]
    I --> J[Generated Markdown]
    J --> K[Wiki Files]

    E --> G
```

## Indexing Pipeline

```mermaid
sequenceDiagram
    participant I as RepositoryIndexer
    participant P as CodeParser
    participant C as CodeChunker
    participant E as EmbeddingProvider
    participant V as VectorStore

    I->>I: Find source files
    loop For each file
        I->>P: Parse file
        P-->>I: AST
        I->>C: Chunk AST
        C-->>I: CodeChunks
        I->>E: Generate embeddings
        E-->>I: Vectors
        I->>V: Store chunks + vectors
    end
    I->>I: Save index status
```

## Wiki Generation Pipeline

```mermaid
sequenceDiagram
    participant W as WikiGenerator
    participant V as VectorStore
    participant L as LLMProvider
    participant D as Diagram Functions

    W->>V: Search for overview context
    V-->>W: Relevant chunks
    W->>L: Generate index.md
    L-->>W: Markdown content

    W->>V: Search for architecture context
    W->>L: Generate architecture.md
    W->>D: Generate mermaid diagrams

    loop For each module/file
        W->>V: Search for module context
        W->>L: Generate module docs
    end

    W->>W: Apply cross-links
    W->>W: Add see-also sections
```

## Component Diagram

```mermaid
graph LR
    subgraph Core
        Parser[CodeParser]
        Chunker[CodeChunker]
        Indexer[RepositoryIndexer]
        VS[VectorStore]
    end

    subgraph Generators
        Wiki[WikiGenerator]
        Diagrams[diagrams.py]
        CrossLinks[crosslinks.py]
        ApiDocs[api_docs.py]
    end

    subgraph Providers
        LLM[LLM Provider]
        Embed[Embedding Provider]
    end

    subgraph Web
        Flask[Flask App]
    end

    Indexer --> Parser
    Indexer --> Chunker
    Indexer --> VS
    Chunker --> Embed
    Wiki --> VS
    Wiki --> LLM
    Wiki --> Diagrams
    Wiki --> CrossLinks
    Wiki --> ApiDocs
    Flask --> VS
```

## Key Design Decisions

### Tree-sitter for Parsing
Uses tree-sitter for language-agnostic AST parsing. Provides accurate, fast parsing across multiple languages without language-specific parsers.

### LanceDB for Vector Storage
Embedded vector database that requires no external services. Stores vectors alongside metadata for efficient retrieval.

### Incremental Updates
Tracks file hashes to detect changes. Only re-indexes modified files and regenerates affected wiki pages.

### Provider Abstraction
LLM and embedding providers are abstracted behind factory functions. Allows switching between local (Ollama) and cloud (Anthropic/OpenAI) without code changes.

### RAG for Documentation
Uses Retrieval-Augmented Generation - searches for relevant code context before prompting the LLM. Produces more accurate, grounded documentation.

## See Also

- [Source Files](files/index.md) - Individual file documentation
- [Dependencies](dependencies.md) - Dependency analysis
- [Modules](modules/index.md) - Module documentation
