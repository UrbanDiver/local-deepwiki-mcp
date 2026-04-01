# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- OpenAI-compatible proxy support via `base_url` config
- MCP server integration docs for Claude Code, Cursor, Windsurf, VS Code
- API key setup instructions and uv installation guide
- Architecture health trending and guided tours
- Interactive code references in chat responses
- Codemap wiki page generation

### Changed
- Default LLM provider changed from Ollama to OpenAI
- All LLM provider packages (openai, anthropic, ollama) and Flask are now core dependencies
- Removed backward-compatibility re-export shims across handlers, generators, and core modules
- Init wizard prioritizes cloud providers (OpenAI > Anthropic > Ollama)

### Fixed
- Wiki link checker handles bare-word targets and LLM hallucination patterns
- Codemap suggestions filter leaf nodes and trivial wrappers

## [0.1.0] - 2026-02-11

### Added
- **MCP Server** with 43 tools for repository documentation and code intelligence
- **Multi-language parsing** via tree-sitter (Python, TypeScript, JavaScript, Go, Rust, Java, C/C++, Swift, Ruby, PHP, Kotlin, C#)
- **AST-based chunking** that respects code structure (functions, classes, methods)
- **Semantic search** using LanceDB vector database
- **LLM-powered wiki generation** with support for Ollama (local), Anthropic, and OpenAI
- **Deep Research mode** with multi-step reasoning, query decomposition, and checkpointing
- **Incremental indexing** - only re-process changed files
- **RAG-based Q&A** for asking questions about codebases
- **Web UI** for browsing generated wiki with chat and research interfaces
- **Export to HTML/PDF** with mermaid diagram support
- **Codemap generation** - execution-flow maps with Mermaid diagrams and LLM narratives
- **Security features**:
  - RBAC with configurable enforcement modes
  - Secret detection before indexing
  - Path traversal prevention (6 layers)
  - Input validation with resource limits (CWE-400 prevention)
  - Audit logging
- **Plugin system** for custom language parsers, wiki generators, and embedding providers
- **Event system** with pub-sub lifecycle hooks

### Security
- Structured error system with `sanitize_error_message()` to prevent information leakage
- Repository access control with allowlist/denylist support
- Credential management without storing API keys in memory

[Unreleased]: https://github.com/UrbanDiver/local-deepwiki-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/UrbanDiver/local-deepwiki-mcp/releases/tag/v0.1.0
