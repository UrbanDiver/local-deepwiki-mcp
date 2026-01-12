# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

This project provides a local MCP server that enables private repository documentation with DeepWiki-style capabilities. It offers tools for parsing, chunking, and searching code documentation while supporting incremental wiki updates and cross-references. The system can be run as a web service or via command-line tools for continuous documentation monitoring.

## Key Features

- **Code parsing and documentation generation** - The `local_deepwiki.parser` module handles parsing source code files and generating documentation chunks
- **Incremental wiki updates** - The `local_deepwiki.incremental_wiki` module supports updating documentation incrementally as code changes occur
- **Cross-reference linking** - The `local_deepwiki.crosslinks` module enables creating links between related documentation sections
- **Search and retrieval** - The `local_deepwiki.search` module provides search capabilities for finding relevant documentation
- **File watching and monitoring** - The `local_deepwiki.watcher` module monitors file changes and triggers documentation updates automatically

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 11 more...

## Directory Structure

```
local-deepwiki-mcp/
├── src/
│   └── local_deepwiki/
├── tests/
│   ├── __init__.py
│   ├── test_api_docs.py
│   ├── test_callgraph.py
│   ├── test_chunker.py
│   ├── test_config.py
│   ├── test_crosslinks.py
│   ├── test_incremental_wiki.py
│   ├── test_manifest.py
│   ├── test_parser.py
│   ├── test_search.py
│   ├── test_see_also.py
│   ├── test_watcher.py
│   └── test_web.py
├── CLAUDE.md
├── README.md
├── WIKI_IMPROVEMENTS.md
├── pyproject.toml
└── uv.lock
```

## Quick Start

- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`