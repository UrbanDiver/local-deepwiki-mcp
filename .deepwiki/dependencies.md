# Dependencies Overview

## External Dependencies

The following third-party libraries are required for the application to function:

- **anthropic** (>=0.40)  
  A client library for interacting with the Anthropic AI API, used for accessing Claude models.

- **flask** (>=3.0)  
  A lightweight web framework for building web applications and APIs.

- **lancedb** (>=0.15)  
  A vector database for storing and querying embeddings, used for semantic search capabilities.

- **markdown** (>=3.0)  
  A library for parsing and rendering Markdown text into HTML.

- **mcp** (>=1.2.0)  
  A library for managing model configuration and prompting, used for orchestrating AI interactions.

- **ollama** (>=0.4)  
  A client for interacting with the Ollama API, used for local LLM inference.

- **openai** (>=1.0)  
  A client library for interacting with the OpenAI API, used for accessing OpenAI models.

- **pandas** (>=2.0)  
  A data manipulation and analysis library, used for handling structured data.

- **pydantic** (>=2.0)  
  A data validation and settings management library, used for defining data models and validation.

- **pyyaml** (>=6.0)  
  A library for parsing and emitting YAML, used for configuration file handling.

- **rich** (>=13.0)  
  A library for rich text formatting in the terminal, used for improved console output.

- **sentence-transformers** (>=3.0)  
  A library for generating sentence embeddings, used for semantic similarity and vectorization.

- **tree-sitter** (>=0.23)  
  A parser for programming languages, used for syntax parsing and code analysis.

- **tree-sitter-c** (>=0.23)  
  Tree-sitter grammar for the C programming language.

- **tree-sitter-cpp** (>=0.23)  
  Tree-sitter grammar for the C++ programming language.

- **tree-sitter-go** (>=0.23)  
  Tree-sitter grammar for the Go programming language.

- **tree-sitter-java** (>=0.23)  
  Tree-sitter grammar for the Java programming language.

- **tree-sitter-javascript** (>=0.23)  
  Tree-sitter grammar for the JavaScript programming language.

- **tree-sitter-python** (>=0.23)  
  Tree-sitter grammar for the Python programming language.

- **tree-sitter-rust** (>=0.23)  
  Tree-sitter grammar for the Rust programming language.

- **tree-sitter-swift** (>=0.0.1)  
  Tree-sitter grammar for the Swift programming language.

- **tree-sitter-typescript** (>=0.23)  
  Tree-sitter grammar for the TypeScript programming language.

- **watchdog** (>=4.0)  
  A library for monitoring file system events, used for watching and reacting to file changes.

## Dev Dependencies

The following dependencies are used for development and testing:

- **pytest** (>=8.0)  
  A testing framework for Python, used for running unit and integration tests.

- **pytest-asyncio** (>=0.24)  
  A plugin for pytest to support asyncio testing, used for testing asynchronous code.

## Internal Module Dependencies

Based on the import statements, the following internal modules depend on each other:

- **WikiGenerator** depends on **VectorStore**
- **VectorStore** depends on **EmbeddingModel**
- **EmbeddingModel** depends on **SentenceTransformer**
- **SentenceTransformer** depends on **lancedb**
- **WikiGenerator** depends on **CodeParser**
- **CodeParser** depends on **tree_sitter**
- **CodeParser** depends on **tree_sitter_c**
- **CodeParser** depends on **tree_sitter_cpp**
- **CodeParser** depends on **tree_sitter_go**
- **CodeParser** depends on **tree_sitter_java**
- **CodeParser** depends on **tree_sitter_javascript**
- **CodeParser** depends on **tree_sitter_python**
- **CodeParser** depends on **tree_sitter_rust**
- **CodeParser** depends on **tree_sitter_swift**
- **CodeParser** depends on **tree_sitter_typescript**
- **WikiGenerator** depends on **MarkdownRenderer**
- **MarkdownRenderer** depends on **markdown**
- **WikiGenerator** depends on **ConfigManager**
- **ConfigManager** depends on **pyyaml**
- **WikiGenerator** depends on **Logger**
- **Logger** depends on **rich**
- **WikiGenerator** depends on **FileWatcher**
- **FileWatcher** depends on **watchdog**