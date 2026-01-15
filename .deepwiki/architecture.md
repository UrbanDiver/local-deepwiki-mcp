# Architecture Documentation

## System Overview

The local-deepwiki system is a documentation generation tool that uses multiple LLM providers to analyze codebases and generate comprehensive wiki documentation. The system is built around a flexible provider architecture that supports different LLM services (Ollama, Anthropic, OpenAI) and embedding providers for semantic analysis.

## Key Components

### Configuration System

The **[Config](files/src/local_deepwiki/config.md)** class serves as the central configuration hub, managing settings for all system components. The **[LLMConfig](files/src/local_deepwiki/config.md)** class specifically handles LLM provider selection and configuration, supporting three providers through dedicated configuration classes:

- **[OllamaConfig](files/src/local_deepwiki/config.md)** - Manages local Ollama deployment settings with configurable model and API URL
- **[AnthropicConfig](files/src/local_deepwiki/config.md)** - Handles Anthropic Claude model configuration  
- **[OpenAILLMConfig](files/src/local_deepwiki/config.md)** - Manages OpenAI model settings

The **[EmbeddingConfig](files/src/local_deepwiki/config.md)** class manages embedding provider configuration, supporting both local and OpenAI-based embedding services.

### LLM Provider Architecture

The **[LLMProvider](files/src/local_deepwiki/providers/base.md)** abstract base class defines the interface for all LLM implementations. The **[OllamaProvider](files/src/local_deepwiki/providers/llm/ollama.md)** class implements this interface for local Ollama deployments, providing health checking and streaming generation capabilities.

The `get_llm_provider` function acts as a factory, instantiating the appropriate provider based on configuration settings.

### Data Models

The **[ChunkType](files/src/local_deepwiki/models.md)** enum defines the types of code elements the system can process (functions, classes, methods, modules, imports, comments, and other code structures).

The **[ProjectManifest](files/src/local_deepwiki/generators/manifest.md)** class manages project metadata and dependency analysis, providing methods to categorize dependencies and generate technology stack summaries.

### Code Analysis Components

The **[EntityRegistry](files/src/local_deepwiki/generators/crosslinks.md)** class manages the registration and tracking of code entities during analysis. Supporting classes include:

- **[ClassInfo](files/src/local_deepwiki/generators/diagrams.md)** and **[ClassSignature](files/src/local_deepwiki/generators/api_docs.md)** - Handle class metadata and structure analysis
- **[FunctionSignature](files/src/local_deepwiki/generators/api_docs.md)** and **[Parameter](files/src/local_deepwiki/generators/api_docs.md)** - Manage function analysis and parameter extraction
- **[UsageExample](files/src/local_deepwiki/generators/test_examples.md)** - Stores code usage examples for documentation

### Documentation Generation

The **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** class orchestrates the documentation generation process, coordinating between code analysis, LLM providers, and output formatting.

### Error Handling

The **[ResearchCancelledError](files/src/local_deepwiki/core/deep_research.md)** exception provides specific error handling for cancelled research operations.

## Data Flow

1. **Configuration Loading**: The system loads configuration through the [Config](files/src/local_deepwiki/config.md) class, determining which LLM and embedding providers to use
2. **Provider Initialization**: Based on configuration, appropriate provider instances are created via the factory function
3. **Code Analysis**: The system processes source code, categorizing elements using [ChunkType](files/src/local_deepwiki/models.md) and storing metadata in [EntityRegistry](files/src/local_deepwiki/generators/crosslinks.md)
4. **Documentation Generation**: [WikiGenerator](files/src/local_deepwiki/generators/wiki.md) coordinates with LLM providers to generate documentation content
5. **Output Processing**: Generated content is formatted and exported to the html-export directory structure

## Component Diagram

```mermaid
classDiagram
    class Config {
        +LLMConfig llm
        +EmbeddingConfig embedding
    }
    
    class LLMConfig {
        +provider: str
        +OllamaConfig ollama
        +AnthropicConfig anthropic
        +OpenAILLMConfig openai
    }
    
    class LLMProvider {
        <<abstract>>
        +generate()
        +check_health()
        +name()
    }
    
    class OllamaProvider {
        +generate()
        +check_health()
        +name()
    }
    
    class WikiGenerator {
        +generate_documentation()
    }
    
    class EntityRegistry {
        +register_entity()
        +get_entities()
    }
    
    class ProjectManifest {
        +get_tech_stack_summary()
        +get_dependency_list()
    }
    
    class ChunkType {
        <<enumeration>>
        FUNCTION
        CLASS
        METHOD
        MODULE
        IMPORT
        COMMENT
        OTHER
    }
    
    class ClassInfo {
        +name: str
        +signature: ClassSignature
    }
    
    class FunctionSignature {
        +name: str
        +parameters: List[Parameter]
    }
    
    Config --> LLMConfig
    LLMConfig --> OllamaConfig
    LLMConfig --> AnthropicConfig
    LLMConfig --> OpenAILLMConfig
    LLMProvider <|-- OllamaProvider
    WikiGenerator --> LLMProvider
    WikiGenerator --> EntityRegistry
    EntityRegistry --> ClassInfo
    EntityRegistry --> FunctionSignature
    ClassInfo --> ClassSignature
    FunctionSignature --> Parameter
```

## Key Design Decisions

### Provider Pattern Implementation
The system implements a provider pattern for LLM services, allowing runtime selection between different AI providers. This is evident in the [LLMConfig](files/src/local_deepwiki/config.md) class supporting multiple provider configurations and the factory function that instantiates the appropriate provider.

### Configuration-Driven Architecture
The extensive configuration system using Pydantic models enables flexible deployment scenarios. Each provider has its own configuration class with sensible defaults, allowing users to customize behavior without code changes.

### Enumerated Code Types
The [ChunkType](files/src/local_deepwiki/models.md) enum provides a standardized way to categorize different code elements, ensuring consistent processing across the analysis pipeline.

### Separation of Concerns
The architecture clearly separates code analysis ([EntityRegistry](files/src/local_deepwiki/generators/crosslinks.md), [ClassInfo](files/src/local_deepwiki/generators/diagrams.md)), content generation ([WikiGenerator](files/src/local_deepwiki/generators/wiki.md)), and provider management ([LLMProvider](files/src/local_deepwiki/providers/base.md) hierarchy), making the system modular and testable.

### Health Checking
The LLM provider interface includes health checking capabilities, allowing the system to verify provider availability before attempting generation operations.

## Workflow Sequences

The following diagrams show how data flows through key operations:

### Indexing Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant I as RepositoryIndexer
    participant P as CodeParser
    participant C as CodeChunker
    participant E as EmbeddingProvider
    participant V as VectorStore
    participant F as FileSystem

    U->>I: index(repo_path, full_rebuild)
    I->>F: find_source_files()
    F-->>I: source_files[]
    I->>F: load_index_status()
    F-->>I: previous_status

    loop For each file batch
        I->>P: parse_file(path)
        P-->>I: tree, source
        I->>C: chunk_file(tree, source)
        C-->>I: CodeChunk[]
        I->>E: embed(chunk_contents)
        E-->>I: embeddings[]
        I->>V: add_chunks(chunks, embeddings)
        V-->>I: success
    end

    I->>F: save_index_status()
    I-->>U: IndexStatus
```

### Wiki Generation Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant W as WikiGenerator
    participant V as VectorStore
    participant L as LLMProvider
    participant F as FileSystem

    U->>W: generate_wiki(index_status)

    rect rgb(40, 40, 60)
        note right of W: Generate Overview
        W->>V: search("main entry point")
        V-->>W: context_chunks
        W->>L: generate(overview_prompt)
        L-->>W: overview_markdown
        W->>F: write(index.md)
    end

    rect rgb(40, 40, 60)
        note right of W: Generate Architecture
        par Parallel searches
            W->>V: search("core components")
            W->>V: search("patterns")
            W->>V: search("data flow")
        end
        V-->>W: combined_context
        W->>L: generate(architecture_prompt)
        L-->>W: architecture_markdown
        W->>F: write(architecture.md)
    end

    rect rgb(40, 40, 60)
        note right of W: Generate Module Docs
        loop For each module
            W->>V: search(module_query)
            V-->>W: module_chunks
            W->>L: generate(module_prompt)
            L-->>W: module_markdown
            W->>F: write(modules/{name}.md)
        end
    end

    W->>W: add_cross_links()
    W->>W: add_see_also_sections()
    W->>F: write(search.json, toc.json)
    W-->>U: WikiStructure
```

### Deep Research Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant D as DeepResearchPipeline
    participant L as LLMProvider
    participant V as VectorStore

    U->>D: research(question)

    rect rgb(50, 40, 40)
        note right of D: Step 1: Decomposition
        D->>L: decompose_question(question)
        L-->>D: SubQuestion[]
    end

    rect rgb(40, 50, 40)
        note right of D: Step 2: Parallel Retrieval
        par For each sub-question
            D->>V: search(sub_q1)
            D->>V: search(sub_q2)
            D->>V: search(sub_q3)
        end
        V-->>D: SearchResult[][]
    end

    rect rgb(40, 40, 50)
        note right of D: Step 3: Gap Analysis
        D->>L: analyze_gaps(context)
        L-->>D: follow_up_queries[]
    end

    rect rgb(50, 50, 40)
        note right of D: Step 4: Follow-up Retrieval
        par For each follow-up
            D->>V: search(follow_up)
        end
        V-->>D: additional_results[]
    end

    rect rgb(50, 40, 50)
        note right of D: Step 5: Synthesis
        D->>L: synthesize(all_context)
        L-->>D: comprehensive_answer
    end

    D-->>U: DeepResearchResult
```

## Relevant Source Files

The following source files were used to generate this documentation:

- [`tests/test_parser.py:24-123`](files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](files/tests/test_retry.md)
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- `tests/test_changelog.py:18-96`
- [`tests/test_vectorstore.py:9-28`](files/tests/test_vectorstore.md)
- `tests/test_pdf_export.py:21-80`
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`


*Showing 10 of 76 source files.*
