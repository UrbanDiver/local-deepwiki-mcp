# Phase 3b: Architecture Dashboard + Guided Tours — Design Spec

## Goal

Add an interactive web-based architecture explorer at `/architecture` with a vis.js dependency graph, health stats footer, and module detail slide-out panel. Add a `get_guided_tour` MCP tool that generates topic-focused reading guides, with tours integrated into the web dashboard to highlight relevant modules on the graph.

## Constraints

- Flask blueprint pattern (matches chat, research, codemap)
- vis.js and Chart.js from CDN — no build step, no node_modules
- Vanilla JS in the template — no React/framework
- Tour generator is template-based by default, optional LLM enrichment
- Tours work both as standalone MCP tool output and as web UI feature
- No new Python dependencies

---

## 1. Architecture Dashboard

### 1.1 Blueprint: `web/routes_architecture.py`

Flask blueprint registered at `/architecture`. Serves the dashboard page and JSON API endpoints.

**Page route:**
- `GET /architecture` — renders `architecture.html` template

**API endpoints:**
- `GET /architecture/api/graph` — calls `analyze_cross_module_dependencies()`, returns nodes + edges formatted for vis.js
- `GET /architecture/api/health` — calls `analyze_architecture_health()`, returns overall grade, dimension scores, and trend sparkline data from `load_snapshots()`
- `GET /architecture/api/module/<name>` — calls `analyze_module_health()`, returns module detail for the slide-out panel
- `GET /architecture/api/tour/<topic>` — calls `generate_tour()`, returns stops with file-to-module mapping

API responses are JSON. All endpoints take `repo_path` as a query parameter.

### 1.2 Template: `templates/architecture.html`

Extends `base.html`. Loads vis.js and Chart.js from CDN.

**Layout** (graph-dominant, stats footer):
- **Graph area**: Full-width, ~85% viewport height. vis.js network renders module nodes and dependency edges.
- **Stats footer**: Compact bar at bottom with overall grade badge, module count, high-coupling count, smell count, and a Chart.js trend sparkline.
- **Slide-out panel**: Right-side panel (hidden by default) that slides in on node click or tour selection. Contains module detail view or tour stops view.

**Graph rendering:**
- Nodes = modules. Size proportional to file count. Color based on coupling distance: green (D < 0.3), yellow (0.3-0.7), red (D > 0.7).
- Edges = import dependencies. Thickness proportional to import weight. Directed arrows.
- Click a node → slide-out panel shows module detail (files, coupling metrics, smells, dependencies, dependents).
- Hover → tooltip with module name and file count.

**Stats footer:**
- Overall grade badge (colored A-F)
- Module count
- High-coupling count (D > 0.7)
- Smell count
- Trend sparkline (Chart.js line chart, last 30 days from health history)

**Slide-out panel (module detail mode):**
- Module name and file/line counts
- Coupling metrics (Ca, Ce, I, A, D)
- Smells in this module
- "Depends on" list (outgoing edges)
- "Depended on by" list (incoming edges)
- Close button to dismiss

**Slide-out panel (tour mode):**
- Tour title and topic
- Numbered list of stops
- Click a stop → graph highlights the relevant module node (pulsing border, zoom-to-fit), panel shows the stop's explanation
- Previous/Next navigation between stops

### 1.3 Graph Data Format

`/architecture/api/graph` returns:
```json
{
  "nodes": [
    {"id": "core", "label": "core", "file_count": 12, "line_count": 3200, "distance": 0.72, "color": "#f4a261"},
    ...
  ],
  "edges": [
    {"from": "handlers", "to": "core", "weight": 15, "label": "15"},
    ...
  ]
}
```

Node `color` is computed server-side based on coupling distance. Node `size` is computed client-side from `file_count`.

### 1.4 Health Data Format

`/architecture/api/health` returns:
```json
{
  "overall": {"score": 72.5, "grade": "B"},
  "dimensions": {
    "complexity": {"score": 77, "grade": "B"},
    "coupling": {"score": 44, "grade": "D"},
    "smells": {"score": 28, "grade": "F"},
    "layers": {"score": 100, "grade": "A"}
  },
  "stats": {"total_modules": 17, "high_coupling": 3, "total_smells": 5},
  "trend": [
    {"timestamp": "2026-03-01", "score": 60},
    {"timestamp": "2026-03-15", "score": 65},
    ...
  ]
}
```

---

## 2. Guided Tours MCP Tool

### 2.1 Generator: `generators/analysis/tours.py`

Pure function `generate_tour(repo_path: Path, *, topic: str = "architecture", max_stops: int = 10, enrich: bool = False) -> dict[str, Any]`.

**Topics** (auto-detected from repo structure):
- `"architecture"` — layers, module boundaries, key abstractions
- `"data_flow"` — entry → processing → storage pipeline
- `"request_handling"` — web request lifecycle (if web framework detected)
- `"testing"` — test organization, patterns, how to add tests
- `"custom:<query>"` — user provides free-text, tool identifies relevant files

**Tour generation logic:**
1. Resolve topic to a set of relevant file patterns and module names
2. Use manifest (entry points), directory structure, and import graph to identify relevant files
3. Order files by dependency flow (entry points first, then their dependencies)
4. Generate explanation for each stop using templates (file name patterns, function signatures, import context)
5. If `enrich=True`, pass through LLM for richer explanations

**Return shape:**
```python
{
    "status": "success",
    "topic": "data_flow",
    "title": "How Data Flows Through the System",
    "stops": [
        {
            "file": "src/server.py",
            "module": "server",
            "section": "TOOL_HANDLERS",
            "explanation": "Entry point: MCP requests arrive here and are dispatched to handlers.",
            "line": 96,
        },
        ...
    ],
    "summary": "The system follows a pipeline pattern...",
    "tool": "get_guided_tour",
}
```

**Topic detection heuristics:**
- `"data_flow"`: look for files matching `indexer`, `pipeline`, `processor`, `store`, `database`
- `"request_handling"`: look for `server`, `handler`, `route`, `app`, `middleware`
- `"testing"`: scan `tests/` structure, look for `conftest`, `fixtures`
- `"architecture"`: use layer analysis results, start with top-level modules

### 2.2 Args Model

```python
class GetGuidedTourArgs(BaseModel):
    repo_path: str = Field(max_length=4096, description="Path to the repository")
    topic: str = Field(
        default="architecture",
        description="Tour topic: architecture, data_flow, request_handling, testing, or custom:<query>",
    )
    max_stops: int = Field(
        default=10, ge=1, le=30,
        description="Maximum tour stops (1-30)",
    )
    enrich: bool = Field(
        default=False,
        description="Use LLM for richer explanations (slower)",
    )
```

### 2.3 Handler

Standard pattern. When `enrich=True`, resolves LLM via `get_llm_provider()` with graceful fallback to template-only (same pattern as `get_recommendations`).

### 2.4 Tool Definition

```python
Tool(
    name="get_guided_tour",
    description=(
        "Generate a guided tour of a codebase organized by topic. Returns an "
        "ordered list of file stops with explanations. Topics: architecture, "
        "data_flow, request_handling, testing, or custom:<query>. "
        "No prior indexing required."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the repository",
            },
            "topic": {
                "type": "string",
                "description": "Tour topic (default: architecture)",
            },
            "max_stops": {
                "type": "integer",
                "description": "Maximum stops (default: 10, max: 30)",
            },
            "enrich": {
                "type": "boolean",
                "description": "Use LLM for richer explanations (default: false)",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
)
```

---

## 3. Tours in the Web UI

Tours integrate into the existing dashboard via the slide-out panel.

**"Tours" button** in the stats footer opens the panel in tour-list mode, showing available topics.

**Tour flow:**
1. User clicks "Tours" → panel shows topic list (architecture, data_flow, etc.)
2. User clicks a topic → API call to `/architecture/api/tour/<topic>`
3. Panel switches to tour-stops view with numbered list
4. Clicking a stop highlights the relevant module node on the graph (pulsing CSS animation + zoom-to-fit via vis.js `network.focus()`)
5. Previous/Next buttons navigate between stops
6. Connected edges from the highlighted module are emphasized

**Module-to-file mapping:** Each tour stop has a `module` field that maps to a graph node. The frontend uses this to find and highlight the correct node.

---

## 4. File Changes

### New Files

| File | Purpose |
|------|---------|
| `src/local_deepwiki/web/routes_architecture.py` | Flask blueprint: page route + JSON API endpoints |
| `src/local_deepwiki/web/templates/architecture.html` | Dashboard template with vis.js graph, footer, panel |
| `src/local_deepwiki/generators/analysis/tours.py` | `generate_tour()` + topic heuristics + stop ordering |
| `tests/test_routes_architecture.py` | Blueprint and API endpoint tests |
| `tests/test_tours.py` | Tour generator tests |

### Modified Files

| File | Change |
|------|--------|
| `web/app.py` | Register architecture blueprint |
| `models/tool_args.py` | Add `GetGuidedTourArgs` |
| `models/__init__.py` | Export new args |
| `tool_defs/analysis.py` | Add `get_guided_tour` tool definition |
| `handlers/analysis_architecture.py` | Add `handle_get_guided_tour` |
| `handlers/analysis.py` | Export handler |
| `handlers/__init__.py` | Export handler |
| `handlers/agentic_data.py` | Add tool keywords |
| `server.py` | Register handler |
| `CLAUDE.md` | Update tool counts, add `/architecture` route, CLI serving docs |

---

## 5. Testing Strategy

### Dashboard Tests (`test_routes_architecture.py`)

- Blueprint registers and serves `/architecture` page (200 status)
- `/architecture/api/graph` returns valid JSON with nodes and edges arrays
- `/architecture/api/health` returns overall grade and dimensions
- `/architecture/api/module/<name>` returns module health data
- `/architecture/api/tour/<topic>` returns tour stops
- Missing repo_path query param returns 400
- Non-existent repo returns error JSON

### Tour Generator Tests (`test_tours.py`)

- `generate_tour` with topic="architecture" returns stops ordered by dependency flow
- Each stop has file, module, section, explanation, line fields
- `max_stops` limits the number of stops
- Topic "testing" identifies test directory and conftest
- Topic "data_flow" identifies pipeline-related files
- Empty repo returns minimal tour with summary
- Unknown topic returns graceful fallback (general architecture tour)
- `enrich=True` with mocked LLM adds richer explanations

### Handler Tests
- Handler returns success with tour stops
- Missing repo returns error
- `enrich=True` with no LLM falls back gracefully
