# Dependencies Overview

## External Dependencies

The following third-party libraries are required for the project:

- **anthropic** (>=0.40,<1.0.0)  
  Provides access to Anthropic's AI models, particularly Claude, for natural language processing tasks.

- **flask** (>=3.0,<4.0.0)  
  A lightweight web framework for building web applications and APIs.

- **LanceDB** (>=0.15,<1.0.0)  
  A vector database for storing and querying embeddings, used for semantic search and similarity retrieval.

- **markdown** (>=3.0,<4.0.0)  
  Library for parsing and rendering Markdown text into HTML.

- **mcp** (>=1.2.0,<2.0.0)  
  Likely used for managing model configuration or communication protocols, possibly related to LLM interactions.

- **nh3** (>=0.2.14,<1.0.0)  
  A fast, safe HTML sanitizer for cleaning and validating HTML content.

- **ollama** (>=0.4,<1.0.0)  
  Provides access to locally hosted LLMs via the Ollama API.

- **openai** (>=1.0,<2.0.0)  
  Official Python client for OpenAI's API, used for interacting with OpenAI models.

- **pandas** (>=2.0,<3.0.0)  
  Data manipulation and analysis library, used for handling structured data.

- **psutil** (>=5.0,<6.0.0)  
  Cross-platform library for retrieving system and process information.

- **pydantic** (>=2.0,<3.0.0)  
  Data validation and settings management using Python type annotations.

- **pyyaml** (>=6.0,<7.0.0)  
  YAML parser and emitter for configuration files and data serialization.

- **rapidfuzz** (>=3.0,<4.0.0)  
  Fast fuzzy string matching library, used for similarity and search operations.

- **rich** (>=13.0,<14.0.0)  
  Library for rich text and beautiful formatting in the terminal.

- **sentence-transformers** (>=3.0,<4.0.0)  
  Library for generating sentence embeddings for semantic similarity tasks.

- **tree-sitter** (>=0.23)  
  A parser for programming languages, used for code analysis and syntax parsing.

- **tree-sitter-c** (>=0.23)  
  Tree-sitter parser for C language.

- **tree-sitter-c-sharp** (>=0.23)  
  Tree-sitter parser for C# language.

- **tree-sitter-cpp** (>=0.23)  
  Tree-sitter parser for C++ language.

- **tree-sitter-go** (>=0.23)  
  Tree-sitter parser for Go language.

- **tree-sitter-java** (>=0.23)  
  Tree-sitter parser for Java language.

- **tree-sitter-javascript** (>=0.23)  
  Tree-sitter parser for JavaScript language.

- **tree-sitter-kotlin** (>=0.23)  
  Tree-sitter parser for Kotlin language.

- **tree-sitter-objc** (>=3.0)  
  Tree-sitter parser for Objective-C language.

- **tree-sitter-php** (>=0.23)  
  Tree-sitter parser for PHP language.

- **tree-sitter-python** (>=0.23)  
  Tree-sitter parser for Python language.

- **tree-sitter-ruby** (>=0.23)  
  Tree-sitter parser for Ruby language.

- **tree-sitter-rust** (>=0.23)  
  Tree-sitter parser for Rust language.

- **tree-sitter-swift** (>=0.0.1)  
  Tree-sitter parser for Swift language.

- **tree-sitter-typescript** (>=0.23)  
  Tree-sitter parser for TypeScript language.

## Dev Dependencies

The following dependencies are used for development and testing:

- **black** (>=24.0)  
  Code formatter for Python.

- **isort** (>=5.0)  
  Tool for sorting and organizing Python imports.

- **local-deepwiki ([all])**  
  Development package for the project itself, likely including all features.

- **mypy** (>=1.0)  
  Static type checker for Python.

- **pip-audit** (>=2.0)  
  Tool for auditing Python dependencies for security vulnerabilities.

- **pre-commit** (>=3.0)  
  Framework for managing pre-commit hooks.

- **pypdf** (>=6.6.1)  
  Library for working with PDF files.

- **pytest** (>=8.0)  
  Testing framework for Python.

- **pytest-asyncio** (>=0.24,<1.0.0)  
  [Plugin](files/src/local_deepwiki/plugins/base.md) for pytest to support asynchronous tests.

- **types-Markdown** (>=3.0)  
  Type stubs for the `markdown` library.

- **types-PyYAML** (>=6.0)  
  Type stubs for the `pyyaml` library.

- **weasyprint** (>=68.0,<69.0.0)  
  Library for rendering HTML and CSS to PDF.

## Internal Module Dependencies

Based on import statements, the following internal module dependencies exist:

- **CLI modules** (`src/local_deepwiki/cli/`) depend on:
  - `rich` for rich terminal output.
  - `yaml` for configuration file parsing.
  - `local_deepwiki.config` for configuration handling.
  - `local_deepwiki.config.models` for parsing configuration models.

- **Security modules** (`src/local_deepwiki/security/`) depend on:
  - `asyncio` for asynchronous operations.
  - `contextvars` for managing context.
  - `dataclasses` for structured data handling.
  - `enum` for defining string enums.
  - `typing` for type hints.

- **Logging module** (`src/local_deepwiki/logging.py`) depends on:
  - `logging` for logging utilities.
  - `os` and `sys` for system-level operations.

- **Core protocols** (`src/local_deepwiki/core/protocols.py`) depend on:
  - `pathlib` for path handling.
  - `typing` for type hints.

- **Generators** (`src/local_deepwiki/generators/`) depend on:
  - `collections.abc` for abstract base classes.
  - `dataclasses` for structured data.
  - `typing` for type hints.
  - `local_deepwiki.core.git_blame` and `local_deepwiki.core.git_utils` for Git-related utilities.
  - `local_deepwiki.logging` for logging.
  - `local_deepwiki.models` for data models.

- **Handlers** (`src/local_deepwiki/handlers/`) depend on:
  - `typing` for type hints.
  - `local_deepwiki.core.vectorstore` for vector store interactions.
  - `local_deepwiki.generators` for content generation.

- **Models** (`src/local_deepwiki/models/`) depend on:
  - `pydantic` for data validation.
  - `typing` for type hints.
  - `enum` for enum definitions.

- **Providers** (`src/local_deepwiki/providers/`) depend on:
  - `typing` for type hints.
  - `local_deepwiki.core.vectorstore` for vector store interactions.
  - `local_deepwiki.generators` for content generation.

- **Test helpers** (`tests/wiki_output_helpers.py`) depend on:
  - `collections.abc` for abstract base classes.
  - `pathlib` for path handling.
  - `typing` for type hints.
  - `local_deepwiki.providers.base` for base provider classes.

- **Test fixtures** (`tests/fixtures/sample_repo/`) depend on:
  - `json` for JSON handling.
  - `pathlib` for path handling.
  - `src.models` for data models.
  - `typing` for type hints.

- **Vector store modules** (`src/local_deepwiki/core/vectorstore/`) depend on:
  - `dataclasses` for structured data.
  - `typing` for type hints.
  - `local_deepwiki.core.vectorstore.schema` for schema definitions.

- **Configuration** (`src/local_deepwiki/config/`) depends on:
  - `yaml` for configuration file parsing.
  - `local_deepwiki.config.models` for configuration models.

- **Initialization CLI** (`src/local_deepwiki/cli/init_cli.py`) depends on:
  - `argparse` for command-line argument parsing.
  - `os` and `sys` for system-level operations.
  - `urllib.request` for URL handling.
  - `collections.Counter` for counting.
  - `dataclasses` for structured data.
  - `pathlib` for path handling.
  - `typing` for type hints.
  - `yaml` for configuration file parsing.
  - `rich` for rich terminal output.
  - `local_deepwiki.config` for configuration handling.
  - `local_deepwiki.config.models` for parsing configuration models.

- **Wiki generators** (`src/local_deepwiki/generators/wiki/`) depend on:
  - `collections` for data structures.
  - `re` for regular expressions.
  - `typing` for type hints.
  - `local_deepwiki.core.vectorstore` for vector store interactions.
  - `local_deepwiki.generators.analysis` for analysis generators.
  - `local_deepwiki.generators.dir_tree` for directory tree generation.
  - `local_deepwiki.generators.scm` for SCM-related generators.
  - `local_deepwiki.generators.utils` for utility functions.
  - `local_deepwiki.logging` for logging.
  - `local_deepwiki.models` for data models.

- **Analysis generators** (`src/local_deepwiki/generators/analysis/`) depend on:
  - `typing` for type hints.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.models` for data models.

- **SCM generators** (`src/local_deepwiki/generators/scm/`) depend on:
  - `typing` for type hints.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.models` for data models.

- **Utils** (`src/local_deepwiki/generators/utils/`) depend on:
  - `typing` for type hints.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.models` for data models.

- **Session state handler** (`src/local_deepwiki/handlers/session_state.py`) depends on:
  - `typing` for type hints.
  - `local_deepwiki.generators` for generator functionality.
  - `local_deepwiki.models` for data models.

- **Term validator** (`src/local_deepwiki/generators/wiki/term_validator.py`) depends on:
  - `re` for regular expressions.
  - `local_deepwiki.generators` for generator functionality.
  - `local_deepwiki.models` for data models.

- **Source formatter** (`src/local_deepwiki/generators/wiki/source_formatter.py`) depends on:
  - `collections.abc` for abstract base classes.
  - `dataclasses` for structured data.
  - `operator` for attribute access.
  - `pathlib` for path handling.
  - `local_deepwiki.core.git_blame` for Git blame utilities.
  - `local_deepwiki.core.git_utils` for Git utilities.
  - `local_deepwiki.logging` for logging.
  - `local_deepwiki.models` for data models.

- **Directory tree generator** (`src/local_deepwiki/generators/dir_tree.py`) depends on:
  - `dataclasses` for structured data.
  - `pathlib` for path handling.
  - `subprocess` for executing shell commands.
  - `local_deepwiki.generators` for generator functionality.
  - `local_deepwiki.models` for data models.

- **Search types** (`src/local_deepwiki/core/vectorstore/mixins/search_types.py`) depend on:
  - `dataclasses` for structured data.
  - `local_deepwiki.core.vectorstore.schema` for schema definitions.

- **Git blame utilities** (`src/local_deepwiki/core/git_blame.py`) depend on:
  - `datetime` for date handling.
  - `pathlib` for path handling.
  - `subprocess` for executing shell commands.
  - `local_deepwiki.core.git_utils` for Git utilities.

- **Git utilities** (`src/local_deepwiki/core/git_utils.py`) depend on:
  - `pathlib` for path handling.
  - `subprocess` for executing shell commands.
  - `local_deepwiki.core.git_blame` for Git blame utilities.

- **Init CLI** (`src/local_deepwiki/cli/init_cli.py`) depends on:
  - `argparse` for command-line argument parsing.
  - `os` and `sys` for system-level operations.
  - `urllib.request` for URL handling.
  - `collections.Counter` for counting.
  - `dataclasses` for structured data.
  - `pathlib` for path handling.
  - `typing` for type hints.
  - `yaml` for configuration file parsing.
  - `rich` for rich terminal output.
  - `local_deepwiki.config` for configuration handling.
  - `local_deepwiki.config.models` for parsing configuration models.

- **Wiki generator** (`src/local_deepwiki/generators/wiki/wiki_generator.py`) depends on:
  - `collections` for data structures.
  - `dataclasses` for structured data.
  - `pathlib` for path handling.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.generators.dir_tree` for directory tree generation.
  - `local_deepwiki.generators.scm` for SCM-related generators.
  - `local_deepwiki.generators.utils` for utility functions.
  - `local_deepwiki.generators.wiki` for wiki-specific generators.
  - `local_deepwiki.logging` for logging.
  - `local_deepwiki.models` for data models.

- **Base provider** (`src/local_deepwiki/providers/base.py`) depends on:
  - `typing` for type hints.
  - `local_deepwiki.models` for data models.

- **Credentials provider** (`src/local_deepwiki/providers/credentials.py`) depends on:
  - `os` for environment variables.

- **LLM provider** (`src/local_deepwiki/providers/llm.py`) depends on:
  - `local_deepwiki.providers.base` for base provider functionality.
  - `local_deepwiki.providers.credentials` for credential handling.
  - `local_deepwiki.models` for data models.

- **Embedding provider** (`src/local_deepwiki/providers/embedding.py`) depends on:
  - `local_deepwiki.providers.base` for base provider functionality.
  - `local_deepwiki.providers.credentials` for credential handling.
  - `local_deepwiki.models` for data models.

- **Vector store** (`src/local_deepwiki/core/vectorstore/vectorstore.py`) depends on:
  - `dataclasses` for structured data.
  - `typing` for type hints.
  - `local_deepwiki.core.vectorstore.mixins` for mixins.
  - `local_deepwiki.core.vectorstore.schema` for schema definitions.
  - `local_deepwiki.generators` for generator functionality.
  - `local_deepwiki.models` for data models.

- **Search profile** (`src/local_deepwiki/core/vectorstore/schema.py`) depends on:
  - `dataclasses` for structured data.
  - `typing` for type hints.
  - `local_deepwiki.models` for data models.

- **Code chunk model** (`src/local_deepwiki/models/code_chunk.py`) depends on:
  - `dataclasses` for structured data.
  - `typing` for type hints.
  - `local_deepwiki.models` for data models.

- **Chunk type enum** (`src/local_deepwiki/models/chunk_type.py`) depends on:
  - `enum` for enum definitions.
  - `typing` for type hints.

- **Provider types** (`src/local_deepwiki/models/provider_types.py`) depends on:
  - `enum` for enum definitions.
  - `typing` for type hints.

- **Types** (`src/local_deepwiki/handlers/types.py`) depends on:
  - `typing` for type hints.

- **Health scoring generator** (`src/local_deepwiki/generators/analysis/health_scoring.py`) depends on:
  - `typing` for type hints.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.models` for data models.

- **Architecture report generator** (`src/local_deepwiki/generators/analysis/architecture_report.py`) depends on:
  - `typing` for type hints.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.models` for data models.

- **Smells page generator** (`src/local_deepwiki/generators/analysis/smells_page.py`) depends on:
  - `collections` for data structures.
  - `typing` for type hints.
  - `local_deepwiki.generators` for base generator functionality.
  - `local_deepwiki.models` for data models.

## Module Dependency Graph

The following diagram shows module dependencies. Click on a module to view its documentation. External dependencies are shown with dashed borders.

```mermaid
flowchart TD
    subgraph cli[Cli]
        M0[init_cli]
        M1[main]
    end
    subgraph config[Config]
        M2[config]
        M3[models]
    end
    subgraph core[Core]
        M4[git_blame]
        M5[git_utils]
        M6[protocols]
        M7[search_types]
    end
    subgraph generators[Generators]
        M8[architecture_report]
        M9[health_scoring]
        M10[smells_page]
        M11[dir_tree]
        M12[source_formatter]
        M13[term_validator]
    end
    subgraph handlers[Handlers]
        M14[session_state]
        M15[types]
    end
    subgraph local_deepwiki[Local Deepwiki]
        M16[logging]
    end
    subgraph logging[Logging]
        M17[logging]
    end
    subgraph models[Models]
        M18[models]
        M19[provider_types]
    end
    subgraph providers[Providers]
        M20[credentials]
    end
    subgraph security[Security]
        M21[access_control]
    end
    subgraph external[External Dependencies]
        E0([typing]):::external
        E1([rich]):::external
        E2([collections]):::external
        E3([dataclasses]):::external
        E4([os]):::external
        E5([pathlib]):::external
        E6([sys]):::external
        E7([enum]):::external
        E8([re]):::external
        E9([importlib]):::external
    end
    M0 --> M2
    M0 --> M3
    M12 --> M4
    M12 --> M5
    M12 --> M17
    M12 --> M18
    M0 -.-> E2
    M0 -.-> E3
    M0 -.-> E4
    M0 -.-> E5
    M0 -.-> E1
    M0 -.-> E6
    M0 -.-> E0
    M1 -.-> E9
    M1 -.-> E1
    M1 -.-> E6
    M6 -.-> E2
    M6 -.-> E5
    M6 -.-> E0
    M7 -.-> E3
    M8 -.-> E0
    M9 -.-> E0
    M10 -.-> E2
    M11 -.-> E3
    M11 -.-> E5
    M12 -.-> E2
    M12 -.-> E3
    M12 -.-> E5
    M13 -.-> E8
    M14 -.-> E0
    M15 -.-> E0
    M16 -.-> E4
    M16 -.-> E6
    M16 -.-> E0
    M19 -.-> E7
    M20 -.-> E4
    M21 -.-> E2
    M21 -.-> E3
    M21 -.-> E7
    M21 -.-> E4
    M21 -.-> E0
    click M0 "files/src/local_deepwiki/cli/init_cli.md"
    click M1 "files/src/local_deepwiki/cli/main.md"
    click M2 "files/src/local_deepwiki/config.md"
    click M3 "files/src/local_deepwiki/config/models.md"
    click M4 "files/src/local_deepwiki/core/git_blame.md"
    click M5 "files/src/local_deepwiki/core/git_utils.md"
    click M6 "files/src/local_deepwiki/core/protocols.md"
    click M7 "files/src/local_deepwiki/core/vectorstore/mixins/search_types.md"
    click M8 "files/src/local_deepwiki/generators/analysis/architecture_report.md"
    click M9 "files/src/local_deepwiki/generators/analysis/health_scoring.md"
    click M10 "files/src/local_deepwiki/generators/analysis/smells_page.md"
    click M11 "files/src/local_deepwiki/generators/dir_tree.md"
    click M12 "files/src/local_deepwiki/generators/wiki/source_formatter.md"
    click M13 "files/src/local_deepwiki/generators/wiki/term_validator.md"
    click M14 "files/src/local_deepwiki/handlers/session_state.md"
    click M15 "files/src/local_deepwiki/handlers/types.md"
    click M16 "files/src/local_deepwiki/local_deepwiki/logging.md"
    click M17 "files/src/local_deepwiki/logging.md"
    click M18 "files/src/local_deepwiki/models.md"
    click M19 "files/src/local_deepwiki/models/provider_types.md"
    click M20 "files/src/local_deepwiki/providers/credentials.md"
    click M21 "files/src/local_deepwiki/security/access_control.md"
    classDef external fill:#2d2d3d,stroke:#666,stroke-dasharray: 5 5
```

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/providers/credentials.py:12-80`](files/src/local_deepwiki/providers/credentials.md)
- [`src/local_deepwiki/generators/wiki/term_validator.py:43-82`](files/src/local_deepwiki/generators/wiki/term_validator.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/generators/analysis/architecture_report.py:15-36`](files/src/local_deepwiki/generators/analysis/architecture_report.md)
- [`src/local_deepwiki/handlers/session_state.py:20-27`](files/src/local_deepwiki/handlers/session_state.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:29-34`](files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/generators/analysis/smells_page.py:25-31`](files/src/local_deepwiki/generators/analysis/smells_page.md)
- [`src/local_deepwiki/cli/main.py:57-90`](files/src/local_deepwiki/cli/main.md)
- [`src/local_deepwiki/models/provider_types.py:8-13`](files/src/local_deepwiki/models/provider_types.md)
- [`src/local_deepwiki/handlers/types.py:8-18`](files/src/local_deepwiki/handlers/types.md)


*Showing 10 of 17 source files.*
