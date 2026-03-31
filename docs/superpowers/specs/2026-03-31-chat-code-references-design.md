# Chat Code References — Interactive Links & Expandable Snippets

## Goal

Make code references in chat responses interactive: file paths become clickable wiki links, entity names link to glossary/entity pages, and file:line references get an expand button that shows the actual source code inline.

## Architecture

Three components, layered on top of the existing chat rendering pipeline:

1. **Post-processor (frontend JS)** — After `renderMarkdown()` produces HTML, a new `linkCodeReferences()` function scans the DOM for code references and transforms them into interactive elements. Runs once when each message is finalized (on `"done"` SSE event), not during streaming.

2. **Entity index (frontend data)** — On chat page load, fetch a lightweight index of known entities (function/class/method names → wiki page paths) from a new API endpoint. Used for matching bare entity names like `` `batch_embed` `` to their wiki pages.

3. **Code snippet API (backend)** — New endpoint `/api/code-snippet` that returns source code for a file:line range. Tries vector store chunks first (fast, already indexed), falls back to reading the file from disk.

## Component Design

### 1. Post-Processor: `linkCodeReferences(messageEl)`

Runs on the finalized `.message-content` DOM element after markdown rendering is complete. Does NOT run during token streaming (would cause flickering and break partial markdown).

**What it transforms:**

| Pattern | Example | Result |
|---------|---------|--------|
| File path in backticks | `` `src/core/indexer.py` `` | Link to `/wiki/files/src/core/indexer.py.md` |
| File path with lines | `` `src/core/indexer.py:527-607` `` or `src/core/indexer.py:527` | Link + expand button |
| File:line in parens | `(src/core/indexer.py:42-67)` | Link + expand button |
| Known entity name | `` `batch_embed` `` | Link to entity's wiki page |
| Unknown name in backticks | `` `asyncio` `` | Left as plain `<code>` (no link) |

**Detection strategy:**

1. Walk all `<code>` elements inside the message (excluding those inside `<pre>` blocks — those are fenced code blocks, not references).
2. For each `<code>` element, test its text content against patterns:
   - **File path regex:** `/^(src\/|tests\/|[\w-]+\/)[^\s]+\.(py|ts|js|go|rs|java|c|cpp|swift|rb|php|kt|cs)(:\d+(-\d+)?)?$/`
   - **Entity match:** Look up the text in the entity index (case-sensitive exact match on name)
3. Replace the `<code>` element with the appropriate interactive element.

**Link format:**
```html
<!-- File path link -->
<a href="/wiki/files/src/core/indexer.py.md" class="code-ref">
  <code>src/core/indexer.py</code>
</a>

<!-- File path with lines — link + expand toggle -->
<span class="code-ref-group">
  <a href="/wiki/files/src/core/indexer.py.md" class="code-ref">
    <code>src/core/indexer.py:527-607</code>
  </a>
  <button class="code-expand-btn" data-file="src/core/indexer.py" data-start="527" data-end="607"
          onclick="toggleCodeSnippet(this)" title="Show source code">▶</button>
</span>

<!-- Entity name link -->
<a href="/wiki/files/src/core/vectorstore/embedding.md#batch_embed" class="code-ref entity-ref">
  <code>batch_embed</code>
</a>
```

**Expand behavior:**
- Clicking the `▶` button fetches `/api/code-snippet?file=...&start=...&end=...`
- Inserts a `<div class="code-snippet">` immediately after the `<span class="code-ref-group">`
- Button changes to `▼` when open, `▶` when closed
- Snippet has a header bar with file:lines and an "Open in Wiki →" link
- Code is syntax-highlighted via highlight.js (already loaded on the page)
- Multiple snippets can be open simultaneously
- Clicking `▼` collapses (removes) the snippet div

### 2. Entity Index: `/api/entity-index`

Lightweight endpoint that returns a JSON map of entity names to their wiki page paths. Loaded once on chat page init, cached in a JS variable.

**Response format:**
```json
{
  "entities": {
    "batch_embed": {"page": "files/src/core/vectorstore/embedding.md", "type": "function"},
    "WikiGenerator": {"page": "files/src/generators/wiki/generator.md", "type": "class"},
    "SearchRequest": {"page": "files/src/core/vectorstore/mixins/search_types.md", "type": "class"}
  }
}
```

**Source:** Built from the existing search index (`search.json`) which already contains entity entries with page paths. The endpoint reads `search.json` from the wiki directory and extracts the entity subset. No new indexing needed.

**Size consideration:** For this codebase (~7K entities), the JSON is ~200-400KB. Acceptable for a one-time page load. If needed later, could filter to top entities by score or add a search-as-you-type approach instead.

### 3. Code Snippet API: `GET /api/code-snippet`

**Parameters:**
- `file` (required) — Relative file path (e.g., `src/local_deepwiki/core/indexer.py`)
- `start` (optional) — Start line number
- `end` (optional) — End line number

**Response:**
```json
{
  "file": "src/local_deepwiki/core/indexer.py",
  "start": 527,
  "end": 607,
  "language": "python",
  "content": "async def index(self, ...):\n    ...",
  "source": "chunk" | "file"
}
```

**Resolution strategy:**
1. Check vector store for a chunk matching the file path and overlapping the line range. If found and the chunk covers the requested range, return chunk content.
2. If no chunk match (or chunk doesn't cover the range), read the file from disk using the repository path from the wiki config. Extract the requested line range.
3. If both fail, return 404.

**Security:** Validate that the file path is within the indexed repository (reuse existing `validate_file_in_repo` from `core/path_utils.py`). Reject path traversal attempts.

## Styling

```css
/* Links for code references */
.code-ref {
  color: var(--link-color);
  text-decoration: none;
  border-bottom: 1px dashed var(--link-color);
  cursor: pointer;
}
.code-ref:hover {
  border-bottom-style: solid;
}
.code-ref code {
  background: var(--code-bg);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.9em;
}

/* Entity name links — slightly different style */
.entity-ref {
  border-bottom: 1px dotted var(--link-color);
}

/* Expand button */
.code-ref-group {
  display: inline;
}
.code-expand-btn {
  background: none;
  border: none;
  color: var(--muted-color);
  cursor: pointer;
  font-size: 10px;
  padding: 0 4px;
  vertical-align: middle;
  opacity: 0.6;
}
.code-expand-btn:hover {
  opacity: 1;
}

/* Expanded code snippet */
.code-snippet {
  background: var(--code-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  margin: 4px 0 12px;
  overflow: hidden;
}
.code-snippet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: var(--hover-bg);
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--muted-color);
}
.code-snippet-header a {
  color: var(--link-color);
  text-decoration: none;
  font-size: 11px;
}
.code-snippet pre {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
}
```

## Error Handling

- **Entity index fails to load:** Degrade gracefully — file path links still work, entity name linking is skipped.
- **Code snippet fetch fails:** Show inline error message "Could not load source code" in the snippet area, with the wiki link still functional.
- **File not in repo:** 404 from API, snippet shows "File not found in repository."
- **Chunk doesn't cover range:** Falls back to file read silently.

## Testing

- **Unit tests** for the regex patterns (file path detection, line range parsing)
- **Unit tests** for the entity index endpoint (correct format, handles missing search.json)
- **Unit tests** for the code snippet endpoint (chunk hit, file fallback, 404, path traversal rejection)
- **Integration test** for the post-processor (mock DOM with various code reference patterns, verify correct link generation)

## Files to Create/Modify

| File | Change |
|------|--------|
| `src/local_deepwiki/web/templates/chat.html` | Add `linkCodeReferences()` JS function, CSS styles, entity index fetch on load |
| `src/local_deepwiki/web/routes_chat.py` | Add `/api/entity-index` and `/api/code-snippet` endpoints |
| `tests/test_chat_code_refs.py` | Create — tests for API endpoints and link detection |
