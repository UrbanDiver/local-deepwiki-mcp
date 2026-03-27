# Phase 2a: Onboarding Guide + Recommendations — Design Spec

## Goal

Add two new MCP tools that make architecture analysis actionable: `get_onboarding_guide` generates a "start here" narrative for developers new to a codebase, and `get_recommendations` turns health findings into prioritized refactoring suggestions. Template-based recommendations are also integrated into the existing `analyze_architecture` composite tool output.

## Scope Notes

This spec supersedes the parent spec's Sections 2.1 and 2.2 (`docs/superpowers/specs/2026-03-21-mcp-server-improvements-design.md`). Key simplifications from the parent spec:
- **Onboarding**: No indexing required (file-system scanning only, no call graph or wiki content). The parent spec's `audience` parameter is dropped — always targets developers. The richer indexed version can be added later.
- **Recommendations**: Uses `low/medium/high` for effort/impact (not S/M/L). The `min_impact` parameter from the parent spec is dropped — priority sorting makes it unnecessary.
- **CLI**: `deepwiki onboard` CLI command is deferred to a later phase. MCP tools first.

## Constraints

- No prior indexing required for either tool
- No LLM calls for default operation (template-based)
- Optional LLM enrichment only in standalone `get_recommendations` with `enrich=True`
- When `enrich=True` and no LLM provider is configured, fall back to template-only (no error)
- Follow existing patterns: Pydantic args → tool def → handler → generator pure function
- Recommendations in `analyze_architecture` are always template-only (fast)

---

## 1. `get_onboarding_guide` Tool

### 1.1 Generator: `generators/analysis/onboarding.py`

Pure function `generate_onboarding_guide(repo_path: Path, *, detail_level: str = "standard") -> dict[str, Any]` that scans the repository and returns structured data:

- **Project manifest**: name, version, tech stack, scripts (via `get_cached_manifest`)
- **Directory structure**: top-level layout with annotations
- **Entry points**: main files, CLI scripts, server files, `__main__.py`
- **Key modules**: 5-8 most important packages by file count and import frequency
- **Test layout**: test directory structure, framework detection from deps
- **Config files**: CI, linting, docker, etc.

Separate formatter `format_onboarding_guide(data: dict, *, detail_level: str = "standard") -> str` produces markdown with sections:

| Section | summary | standard | full |
|---------|---------|----------|------|
| Project Overview | Yes | Yes | Yes |
| Getting Started | Yes | Yes | Yes |
| Repository Layout | Top-level dirs only | Annotated tree | Annotated tree + file counts |
| Entry Points | — | Yes | Yes |
| Key Modules | — | Top 5 | Top 8 with descriptions |
| Testing | — | Yes | Yes + coverage info |
| Configuration | — | — | Yes |

### 1.2 Args Model

```python
class GetOnboardingGuideArgs(BaseModel):
    repo_path: str = Field(max_length=4096, description="Path to the repository")
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~1K), standard (~3K), full (~6K)",
    )
```

### 1.3 Handler

Standard pattern: validate args → resolve path → call generator → call formatter → return `make_tool_text_content`.

### 1.4 Tool Definition

```python
Tool(
    name="get_onboarding_guide",
    description=(
        "Generate a developer onboarding guide for a codebase. Returns a "
        "markdown narrative with project overview, getting started instructions, "
        "repository layout, entry points, key modules, and testing info. "
        "No prior indexing required."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the repository"},
            "detail_level": {
                "type": "string",
                "enum": ["summary", "standard", "full"],
                "description": "Output detail level (default: standard)",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
)
```

---

## 2. `get_recommendations` Tool

### 2.1 Generator: `generators/analysis/recommendations.py`

**Core function**: `generate_recommendations(repo_path: Path, *, health_data: dict | None = None, max_items: int = 10, category_filter: str | None = None) -> dict[str, Any]`

If `health_data` is None, calls `analyze_architecture_health()` internally. If provided (by the composite tool), reuses it.

**Template mapping** (`_RECOMMENDATION_TEMPLATES`):

| Finding Type | Category | Template Title | Effort | Impact |
|-------------|----------|---------------|--------|--------|
| God Class | smells | "Split {entity} into focused components" | medium | high |
| Long Method | complexity | "Extract helpers from {entity}" | low | high |
| Long Parameter List | smells | "Introduce parameter object for {entity}" | low | medium |
| Feature Envy | smells | "Move {entity} to the class it envies" | medium | medium |
| Large File | smells | "Split {file} into focused modules" | medium | high |
| Deep Nesting | complexity | "Flatten nesting in {entity}" | low | medium |
| High distance (D > 0.7) | coupling | "Reduce coupling in module {module}" | high | medium |
| Layer violation | layers | "Fix upward dependency: {source} → {target}" | low | high |
| Hotspot (CC > 15) | complexity | "Reduce complexity in {entity}" | medium | high |

**Priority scoring**: `priority = impact_weight * (1 / effort_weight)` where impact weights are high=3, medium=2, low=1 and effort weights are low=1, medium=2, high=3.

**Return shape**:
```python
{
    "status": "success",
    "recommendations": [
        {
            "title": "Extract helpers from _parse_node",
            "category": "complexity",
            "description": "Cyclomatic complexity 23, 145 lines. Extract branches...",
            "file": "src/core/parser.py",
            "line": 42,
            "effort": "low",
            "impact": "high",
            "priority": 3.0,
        },
        # ...
    ],
    "stats": {
        "total_findings": 47,
        "returned": 10,
        "category": "all",
    },
}
```

**LLM enrichment function**: `enrich_recommendations(recommendations: list[dict], llm_provider: LLMProvider) -> list[dict]`

Takes the template recommendations and passes them through the LLM to generate richer descriptions with specific refactoring steps. Called only by the standalone handler when `enrich=True`. Adds an `enriched_description` field to each recommendation without replacing the template description. The handler resolves the provider via `get_cached_llm_provider()` from `local_deepwiki.providers.llm`. If no LLM is configured, the handler silently falls back to template-only (no error).

### 2.2 Args Model

```python
class GetRecommendationsArgs(BaseModel):
    repo_path: str = Field(max_length=4096, description="Path to the repository")
    max_items: int = Field(
        default=10, ge=1, le=50,
        description="Maximum recommendations to return (1-50)",
    )
    category_filter: str | None = Field(
        default=None,
        description="Filter by category: complexity, coupling, smells, or layers",
    )
    enrich: bool = Field(
        default=False,
        description="Use LLM to generate richer descriptions (slower)",
    )
```

### 2.3 Handler

Standard pattern. When `enrich=True`, attempts to resolve LLM provider via `get_cached_llm_provider()` and calls `enrich_recommendations()`. If provider resolution fails (no API key configured), silently returns template-only results — no error.

### 2.4 Tool Definition

```python
Tool(
    name="get_recommendations",
    description=(
        "Generate prioritized refactoring recommendations from architecture "
        "health analysis. Returns actionable suggestions with effort/impact "
        "scoring. Set enrich=true for LLM-generated detailed descriptions. "
        "No prior indexing required."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the repository"},
            "max_items": {
                "type": "integer",
                "description": "Maximum recommendations (default: 10, max: 50)",
            },
            "category_filter": {
                "type": "string",
                "enum": ["complexity", "coupling", "smells", "layers"],
                "description": "Filter to a specific category (optional)",
            },
            "enrich": {
                "type": "boolean",
                "description": "Use LLM for richer descriptions (default: false)",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
)
```

---

## 3. Integration into `analyze_architecture`

### 3.1 Composite Orchestrator Changes

In `architecture_composite.py`, after running health analysis:

```python
# Generate template-only recommendations (no LLM)
recs_count = {"summary": 0, "standard": 5, "full": 10}.get(detail_level, 5)
recommendations = []
if recs_count > 0:
    from .recommendations import generate_recommendations
    recs_result = generate_recommendations(
        repo_path, health_data=health, max_items=recs_count,
    )
    recommendations = recs_result.get("recommendations", [])
```

Pass `recommendations` to the formatter.

### 3.2 Report Formatter Changes

In `architecture_report.py`, add `_format_recommendations(recommendations: list) -> str`:

```markdown
## Recommendations

1. **Extract helpers from `_parse_node`** (complexity, effort: low, impact: high)
   `src/core/parser.py:42` — CC=23, 145 lines
2. **Split `SearchEngine` class** (smells, effort: medium, impact: high)
   `src/core/search.py:1` — 18 methods, 650 lines
```

Called in `format_architecture_report()` after concerns, before dependency structure. Skipped when recommendations list is empty (summary detail level).

---

## 4. File Changes

### New Files

| File | Purpose |
|------|---------|
| `src/local_deepwiki/generators/analysis/onboarding.py` | `generate_onboarding_guide()` + `format_onboarding_guide()` |
| `src/local_deepwiki/generators/analysis/recommendations.py` | `generate_recommendations()` + `enrich_recommendations()` + templates |
| `tests/test_onboarding.py` | Onboarding generator + handler tests |
| `tests/test_recommendations.py` | Recommendations generator + handler tests |

### Modified Files

| File | Change |
|------|--------|
| `models/tool_args.py` | Add `GetOnboardingGuideArgs`, `GetRecommendationsArgs` |
| `models/__init__.py` | Export new args |
| `tool_defs/analysis.py` | Add tool definitions |
| `handlers/analysis_architecture.py` | Add `handle_get_onboarding_guide`, `handle_get_recommendations` |
| `handlers/analysis.py` | Export new handlers |
| `handlers/__init__.py` | Export new handlers |
| `handlers/agentic_data.py` | Add tool keywords |
| `server.py` | Register new handlers |
| `generators/analysis/architecture_composite.py` | Call `generate_recommendations()` |
| `generators/analysis/architecture_report.py` | Add `_format_recommendations()` |
| `CLAUDE.md` | Update tool counts and component tables |

---

## 5. Testing Strategy

### Onboarding Tests (`test_onboarding.py`)

**Generator tests:**
- Generator returns all expected sections for a synthetic repo
- `detail_level=summary` returns only overview + layout
- `detail_level=full` includes config files
- Entry point detection for common patterns (main.py, server.py, cli.py, `__main__.py`)
- Empty repo returns graceful minimal guide

**Handler tests:**
- Handler returns success with formatted markdown
- Missing repo returns error response
- Invalid `detail_level` falls back to standard (no crash)

### Recommendations Tests (`test_recommendations.py`)

**Generator tests:**
- God Class finding → generates "Split class" recommendation
- Long Method finding → generates "Extract helpers" recommendation
- Recommendations sorted by priority (high impact/low effort first)
- `max_items` limits output
- `category_filter` filters correctly
- `health_data` parameter reuses provided data (no re-analysis)
- Empty health data returns empty recommendations list

**LLM enrichment tests:**
- `enrich=True` with mocked LLM provider adds `enriched_description` field
- `enrich=True` with no LLM configured falls back to template-only (no error)

**Handler tests:**
- Handler returns success with recommendations list
- Missing repo returns error response
- `enrich=False` (default) does not call LLM

### Integration Tests
- `analyze_architecture` standard detail includes `## Recommendations` section
- `analyze_architecture` summary detail does NOT include recommendations
- `analyze_architecture` full detail includes up to 10 recommendations
- Output size stays under limits (existing `test_output_sizes.py`)
