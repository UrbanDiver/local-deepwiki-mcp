# Wiki Improvements Roadmap

This document tracks planned improvements to the Local DeepWiki documentation generator.

## Content Quality

### 1. Better API Reference ✅
- [x] Generate structured API docs with type signatures
- [x] Extract parameters, return types from type hints
- [x] Parse and display docstrings in a consistent format
- [x] Show default values for optional parameters
- **Files**: `generators/api_docs.py`, `generators/wiki.py`

### 2. Usage Examples from Tests ✅
- [x] Scan test files for usage patterns of documented classes/functions
- [x] Extract relevant code snippets that demonstrate real usage
- [x] Add "Usage Examples" section to file documentation
- **Files**: `generators/test_examples.py`, `generators/wiki.py`

### 3. Changelog/History Page ✅
- [x] Generate page showing recent git commits
- [x] Group commits by date with file changes
- [x] Link commits to GitHub/GitLab
- **Files**: `generators/changelog.py`, `generators/wiki.py`

---

## Navigation & Discovery

### 4. Search Index ✅
- [x] Generate `search.json` with page titles, headings, and content snippets
- [x] Add client-side search to web UI (JavaScript fuzzy search)
- [x] Index class names, function names, and key terms
- **Files**: `generators/search.py`, `generators/wiki.py`, `web/app.py`

### 5. Breadcrumb Navigation ✅
- [x] Add breadcrumb trail to each wiki page
- [x] Show path like: Home › Modules › Core › Indexer
- [x] Update web UI template to render breadcrumbs
- [x] Links to index.md when folder has one, plain text otherwise
- **Files**: `web/app.py`

### 6. "See Also" Sections ✅
- [x] Analyze import relationships between files
- [x] Suggest related pages based on shared dependencies
- [x] Add "See Also" section at bottom of each page
- **Files**: `generators/see_also.py`, `generators/wiki.py`

---

## Diagrams & Visualization

### 7. Call Graph Diagrams ✅
- [x] Parse function bodies to find function calls
- [x] Generate Mermaid flowchart showing call relationships
- [x] Add to file documentation pages
- **Files**: `generators/callgraph.py`, `generators/wiki.py`

### 8. Enhanced Import/Dependency Graphs
- [ ] Improve existing dependency graph with better layout
- [ ] Add interactive SVG or clickable links in Mermaid
- [ ] Show external vs internal dependencies differently
- **Files**: `generators/diagrams.py`

### 9. Sequence Diagrams for Workflows ✅
- [x] Identify key workflows (indexing, wiki generation, deep research)
- [x] Generate Mermaid sequence diagrams
- [x] Add to architecture documentation
- **Files**: `generators/diagrams.py`, `generators/wiki.py`

---

## Technical Improvements

### 10. Incremental Wiki Generation ✅
- [x] Track file hashes and only regenerate changed pages
- [x] Store generation metadata (hash, timestamp) per page
- [x] Skip unchanged files during wiki generation
- **Files**: `generators/wiki.py`, `models.py`

### 11. Better Cross-Link Detection ✅
- [x] Parse LLM output to find class names even in backticks
- [x] Convert `` `ClassName` `` to `` [`ClassName`](path) ``
- [x] Handle qualified names like `module.ClassName`
- **Files**: `generators/crosslinks.py`

### 12. Watch Mode ✅
- [x] Add file watcher using `watchdog` library
- [x] Auto-trigger incremental reindex on file changes
- [x] Auto-regenerate affected wiki pages
- [x] Add `deepwiki-watch` CLI command
- **Files**: `watcher.py`, `pyproject.toml`

---

## New Features

### 13. Conversational Mode ✅
- [x] Add chat interface to web UI for interactive Q&A
- [x] Use `deep_research` pipeline behind the scenes
- [x] Maintain conversation history for follow-up questions
- [x] Support streaming responses for real-time feedback
- **Files**: `web/app.py`, `web/templates/chat.html`

### 14. GitHub/GitLab Links ✅
- [x] Detect remote origin URL from git config
- [x] Convert source references to clickable GitHub/GitLab URLs
- [x] Support branch-specific links for reproducibility
- **Files**: `core/git_utils.py`, `generators/source_refs.py`, `generators/wiki.py`

### 15. Multi-Repository Support
- [ ] Index and cross-reference multiple related repositories
- [ ] Generate unified search across repos
- [ ] Show cross-repo dependencies and relationships
- **Files**: `core/indexer.py`, `server.py`

---

## Performance & Quality

### 16. Streaming Deep Research ✅
- [x] Stream `deep_research` output for better UX on long queries
- [x] Show progress for each research step in real-time
- [x] Support cancellation of in-progress research
- **Files**: `core/deep_research.py`, `server.py`

### 17. Provider-Specific Prompts
- [ ] Tune prompts for Anthropic vs Ollama vs OpenAI strengths
- [ ] Add prompt templates per provider in config
- [ ] Optimize token usage for each provider's pricing
- **Files**: `core/deep_research.py`, `generators/wiki.py`, `config.py`

### 18. Response Caching ✅
- [x] Cache LLM responses for repeated similar queries
- [x] Use embedding similarity to detect cache hits
- [x] Configurable cache TTL and size limits
- **Files**: `core/llm_cache.py`, `providers/llm/cached.py`, `server.py`

### 19. Configurable Deep Research ✅
- [x] Expose parameters in config.yaml (sub-question count, chunk limits, etc.)
- [x] Allow per-query overrides via MCP tool arguments (preset parameter)
- [x] Add presets for "quick" vs "thorough" research modes
- **Files**: `config.py`, `core/deep_research.py`, `server.py`

---

## Priority Suggestions

**Quick Wins** (1-2 hours each):
- ~~#5 Breadcrumb Navigation~~ ✅
- ~~#11 Better Cross-Link Detection~~ ✅

**Medium Effort** (half day each):
- ~~#4 Search Index~~ ✅
- ~~#6 "See Also" Sections~~ ✅
- ~~#10 Incremental Wiki Generation~~ ✅

**Larger Features** (1+ day each):
- ~~#1 Better API Reference~~ ✅
- ~~#7 Call Graph Diagrams~~ ✅
- ~~#12 Watch Mode~~ ✅

---

## Notes

- Current wiki generation uses Ollama (qwen3-coder:30b) by default
- Cross-linking was added in commit `f933c46`
- Web UI runs on Flask at port 8080
- All 603 tests currently pass
