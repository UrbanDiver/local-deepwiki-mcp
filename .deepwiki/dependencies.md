# Dependencies Overview

## External Dependencies

| Dependency                  | Purpose                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| `anthropic`                 | Provides access to Anthropic's AI models, used for language generation. |
| `flask`                     | Web framework for building the application's HTTP API.                  |
| `LanceDB`                   | Vector database for storing and querying embeddings.                    |
| `markdown`                  | Library for parsing and rendering Markdown text.                        |
| `mcp`                       | Multi-Client Protocol support for communication with LLMs.              |
| `nh3`                       | HTML sanitization library to clean user-provided content.               |
| `ollama`                    | Interface to Ollama's local LLM inference engine.                       |
| `openai`                    | Client for interacting with OpenAI's API.                               |
| `pandas`                    | Data manipulation and analysis library.                                 |
| `psutil`                    | System and process utilities for monitoring resource usage.             |
| `pydantic`                  | Data validation and settings management using Python type annotations.  |
| `pyyaml`                    | YAML parsing and emitting library.                                      |
| `rapidfuzz`                 | Fast fuzzy string matching for similarity comparisons.                  |
| `rich`                      | Library for rich text and beautiful formatting in the terminal.         |
| `sentence-transformers`     | Provides sentence and text embedding capabilities.                      |
| `tree-sitter`               | General-purpose parsing library for code syntax analysis.               |
| `tree-sitter-c`             | Tree-sitter grammar for C language.                                     |
| `tree-sitter-c-sharp`       | Tree-sitter grammar for C# language.                                    |
| `tree-sitter-cpp`           | Tree-sitter grammar for C++ language.                                   |
| `tree-sitter-go`            | Tree-sitter grammar for Go language.                                    |
| `tree-sitter-java`          | Tree-sitter grammar for Java language.                                  |
| `tree-sitter-javascript`    | Tree-sitter grammar for JavaScript language.                            |
| `tree-sitter-kotlin`        | Tree-sitter grammar for Kotlin language.                                |
| `tree-sitter-objc`          | Tree-sitter grammar for Objective-C language.                           |
| `tree-sitter-php`           | Tree-sitter grammar for PHP language.                                   |
| `tree-sitter-python`        | Tree-sitter grammar for Python language.                                |
| `tree-sitter-ruby`          | Tree-sitter grammar for Ruby language.                                  |
| `tree-sitter-rust`          | Tree-sitter grammar for Rust language.                                  |
| `tree-sitter-swift`         | Tree-sitter grammar for Swift language.                                 |
| `tree-sitter-typescript`    | Tree-sitter grammar for TypeScript language.                            |

## Dev Dependencies

| Dependency              | Purpose                                                      |
|-------------------------|--------------------------------------------------------------|
| `black`                 | Code formatter to enforce consistent Python style.           |
| `isort`                 | Tool to sort and organize Python imports.                    |
| `local-deepwiki`        | Development dependency for local package installation.       |
| `mypy`                  | Static type checker for Python.                              |
| `pip-audit`             | Security audit tool for Python dependencies.                 |
| `pre-commit`            | Framework for managing and maintaining pre-commit hooks.     |
| `pypdf`                 | Library for working with PDF files.                          |
| `pytest`                | Testing framework for Python.                                |
| `pytest-asyncio`        | Plugin for testing asynchronous code with pytest.            |
| `types-Markdown`        | Type stubs for the `markdown` library.                       |
| `types-PyYAML`          | Type stubs for the `pyyaml` library.                         |
| `weasyprint`            | Library for rendering HTML and CSS to PDF.                   |

## Internal Module Dependencies

- [`WikiGenerator`](files/src/local_deepwiki/generators/wiki/generator.md) depends on [`VectorStore`](files/src/local_deepwiki/core/vectorstore/store.md)
- [`VectorStore`](files/src/local_deepwiki/core/vectorstore/store.md) depends on [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md)
- [`LLMProvider`](files/src/local_deepwiki/providers/base.md) is used by [`WikiGenerator`](files/src/local_deepwiki/generators/wiki/generator.md) and [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md)
- [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md) is used by [`VectorStore`](files/src/local_deepwiki/core/vectorstore/store.md)
- `DataParser` depends on `User` model
- `User` model is imported by `DataParser` and `Order` model
- `Order` model is imported by `Processor`
- `Processor` depends on `User` and `Order` models
- [`WikiGenerator`](files/src/local_deepwiki/generators/wiki/generator.md) depends on `SourceFormatter`
- `SourceFormatter` depends on [`GitRepoInfo`](files/src/local_deepwiki/core/git_utils.md), [`build_source_url`](files/src/local_deepwiki/core/git_utils.md), [`format_blame_date`](files/src/local_deepwiki/core/git_blame.md), and [`get_file_entity_blame`](files/src/local_deepwiki/core/git_blame.md)
- `SecurityHandler` depends on `AccessControl`
- `AccessControl` depends on `ContextVar`, `Callable`, `StrEnum`, and `asyncio`
- `CLI` depends on `Console`, `Table`, `argparse`, `yaml`, and [`Config`](files/src/local_deepwiki/config/models.md)
- [`Config`](files/src/local_deepwiki/config/models.md) depends on [`ParsingConfig`](files/src/local_deepwiki/config/models_wiki.md)
- [`SearchProfile`](files/src/local_deepwiki/core/vectorstore/schema.md) is used by [`SearchMixin`](files/src/local_deepwiki/core/vectorstore/mixins/search.md)
- [`SearchMixin`](files/src/local_deepwiki/core/vectorstore/mixins/search.md) depends on [`SearchProfile`](files/src/local_deepwiki/core/vectorstore/schema.md)
- `ProviderTypes` depends on `StrEnum`
- `Types` depends on `TypedDict`
- `Logging` depends on `logging`, `os`, and `sys`
- `Protocols` depends on `Protocol`, `runtime_checkable`, and `Path`
- `WikiOutputHelpers` depends on `AsyncIterator`, `Path`, [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md), and [`LLMProvider`](files/src/local_deepwiki/providers/base.md)
- `InitCLI` depends on `Console`, `Panel`, `Prompt`, `Table`, [`Config`](files/src/local_deepwiki/config/models.md), [`ParsingConfig`](files/src/local_deepwiki/config/models_wiki.md), `argparse`, `os`, `sys`, `urllib.request`, `Counter`, `dataclass`, `Path`, `yaml`
- `Analysis` modules depend on `Any` and `defaultdict`
- `SessionState` depends on `Any`
- `HealthScoring` depends on `Any`
- `SmellsPage` depends on `Any`
- `Credentials` depends on `os`
- `TermValidator` depends on `re`
- `MainCLI` depends on `Console`, `Table`, `sys`, and `importlib`
- `InitCLI` depends on `Console`, `Panel`, `Prompt`, `Table`, [`Config`](files/src/local_deepwiki/config/models.md), [`ParsingConfig`](files/src/local_deepwiki/config/models_wiki.md), `argparse`, `os`, `sys`, `urllib.request`, `Counter`, `dataclass`, `Path`, `yaml`
- `__init__` depends on `version` from `importlib.metadata`
- `GitBlame` depends on [`format_blame_date`](files/src/local_deepwiki/core/git_blame.md) and [`get_file_entity_blame`](files/src/local_deepwiki/core/git_blame.md)
- `GitUtils` depends on [`GitRepoInfo`](files/src/local_deepwiki/core/git_utils.md) and [`build_source_url`](files/src/local_deepwiki/core/git_utils.md)

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
- [`src/local_deepwiki/generators/analysis/health_scoring.py:34-39`](files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/generators/analysis/smells_page.py:25-31`](files/src/local_deepwiki/generators/analysis/smells_page.md)
- [`src/local_deepwiki/cli/main.py:57-90`](files/src/local_deepwiki/cli/main.md)
- [`src/local_deepwiki/models/provider_types.py:8-13`](files/src/local_deepwiki/models/provider_types.md)
- [`src/local_deepwiki/handlers/types.py:8-18`](files/src/local_deepwiki/handlers/types.md)


*Showing 10 of 17 source files.*
