# Dependencies Overview

## External Dependencies

| Dependency                | Purpose |
|---------------------------|---------|
| `anthropic`               | Provides access to Anthropic's AI models, such as Claude, for natural language processing tasks. |
| `flask`                   | A lightweight WSGI web application framework used for building web interfaces or APIs. |
| `LanceDB`                 | A vector database for building AI-powered applications, used for storing and querying embeddings. |
| `markdown`                | Library for parsing and rendering Markdown text into HTML. |
| `mcp`                     | Used for managing model communication protocol (MCP) in AI applications. |
| `nh3`                     | A fast, safe HTML sanitization library to prevent XSS attacks. |
| `ollama`                  | Provides access to locally hosted large language models via Ollama API. |
| `openai`                  | Official Python client for OpenAI's API, used for interacting with GPT models. |
| `pandas`                  | Data manipulation and analysis library, used for handling structured data. |
| `psutil`                  | System and process utilities for monitoring system resources and performance. |
| `pydantic`                | Data validation and settings management using Python type annotations. |
| `pyyaml`                  | YAML parser and emitter for configuration files and data serialization. |
| `rapidfuzz`               | Fast fuzzy string matching library for similarity comparisons. |
| `rich`                    | Library for rich text and beautiful formatting in the terminal. |
| `sentence-transformers`   | Provides pre-trained models for generating sentence embeddings. |
| `tree-sitter`             | A parser generator tool and an incremental parsing library for syntax tree construction. |
| `tree-sitter-c`           | Tree-sitter grammar for C language. |
| `tree-sitter-c-sharp`     | Tree-sitter grammar for C# language. |
| `tree-sitter-cpp`         | Tree-sitter grammar for C++ language. |
| `tree-sitter-go`          | Tree-sitter grammar for Go language. |
| `tree-sitter-java`        | Tree-sitter grammar for Java language. |
| `tree-sitter-javascript`  | Tree-sitter grammar for JavaScript language. |
| `tree-sitter-kotlin`      | Tree-sitter grammar for Kotlin language. |
| `tree-sitter-php`         | Tree-sitter grammar for PHP language. |
| `tree-sitter-python`      | Tree-sitter grammar for Python language. |
| `tree-sitter-ruby`        | Tree-sitter grammar for Ruby language. |
| `tree-sitter-rust`        | Tree-sitter grammar for Rust language. |
| `tree-sitter-swift`       | Tree-sitter grammar for Swift language. |
| `tree-sitter-typescript`  | Tree-sitter grammar for TypeScript language. |
| `watchdog`                | File system event monitoring library for watching file changes. |

## Dev Dependencies

| Dependency                | Purpose |
|---------------------------|---------|
| `black`                   | Code formatter to enforce consistent Python code style. |
| `isort`                   | Tool to sort and organize import statements. |
| `local-deepwiki ([all])`  | Development package for local deepwiki with all optional dependencies. |
| `mypy`                    | Static type checker for Python to catch type-related errors. |
| `pip-audit`               | Security audit tool for Python package dependencies. |
| `pre-commit`              | Framework for managing and maintaining pre-commit hooks. |
| `pypdf`                   | Library for working with PDF files. |
| `pytest`                  | Testing framework for Python. |
| `pytest-asyncio`          | Plugin for pytest to support asynchronous tests. |
| `types-Markdown`          | Type stubs for the `markdown` library. |
| `types-PyYAML`            | Type stubs for the `pyyaml` library. |
| `weasyprint`              | HTML to PDF converter used for report generation. |

## Internal Module Dependencies

- [`WikiGenerator`](files/src/local_deepwiki/generators/wiki/generator.md) depends on [`VectorStore`](files/src/local_deepwiki/core/vectorstore/store.md)
- [`VectorStore`](files/src/local_deepwiki/core/vectorstore/store.md) depends on [`SearchProfile`](files/src/local_deepwiki/core/vectorstore/schema.md)
- `SourceFormatter` depends on [`GitRepoInfo`](files/src/local_deepwiki/core/git_utils.md), [`ChunkType`](files/src/local_deepwiki/models/foundation.md), [`CodeChunk`](files/src/local_deepwiki/models/chunks.md)
- `SecurityAccessControl` depends on `ContextVar`, `Callable`, `StrEnum`, `TypeVar`, `asyncio`
- `CLI` depends on `Console`, `Table`, `argparse`, `yaml`, [`Config`](files/src/local_deepwiki/config/models.md), [`ParsingConfig`](files/src/local_deepwiki/config/models_wiki.md)
- `InitCLI` depends on `Console`, `Panel`, `Prompt`, `Table`, [`Config`](files/src/local_deepwiki/config/models.md), [`ParsingConfig`](files/src/local_deepwiki/config/models_wiki.md)
- `Analysis` modules depend on `Any`, `defaultdict`
- `DataParser` depends on `User`, `json`, `Path`
- `Processor` depends on `Order`, `User`
- `TestParser` depends on `User`, `DataParser`
- `WikiOutputHelpers` depends on `AsyncIterator`, `Path`, [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md), [`LLMProvider`](files/src/local_deepwiki/providers/base.md)
- `Logging` depends on `logging`, `os`, `sys`
- `Protocols` depends on `Iterator`, `Path`, `Protocol`, `runtime_checkable`
- `SessionState` depends on `Any`
- `HealthScoring` depends on `Any`
- `SmellsPage` depends on `Any`
- `TermValidator` depends on `re`
- `Credentials` depends on `os`
- `MainCLI` depends on `Console`, `Table`, `importlib`, `sys`
- `DirTree` depends on `Path`, `subprocess`
- `ProviderTypes` depends on `StrEnum`
- `Types` depends on `TypedDict`
- `GitBlame` depends on [`format_blame_date`](files/src/local_deepwiki/core/git_blame.md), [`get_file_entity_blame`](files/src/local_deepwiki/core/git_blame.md)
- `GitUtils` depends on [`build_source_url`](files/src/local_deepwiki/core/git_utils.md)
- `SearchTypes` depends on `dataclass`, [`SearchProfile`](files/src/local_deepwiki/core/vectorstore/schema.md)
- `Models` depends on `version` (from `importlib.metadata`)
- `External` depends on `Any`
- `Utils` depends on `hashlib`, `re`
- [`Config`](files/src/local_deepwiki/config/models.md) depends on `yaml`
- `ConfigModels` depends on [`ParsingConfig`](files/src/local_deepwiki/config/models_wiki.md)
- `BaseProvider` depends on [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md), [`LLMProvider`](files/src/local_deepwiki/providers/base.md)

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
