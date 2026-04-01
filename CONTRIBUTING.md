# Contributing to Local DeepWiki

Thanks for your interest in contributing! This guide covers setup, architecture, and how to submit changes.

## Development Setup

```bash
git clone https://github.com/UrbanDiver/local-deepwiki-mcp.git
cd local-deepwiki-mcp
uv sync --extra dev
uv run pytest tests/ -v
```

## Running Tests

```bash
uv run pytest tests/ -v                    # Full suite (~6,000 tests)
uv run pytest tests/test_parser.py -v      # Single file
uv run pytest tests/ --cov=src/local_deepwiki --cov-report=term-missing
```

## Code Style

- **Formatter**: Black (line length 100)
- **Import sorting**: isort (black profile)
- **Type checking**: mypy

```bash
uv run black src/ tests/
uv run isort src/ tests/
uv run mypy src/
```

## Architecture

```
src/local_deepwiki/
├── server.py              MCP server entry point, tool dispatch
├── config/                Configuration loading, models, profiles
├── core/                  Core engine
│   ├── parser/            Tree-sitter AST parsing (13 languages)
│   ├── chunker.py         AST-based semantic code chunking
│   ├── vectorstore/       LanceDB vector storage and search
│   ├── indexer.py         Orchestrates parsing → chunking → embedding → wiki
│   └── deep_research/     Multi-step reasoning pipeline
├── generators/            Content generation
│   ├── wiki/              LLM-powered markdown wiki generation
│   ├── codemap/           Cross-file execution-flow maps
│   ├── analysis/          Code analysis (complexity, coupling, smells, etc.)
│   ├── examples/          Test-based usage example extraction
│   └── diagrams/          Mermaid diagram generation
├── handlers/              MCP tool handler functions
├── providers/             Pluggable LLM and embedding backends
│   ├── llm/               Ollama, Anthropic, OpenAI providers
│   └── embeddings/        Local (sentence-transformers), OpenAI providers
├── web/                   Flask web UI (wiki browser, chat, codemap explorer)
├── export/                HTML and PDF export
├── cli/                   CLI subcommands (init, search, config, etc.)
├── models/                Pydantic data models
├── security/              RBAC, repository access control
├── plugins/               Plugin system (language parsers, generators, embeddings)
└── services/              Service layer (provider factory, query orchestration)
```

### Data Flow

1. **Indexing**: Files → Tree-sitter AST → Semantic chunks → Embeddings → LanceDB + LLM → Wiki markdown
2. **Query**: Question → Embedding → Vector search → Top-k chunks → LLM synthesis
3. **Deep Research**: Question → Sub-question decomposition → Parallel retrieval → Gap analysis → Synthesis
4. **Codemap**: Query → Vector search entry points → Cross-file BFS call graph → Mermaid diagram + LLM narrative

### Key Design Decisions

- **Async throughout** — all core operations use asyncio for concurrent LLM/embedding calls
- **Incremental indexing** — file hashes tracked in manifest; only changed files are re-processed
- **AST-aware chunking** — code splits at function/class boundaries, not arbitrary token limits
- **Frozen Pydantic config** — immutable configuration objects prevent accidental mutation
- **Provider abstraction** — LLM and embedding providers implement base classes; config-driven selection
- **Plugin system** — extensible parsers, generators, and embedding providers via registry

### Where to Add Code

| You want to... | Look at... |
|----------------|------------|
| Add an MCP tool | `tool_defs/` (definition) + `handlers/` (implementation) |
| Add a language | `core/parser/languages.py` + tree-sitter grammar |
| Add an LLM provider | `providers/llm/` — implement `LLMProvider` base class |
| Add an embedding provider | `providers/embeddings/` — implement `EmbeddingProvider` |
| Add a wiki generator | `generators/wiki/` or register a `WikiGeneratorPlugin` |
| Add a code analysis tool | `generators/analysis/` |
| Add a web route | `web/routes_*.py` — Flask blueprints |

## Submitting Changes

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Ensure all tests pass: `uv run pytest tests/ -v`
4. Format your code: `uv run black src/ tests/ && uv run isort src/ tests/`
5. Open a pull request with a clear description of what changed and why

## Reporting Issues

Open an issue on GitHub with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant logs or error messages

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
