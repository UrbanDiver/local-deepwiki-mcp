# CLAUDE.md

Project instructions for Claude Code.

## Commands

```bash
uv sync                                    # Install dependencies
uv run pytest tests/ -v                    # Run all tests
uv run pytest tests/test_parser.py -v      # Run a single test file
uv run pytest tests/test_parser.py::test_function_name -v  # Run a specific test
uv run black src/ tests/                   # Format code
uv run isort src/ tests/                   # Sort imports
uv run mypy src/                           # Type check
uv run local-deepwiki                      # Run the MCP server
uv run deepwiki update                     # Index repo and regenerate wiki
uv run deepwiki status                     # Show index health dashboard
uv run deepwiki check                      # Architecture quality gate
```

## Testing Notes

- Tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
- Most tests mock LLM/embedding providers to avoid external calls
- Shared `conftest.py` provides factory functions; test files are self-contained
- `pythonpath = ["tests"]` in pyproject.toml enables `from conftest import ...`

## Key Patterns

- **Async throughout**: All core operations use asyncio
- **Frozen Pydantic models**: Configuration objects are immutable
- **AST-aware chunking**: Code splits at function/class boundaries via tree-sitter
- **Config hierarchy**: CLI args > env vars > config file > defaults
- **Provider abstraction**: LLM and embedding providers implement base classes in `providers/base.py`

## Supported Languages

Python, TypeScript/TSX, JavaScript, Go, Rust, Java, C, C++, Swift, Ruby, PHP, Kotlin, C#
