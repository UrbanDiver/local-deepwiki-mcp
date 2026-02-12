# Contributing to Local DeepWiki

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/UrbanDiver/local-deepwiki-mcp.git
cd local-deepwiki-mcp

# Install dependencies (including dev extras)
uv sync --extra dev

# Run the test suite
uv run pytest tests/ -v
```

## Running Tests

```bash
# Full suite
uv run pytest tests/ -v

# Single file
uv run pytest tests/test_parser.py -v

# With coverage
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

## Submitting Changes

1. Fork the repository and create a feature branch.
2. Make your changes with tests.
3. Ensure all tests pass: `uv run pytest tests/ -v`
4. Format your code: `uv run black src/ tests/ && uv run isort src/ tests/`
5. Open a pull request with a clear description of what changed and why.

## Reporting Issues

Open an issue on GitHub with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant logs or error messages

## Project Structure

See `CLAUDE.md` for a detailed architecture overview including all modules, generators, and design decisions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
