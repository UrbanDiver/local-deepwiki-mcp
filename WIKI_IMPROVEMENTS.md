# Wiki Improvements Roadmap

This document tracks planned improvements to the Local DeepWiki documentation generator.

## Content Quality

### 1. Better API Reference
- [ ] Generate structured API docs with type signatures
- [ ] Extract parameters, return types from type hints
- [ ] Parse and display docstrings in a consistent format
- [ ] Show default values for optional parameters
- **Files**: `generators/wiki.py`, possibly new `generators/api_docs.py`

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

### 4. Search Index
- [ ] Generate `search.json` with page titles, headings, and content snippets
- [ ] Add client-side search to web UI (JavaScript fuzzy search)
- [ ] Index class names, function names, and key terms
- **Files**: `generators/wiki.py`, `web/app.py`, new JS in `web/static/`

### 5. Breadcrumb Navigation
- [ ] Add breadcrumb trail to each wiki page
- [ ] Show path like: Home > Modules > Core > Indexer
- [ ] Update web UI template to render breadcrumbs
- **Files**: `web/app.py`, templates

### 6. "See Also" Sections
- [ ] Analyze import relationships between files
- [ ] Suggest related pages based on shared dependencies
- [ ] Add "See Also" section at bottom of each page
- **Files**: `generators/wiki.py`

---

## Diagrams & Visualization

### 7. Call Graph Diagrams
- [ ] Parse function bodies to find function calls
- [ ] Generate Mermaid flowchart showing call relationships
- [ ] Add to file documentation pages
- **Files**: `core/parser.py`, `generators/diagrams.py`

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

### 10. Incremental Wiki Generation
- [ ] Track file hashes and only regenerate changed pages
- [ ] Store generation metadata (hash, timestamp) per page
- [ ] Skip unchanged files during wiki generation
- **Files**: `generators/wiki.py`, `models.py`

### 11. Better Cross-Link Detection
- [ ] Parse LLM output to find class names even in backticks
- [ ] Convert `` `ClassName` `` to `` [`ClassName`](path) ``
- [ ] Handle qualified names like `module.ClassName`
- **Files**: `generators/crosslinks.py`

### 12. Watch Mode
- [ ] Add file watcher using `watchdog` library
- [ ] Auto-trigger incremental reindex on file changes
- [ ] Auto-regenerate affected wiki pages
- [ ] Add `--watch` flag to CLI
- **Files**: `server.py`, new `watcher.py`

---

## Priority Suggestions

**Quick Wins** (1-2 hours each):
- #5 Breadcrumb Navigation
- #11 Better Cross-Link Detection

**Medium Effort** (half day each):
- #4 Search Index
- #6 "See Also" Sections
- #10 Incremental Wiki Generation

**Larger Features** (1+ day each):
- #1 Better API Reference
- #7 Call Graph Diagrams
- #12 Watch Mode

---

## Notes

- Current wiki generation uses Ollama (qwen3-coder:30b) by default
- Cross-linking was added in commit `f933c46`
- Web UI runs on Flask at port 8080
- All 52 tests currently pass
