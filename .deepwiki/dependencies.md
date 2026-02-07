# Dependencies Overview

## External Dependencies

The following external libraries are required for the application to function:

- **anthropic** (>=0.40,<1.0.0)  
  Provides access to Anthropic's AI models, particularly Claude, for natural language processing tasks.

- **flask** (>=3.0,<4.0.0)  
  A lightweight web framework used for building the application's API and web interface.

- **lancedb** (>=0.15,<1.0.0)  
  A vector database for storing and querying embeddings, used for semantic search and similarity retrieval.

- **markdown** (>=3.0,<4.0.0)  
  Used for parsing and rendering Markdown text into HTML.

- **mcp** (>=1.2.0,<2.0.0)  
  Enables interaction with the Model Control Protocol for managing and controlling AI model interactions.

- **ollama** (>=0.4,<1.0.0)  
  Provides access to locally hosted LLMs via the Ollama API.

- **openai** (>=1.0,<2.0.0)  
  Official SDK for interacting with OpenAI's API, used for accessing GPT models and related services.

- **pandas** (>=2.0,<3.0.0)  
  A data manipulation and analysis library used for handling structured data.

- **psutil** (>=5.0,<6.0.0)  
  Provides system and process utilities for monitoring resource usage.

- **pydantic** (>=2.0,<3.0.0)  
  Used for data validation and settings management with automatic type hints.

- **pyyaml** (>=6.0,<7.0.0)  
  Library for parsing and emitting YAML data, used for configuration files.

- **rapidfuzz** (>=3.0,<4.0.0)  
  A fast fuzzy string matching library used for approximate string matching and similarity calculations.

- **rich** (>=13.0,<14.0.0)  
  Enables rich text and beautiful formatting in the terminal.

- **sentence-transformers** (>=3.0,<4.0.0)  
  Provides pre-trained models for generating sentence embeddings for semantic similarity tasks.

- **tree-sitter** (>=0.23)  
  A parser for programming languages used for syntax analysis and code understanding.

- **tree-sitter-c** (>=0.23)  
  Tree-sitter grammar for C language.

- **tree-sitter-c-sharp** (>=0.23)  
  Tree-sitter grammar for C# language.

- **tree-sitter-cpp** (>=0.23)  
  Tree-sitter grammar for C++ language.

- **tree-sitter-go** (>=0.23)  
  Tree-sitter grammar for Go language.

- **tree-sitter-java** (>=0.23)  
  Tree-sitter grammar for Java language.

- **tree-sitter-javascript** (>=0.23)  
  Tree-sitter grammar for JavaScript language.

- **tree-sitter-kotlin** (>=0.23)  
  Tree-sitter grammar for Kotlin language.

- **tree-sitter-php** (>=0.23)  
  Tree-sitter grammar for PHP language.

- **tree-sitter-python** (>=0.23)  
  Tree-sitter grammar for Python language.

- **tree-sitter-ruby** (>=0.23)  
  Tree-sitter grammar for Ruby language.

- **tree-sitter-rust** (>=0.23)  
  Tree-sitter grammar for Rust language.

- **tree-sitter-swift** (>=0.0.1)  
  Tree-sitter grammar for Swift language.

- **tree-sitter-typescript** (>=0.23)  
  Tree-sitter grammar for TypeScript language.

- **watchdog** (>=4.0,<5.0.0)  
  A library for monitoring file system events, used for watching changes in configuration or source files.

- **weasyprint** (>=68.0,<69.0.0)  
  A library for converting HTML and CSS to PDF.

## Dev Dependencies

The following dependencies are used for development and testing:

- **black** (>=24.0)  
  A code formatter for Python to enforce consistent code style.

- **isort** (>=5.0)  
  A tool to sort and organize import statements in Python files.

- **mypy** (>=1.0)  
  A static type checker for Python to detect type-related issues.

- **pre-commit** (>=3.0)  
  A framework for managing and maintaining pre-commit hooks for code quality checks.

- **pypdf** (>=6.6.1)  
  A library for working with PDF files, used for parsing and manipulating PDF content.

- **pytest** (>=8.0)  
  A testing framework for Python used for unit and integration testing.

- **pytest-asyncio** (>=0.24,<1.0.0)  
  A plugin for pytest to support asynchronous tests.

- **types-Markdown** (>=3.0)  
  Type stubs for the Markdown library.

- **types-PyYAML** (>=6.0)  
  Type stubs for PyYAML.

## Internal Module Dependencies

The following internal modules depend on each other based on import statements:

### Core Pipeline
- **ToolHandlers** (`handlers.py`) depends on **RepositoryIndexer**, **VectorStore**, **DeepResearchEngine**, all generators
- **RepositoryIndexer** (`core/indexer.py`) depends on **CodeParser**, **SemanticChunker**, **VectorStore**, **WikiGenerator**
- **CodeParser** (`core/parser.py`) depends on **tree-sitter** grammars (13 languages)
- **SemanticChunker** (`core/chunker.py`) depends on **CodeParser** for AST nodes
- **VectorStore** (`core/vectorstore.py`) depends on **lancedb**, **pandas**, embedding providers

### Research & Search
- **DeepResearchEngine** (`core/deep_research.py`) depends on **VectorStore**, LLM providers
- **FuzzySearch** (`core/fuzzy_search.py`) depends on **rapidfuzz**
- **LLMCache** (`core/llm_cache.py`) provides caching for LLM providers
- **RateLimiter** (`core/rate_limiter.py`) wraps LLM provider calls

### Wiki Generation
- **WikiGenerator** (`generators/wiki.py`) depends on **WikiFileGenerator**, **WikiModuleGenerator**, **WikiPageGenerator**
- **DiagramGenerator** (`generators/diagrams.py`) depends on parsed chunk data
- **CoverageAnalyzer** (`generators/coverage.py`) depends on parsed chunk data
- **CallGraphGenerator** (`generators/callgraph.py`) depends on parsed chunk data

### Providers
- **OllamaProvider** (`providers/llm/ollama.py`) depends on **ollama**
- **AnthropicProvider** (`providers/llm/anthropic.py`) depends on **anthropic**
- **OpenAIProvider** (`providers/llm/openai.py`) depends on **openai**
- **LocalEmbeddingProvider** (`providers/embeddings/local.py`) depends on **sentence-transformers**
- **OpenAIEmbeddingProvider** (`providers/embeddings/openai.py`) depends on **openai**

### Export & Web
- **HtmlExporter** (`export/html.py`) depends on wiki markdown files, **markdown**
- **PdfExporter** (`export/pdf.py`) depends on **weasyprint**
- **WebApp** (`web/app.py`) depends on **flask**, wiki structure

### Infrastructure
- **FileWatcher** (`watcher.py`) depends on **watchdog**, **RepositoryIndexer**
- **DeepWikiConfig** (`config.py`) depends on **pydantic**, **pyyaml**
- **SecretDetector** (`core/secret_detector.py`) scans files before indexing
- **AccessControl** (`security/access_control.py`) enforces RBAC on tool handlers