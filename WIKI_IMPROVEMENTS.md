# Wiki Improvements Roadmap

This document tracks planned improvements to the Local DeepWiki documentation generator.

## Content Quality

### 1. Better API Reference ✅
- [x] Generate structured API docs with type signatures
- [x] Extract parameters, return types from type hints
- [x] Parse and display docstrings in a consistent format
- [x] Show default values for optional parameters
- **Files**: `generators/api_docs.py`, `generators/wiki.py`

### 2. Usage Examples from Tests
- [ ] Scan test files for usage patterns of documented classes/functions
- [ ] Extract relevant code snippets that demonstrate real usage
- [ ] Add "Examples from Tests" section to file documentation
- **Files**: `generators/wiki.py`, `core/parser.py`

### 3. Changelog/History Page
- [ ] Generate page showing recent git commits
- [ ] Group changes by file/module
- [ ] Link commits to affected documentation pages
- **Files**: New `generators/changelog.py`

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

### 9. Sequence Diagrams for Workflows
- [ ] Identify key workflows (indexing, wiki generation, search)
- [ ] Generate Mermaid sequence diagrams
- [ ] Add to architecture documentation
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
- All 205 tests currently pass
