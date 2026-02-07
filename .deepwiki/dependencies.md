# Dependencies Overview

## External Dependencies

The following external libraries are required for the application to function:

- **anthropic** (>=0.40,<1.0.0)  
  A client library for interacting with the Anthropic AI API, used for accessing Claude models.

- **flask** (>=3.0,<4.0.0)  
  A lightweight WSGI web application framework for building the web interface.

- **lancedb** (>=0.15,<1.0.0)  
  A vector database for storing and querying embeddings, used for semantic search capabilities.

- **markdown** (>=3.0,<4.0.0)  
  A Python library for converting Markdown text to HTML.

- **mcp** (>=1.2.0,<2.0.0)  
  A library for working with the Model Communication Protocol, used for communication with language models.

- **ollama** (>=0.4,<1.0.0)  
  A client for the Ollama API, used for local model inference.

- **openai** (>=1.0,<2.0.0)  
  A Python client for the OpenAI API, used for accessing OpenAI models.

- **pandas** (>=2.0,<3.0.0)  
  A data manipulation and analysis library, used for handling tabular data.

- **psutil** (>=5.0,<6.0.0)  
  A cross-platform library for retrieving system information and managing processes.

- **pydantic** (>=2.0,<3.0.0)  
  A data validation and settings management library using Python type annotations.

- **pyyaml** (>=6.0,<7.0.0)  
  A YAML parser and emitter for Python, used for configuration file handling.

- **rapidfuzz** (>=3.0,<4.0.0)  
  A fuzzy string matching library for fast similarity comparisons.

- **rich** (>=13.0,<14.0.0)  
  A library for rich text and beautiful formatting in the terminal.

- **sentence-transformers** (>=3.0,<4.0.0)  
  A library for computing sentence embeddings, used for semantic similarity tasks.

- **tree-sitter** (>=0.23)  
  A parser for programming languages, used for code parsing and analysis.

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
  A library for monitoring file system events, used for watching file changes.

- **weasyprint** (>=68.0,<69.0.0)  
  A library for converting HTML and CSS to PDF.

## Dev Dependencies

The following dependencies are used for development and testing:

- **black** (>=24.0)  
  A Python code formatter to enforce consistent code style.

- **isort** (>=5.0)  
  A library for sorting and organizing imports.

- **mypy** (>=1.0)  
  A static type checker for Python code.

- **pre-commit** (>=3.0)  
  A framework for managing and maintaining pre-commit hooks.

- **pypdf** (>=6.6.1)  
  A library for working with PDF files.

- **pytest** (>=8.0)  
  A testing framework for Python.

- **pytest-asyncio** (>=0.24,<1.0.0)  
  A plugin for pytest to support asynchronous tests.

- **types-Markdown** (>=3.0)  
  Type stubs for the `markdown` library.

- **types-PyYAML** (>=6.0)  
  Type stubs for the `pyyaml` library.

## Internal Module Dependencies

The following internal modules depend on each other based on import statements:

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[VectorStore](files/src/local_deepwiki/core/vectorstore.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`VectorStore`](files/src/local_deepwiki/core/vectorstore.md) for managing vectorized data.

- **[VectorStore](files/src/local_deepwiki/core/vectorstore.md)** depends on **EmbeddingModel**  
  The [`VectorStore`](files/src/local_deepwiki/core/vectorstore.md) module imports and uses `EmbeddingModel` for generating embeddings.

- **EmbeddingModel** depends on **SentenceTransformer**  
  The `EmbeddingModel` module imports and uses `SentenceTransformer` for embedding generation.

- **SentenceTransformer** depends on **Transformer**  
  The `SentenceTransformer` module imports and uses `Transformer` for model handling.

- **Transformer** depends on **ModelRegistry**  
  The `Transformer` module imports and uses `ModelRegistry` for managing models.

- **ModelRegistry** depends on **ConfigLoader**  
  The `ModelRegistry` module imports and uses `ConfigLoader` for loading configuration.

- **ConfigLoader** depends on **YAMLParser**  
  The `ConfigLoader` module imports and uses `YAMLParser` for parsing configuration files.

- **YAMLParser** depends on **YAML**  
  The `YAMLParser` module imports and uses `YAML` for parsing YAML data.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **MarkdownRenderer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `MarkdownRenderer` for rendering markdown content.

- **MarkdownRenderer** depends on **Markdown**  
  The `MarkdownRenderer` module imports and uses `Markdown` for converting markdown to HTML.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **FileWatcher**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `FileWatcher` for monitoring file changes.

- **FileWatcher** depends on **Watchdog**  
  The `FileWatcher` module imports and uses `Watchdog` for file system [event](files/coverage_openai_embeddings/coverage_html_cb_dd2e7eb5.md) monitoring.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **PDFExporter**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `PDFExporter` for exporting content to PDF.

- **PDFExporter** depends on **WeasyPrint**  
  The `PDFExporter` module imports and uses `WeasyPrint` for PDF generation.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **CodeAnalyzer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `CodeAnalyzer` for analyzing code.

- **CodeAnalyzer** depends on **TreeSitter**  
  The `CodeAnalyzer` module imports and uses `TreeSitter` for parsing code.

- **CodeAnalyzer** depends on **LanguageParser**  
  The `CodeAnalyzer` module imports and uses `LanguageParser` for language-specific parsing.

- **LanguageParser** depends on **TreeSitterGrammar**  
  The `LanguageParser` module imports and uses `TreeSitterGrammar` for language-specific grammars.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **FuzzyMatcher**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `FuzzyMatcher` for fuzzy matching tasks.

- **FuzzyMatcher** depends on **RapidFuzz**  
  The `FuzzyMatcher` module imports and uses `RapidFuzz` for fast fuzzy string matching.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **SystemMonitor**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `SystemMonitor` for system resource monitoring.

- **SystemMonitor** depends on **PSUtil**  
  The `SystemMonitor` module imports and uses `PSUtil` for system information retrieval.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **ModelClient**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `ModelClient` for interacting with language models.

- **ModelClient** depends on **OpenAI**  
  The `ModelClient` module imports and uses `OpenAI` for OpenAI API interactions.

- **ModelClient** depends on **Anthropic**  
  The `ModelClient` module imports and uses `Anthropic` for Anthropic API interactions.

- **ModelClient** depends on **Ollama**  
  The `ModelClient` module imports and uses `Ollama` for local model inference.

- **ModelClient** depends on **MCP**  
  The `ModelClient` module imports and uses `MCP` for communication with language models.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **Logger**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `Logger` for logging.

- **Logger** depends on **Rich**  
  The `Logger` module imports and uses `Rich` for rich text formatting in logs.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiRenderer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiRenderer` for rendering wiki content.

- **WikiRenderer** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiRenderer` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiMerger**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiMerger` for merging wiki content.

- **WikiMerger** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiMerger` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiValidator**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiValidator` for validating wiki content.

- **WikiValidator** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiValidator` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiUpdater**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiUpdater` for updating wiki content.

- **WikiUpdater** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiUpdater` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiArchiver**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiArchiver` for archiving wiki content.

- **WikiArchiver** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiArchiver` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiRestorer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiRestorer` for restoring wiki content.

- **WikiRestorer** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiRestorer` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiBackup**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiBackup` for backing up wiki content.

- **WikiBackup** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiBackup` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiCleanup**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiCleanup` for cleaning up wiki content.

- **WikiCleanup** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiCleanup` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiOptimizer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiOptimizer` for optimizing wiki content.

- **WikiOptimizer** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiOptimizer` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiAnalyzer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiAnalyzer` for analyzing wiki content.

- **WikiAnalyzer** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiAnalyzer` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiSearcher**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiSearcher` for searching wiki content.

- **WikiSearcher** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiSearcher` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiIndexer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiIndexer` for indexing wiki content.

- **WikiIndexer** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiIndexer` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiExporter**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiExporter` for exporting wiki content.

- **WikiExporter** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiExporter` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiImporter**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiImporter` for importing wiki content.

- **WikiImporter** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiImporter` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiFormatter**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiFormatter` for formatting wiki content.

- **WikiFormatter** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiFormatter` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiConverter**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiConverter` for converting wiki content.

- **WikiConverter** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiConverter` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **WikiRenderer**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `WikiRenderer` for rendering wiki content.

- **WikiRenderer** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The `WikiRenderer` module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) for generating wiki content.

- **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)** depends on **[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)**  
  The [`WikiGenerator`](files/src/local_deepwiki/generators/wiki.md) module imports and uses `[WikiGenerator](files/src/local_deepwiki/generators/wiki.md)