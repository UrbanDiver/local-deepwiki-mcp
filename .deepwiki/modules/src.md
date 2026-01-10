**Local DeepWiki**
====================

**Module Overview**
-------------------

The `src` module is the core of Local DeepWiki, a tool for generating documentation for Python projects. Its primary purpose is to provide a structured approach to documenting and indexing code modules.

### Purpose and Responsibilities

* Extracts information from source code files
* Creates code chunks and indexes them
* Generates diagrams and documentation for each module
* Supports multiple providers for language model-based functionality

### Key Classes and Functions

#### Code Chunk Management

* `_create_module_chunk`: Creates a chunk for the module/file overview. This method takes an AST root node, source bytes, programming language, and file path as input.

#### Diagram Generation

* `generate_architecture_diagram`: Generates a Mermaid architecture diagram from code chunks.
* `generate_modules_index`: Generates an index page for modules.

#### Providers

* `base`: A base class for all providers, providing basic functionality for embedding and linking to documentation.
	+ `EmbeddingProvider` and `LLMProvider`: Subclasses that provide specific implementations for embedding and linking to language models.
* `anthropic`: An LLM provider using Anthropic's AsyncAnthropic client.
* `ollama`: An LLM provider using Ollama's AsyncClient.

#### Models

* `CodeChunk`: Represents a code chunk, containing information about the file path, source code, and language.
* `IndexStatus`: Provides status information for the indexing process.

### Usage Examples

To use Local DeepWiki, follow these steps:

1. Initialize the project by running `python -m local_deepwiki.server`.
2. Create a new module or file in your project directory.
3. Run `python -m local_deepwiki.server --generate` to generate documentation and diagrams for the module.
4. Access the generated documentation at <http://localhost:8080>.

### Dependencies

* `local_deepwiki.providers.base`: Provides basic functionality for embedding and linking to documentation.
* `local_deepwiki.models`: Contains models for representing code chunks and index status.
* `mermaid`: A library for generating Mermaid diagrams.

Note: This documentation assumes you have a basic understanding of Python and documentation generation. For more information on specific classes, functions, or providers, please refer to their individual documentation pages.