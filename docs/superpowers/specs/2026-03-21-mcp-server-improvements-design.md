# MCP Server Improvements — Design Spec

## Problem Statement

The local-deepwiki MCP server provides architecture analysis tools, but firsthand usage reveals friction for both AI agents and human developers:

1. **AI agents** must make 5+ separate tool calls and manually synthesize results to produce an architecture report. Output overflow (97K chars) silently truncates critical data.
2. **Human developers** exploring a new codebase have no guided entry point — the wiki is comprehensive but there's no "start here" path.
3. **No longitudinal tracking** — a health grade snapshot has no context without trend data or comparison capability.

## Goals

- Make architecture analysis a single-tool-call experience for AI agents
- Provide guided onboarding for developers new to a codebase
- Enhance existing architecture comparison for PR review workflows
- Add trend tracking so health grades have historical context
- Ensure all tools produce output sized appropriately for their consumer

## Non-Goals

- Replacing external linters or type checkers
- Supporting non-Python languages for layer/coupling analysis (existing limitation)
- Real-time monitoring or alerting

## Tool Count Consideration

The server currently has ~50 registered MCP tools. This spec adds 4 new tools (`analyze_architecture`, `get_onboarding_guide`, `get_recommendations`, `get_architecture_trends`) and enhances 2 existing ones (`compare_architecture`, `get_file_context`). The existing `find_tools` meta-tool helps agents discover relevant tools. Where possible, new capabilities are added as parameters on existing tools rather than creating new ones (e.g., recommendations can be included in `analyze_architecture` output rather than requiring a separate call).

---

## Design

### Tier 1: Fix What's Broken

*High impact, low effort. No new tools — improvements to existing ones.*

#### 1.1 Output Overflow Protection

**Problem:** `get_cross_module_dependencies` returned 97K characters and was truncated. AI agents cannot process the result.

**Changes:**
- Standardize output control parameters across all tools that can produce large results:
  - `summary_only: bool` — returns counts and top-level aggregates only
  - `top_n: int` — limits ranked results (with sensible defaults so output stays under ~4K chars)
- Default `top_n` values tuned per tool so common-case output stays under 4K characters
- Tools that already have some of these parameters (`get_design_smells` has `summary_only` and `top_n`) serve as the reference pattern

**Note:** A `format: "narrative"` parameter was considered but rejected — the composite `analyze_architecture` tool (1.4) handles the narrative use case. Individual tools remain structured JSON.

**Affected tools:**
- `get_cross_module_dependencies` — add `summary_only`, `top_n`, default `top_n=20`
- `get_coupling_metrics` — add `summary_only`, default `top_n=20`
- `get_hotspots` — already has `top_n`, add `summary_only`
- `get_layer_dependencies` — add `summary_only`

**Acceptance criteria:**
- No tool returns more than 8K characters with default parameters
- All ranking tools have `top_n` with a default that produces <4K output
- `summary_only=true` produces <1K output for any tool

#### 1.2 Smarter Default Sorting

**Problem:** `get_coupling_metrics` top-15 returned all CLI leaf modules at distance 1.0 — technically correct but uninformative. Leaf modules with zero efferent coupling *should* have high distance; they're not actionable findings.

**Changes:**
- Filter out modules with `efferent_coupling == 0` (pure leaves) by default
- Add `include_leaves: bool = false` parameter to opt back in
- For hotspots, exclude `__init__.py` re-export modules by default (heuristic: `__init__.py` files where >80% of non-comment lines are import or `__all__` statements)

**Deferred:** Anomaly scoring (ranking modules by how far their coupling deviates from layer expectations) is a good idea but requires defining a layer-to-expected-coupling mapping (e.g., `core: expected_instability < 0.3`, `cli: expected_instability > 0.7`). This is deferred to a follow-up — leaf filtering alone solves the stated problem for now.

**Acceptance criteria:**
- Default coupling metrics output shows architecturally interesting modules, not leaf modules
- `include_leaves=true` restores current behavior

#### 1.3 Tool Consolidation

**Problem:** `get_architecture_summary` and `get_architecture_health` return ~80% overlapping data.

**Changes:**
- Deprecate `get_architecture_summary` (keep as alias for backward compatibility)
- Add `detail_level: "summary" | "standard" | "full"` to `get_architecture_health`:
  - `summary` (~1K chars): grade, dimension scores, top 3 findings per category
  - `standard` (~4K chars): current behavior — the default
  - `full` (~12K chars): all findings, complete smell list, full module metrics
- Merge the unique data from `get_architecture_summary` (file metrics, largest files) into the health check's `full` detail level

**Acceptance criteria:**
- `get_architecture_health(detail_level="summary")` returns <1K chars
- `get_architecture_summary` still works but delegates to health check internally

#### 1.4 Composite Analysis Tool

**Problem:** Producing a complete architecture report required 5 separate tool calls and manual synthesis.

**Changes:**
- New tool: `analyze_architecture`
- Internally orchestrates: health check + cross-module deps + smells + hotspots + layer analysis
- Returns a **pre-synthesized markdown report** with sections:
  1. Executive summary (grade, scale, one-line assessment)
  2. Strengths (what's working well — e.g., zero layer violations)
  3. Concerns (prioritized by severity, deduplicated)
  4. Dependency structure (key hubs, heaviest edges)
- Parameters:
  - `repo_path: str` (required)
  - `detail_level: "summary" | "standard" | "full"` — controls how many sub-analyses run
    - `summary`: health check + layer analysis only (~2K chars)
    - `standard`: all analyses, top-5 per category (~6K chars)
    - `full`: all analyses, top-10 per category, full dependency graph (~12K chars)
  - `focus: "all" | "complexity" | "coupling" | "smells"` — zoom into one dimension

**Note:** The recommendations section (see 2.2) is **not** included in Phase 1. It is added to the `analyze_architecture` output in Phase 2a when `get_recommendations` is implemented.

**Note:** Uses `detail_level` (not `depth`) to be consistent with 1.3 and to avoid conflict with graph-traversal `depth` parameters on tools like `generate_codemap`.

**Acceptance criteria:**
- Single tool call produces a complete, readable architecture report
- `standard` detail level output stays under 8K characters
- Report is useful as-is for both AI pass-through and human reading

---

### Tier 2: Targeted New Capabilities

*High impact, medium effort. New tools that fill clear gaps.*

#### 2.1 Codebase Onboarding Guide

**Problem:** A developer new to a codebase has no guided entry point. The wiki is comprehensive but where do you start?

**New tool:** `get_onboarding_guide`

**Output sections:**
1. **What this project does** — one-paragraph summary derived from manifest (pyproject.toml, package.json) + README
2. **Key entry points** — 3-5 files where execution begins (detected from call graph roots, CLI entry points, server/app setup files)
3. **Core abstractions** — the types/classes everything else depends on (highest afferent coupling in core/models layers)
4. **Main data flows** — 2-3 sentence descriptions of primary pipelines, derived from cross-module dependency graph and codemap analysis
5. **"Read these 5 files first"** — ranked by centrality (high afferent coupling) weighted toward shorter, more readable files
6. **Patterns and conventions** — detected from code analysis (e.g., "async throughout," "frozen pydantic models," "plugin system")

**Parameters:**
- `repo_path: str` (required)
- `audience: "developer" | "reviewer" | "user"` — adjusts content focus (not just verbosity, which is why this uses `audience` rather than `detail_level`)
  - `developer`: full technical detail, includes patterns and conventions (~6-8K chars)
  - `reviewer`: focuses on architecture, entry points, and data flows (~4K chars)
  - `user`: focuses on what the project does and how to use it (~2K chars)

**Surface through all entry points:**
- MCP tool for AI consumers
- `deepwiki onboard` CLI command (prints to terminal)
- "Getting Started" page auto-generated in web UI wiki

**Requires:** Indexed repository (uses call graph, coupling data, wiki content)

**Acceptance criteria:**
- Output is a coherent narrative, not a data dump
- Useful to someone with zero context about the project
- Under 8K characters for `developer` audience, under 4K for `reviewer`/`user`

#### 2.2 Prioritized Recommendations

**Problem:** Architecture health tells you *what's wrong* but not *what to fix first*.

**New tool:** `get_recommendations`

**Output:** Ordered list of up to 10 action items, each containing:
- `title: str` — e.g., "Extract helpers from generate_module_docs"
- `category: str` — "complexity" | "coupling" | "smells" | "structure"
- `effort: str` — "S" | "M" | "L"
- `impact: str` — "high" | "medium" | "low"
- `priority_score: float` — computed as `impact_weight / effort_weight` where effort: S=1, M=2, L=4 and impact: high=3, medium=2, low=1
- `affected_files: list[str]` — files that would change
- `description: str` — what to do and why
- `suggestion: str` — concrete refactoring hint

**Deduplication:** If 5 smells are in the same file, produce one recommendation ("refactor `modules.py`") with aggregated details, not 5 separate items.

**Parameters:**
- `repo_path: str` (required)
- `max_items: int = 10`
- `category_filter: str | None` — restrict to one category
- `min_impact: str = "medium"` — filter out low-impact items

**Integration:** Once implemented, recommendations are also included as section 5 in the `analyze_architecture` output (top 5 in `standard`, top 10 in `full`). Can still be called standalone for focused use.

**Acceptance criteria:**
- Recommendations are actionable (specific files, specific suggestions)
- Highest-ROI items appear first
- No duplicate recommendations for the same underlying issue

#### 2.3 Enhanced File Context

**Problem:** "I'm about to modify `indexer.py` — what do I need to know?" The existing `get_file_context` tool returns imports, callers, and related files, but misses smells, complexity data, test coverage, and recent git history.

**Enhancement to existing tool:** `get_file_context` (not a new tool — avoids creating the same overlap problem addressed in 1.3)

**New parameter:** `detail_level: "standard" | "full"`
- `standard` (default): current behavior — imports, callers, related files, type definitions
- `full`: adds the following sections to the response:
  - **Gotchas** — smells, complexity hotspots, or coupling anomalies in this file
  - **Related tests** — test files that cover this module (pattern-matched by filename and import analysis)
  - **Recent changes** — last 5 commits touching this file (from `git log`)
  - **Entity summary** — brief description from wiki/glossary if available

**Acceptance criteria:**
- `detail_level="standard"` returns identical output to current behavior (backward compatible)
- `detail_level="full"` responds in under 5 seconds with warm index
- `full` output under 8K characters

#### 2.4 Architecture Comparison Enhancements

**Enhancement to existing tool:** `compare_architecture` already exists in `generators/analysis/architecture_compare.py` with a handler, args model, and tool definition. It already uses git worktrees, computes deltas, and tracks new/resolved smells.

**Current behavior:** Accepts `repo_path`, `base_ref` (default `"HEAD~1"`), `head_ref` (default `"HEAD"`). Returns grade delta, dimension changes, new/resolved smells.

**Enhancements:**
- Add `detail_level: "summary" | "full"` parameter:
  - `summary` (~1K chars): grade delta + dimension score changes + verdict line only
  - `full` (default, current behavior): all existing output plus new sections below
- Add **coupling changes** section — modules whose instability/distance changed significantly between refs
- Add **verdict** line — "Architecture improved" / "Architecture degraded" / "No significant change" based on score delta thresholds (>+2 = improved, <-2 = degraded, else no significant change)
- Preserve existing `base_ref` default of `"HEAD~1"` (not changing to `"main"`)

**New surfaces (in addition to existing MCP tool):**
- `deepwiki compare [base_ref] [head_ref]` CLI command
- Web UI: comparison view accessible from architecture dashboard

**Acceptance criteria:**
- Existing tool behavior unchanged when new parameters are omitted
- `detail_level="summary"` output under 1K characters
- Verdict accurately reflects score direction

---

### Tier 3: Bigger Vision

*Transformative capabilities. Build on Tiers 1-2.*

#### 3.1 Trend Tracking

**Problem:** A health grade snapshot has no context. Is 76.5 improving or degrading?

**Changes:**
- Store health snapshots in `.deepwiki/health-history.jsonl` (one JSON object per line for concurrency safety — concurrent `deepwiki update` processes can safely append):
  ```json
  {"timestamp": "2026-03-21T14:30:00Z", "commit_sha": "abc123", "commit_message": "refactor: extract helpers", "overall_score": 76.5, "overall_grade": "B", "dimensions": {"complexity": 77.7, "coupling": 69.1, "smells": 63.5, "layers": 100.0}, "smell_count": 162}
  ```
- Auto-snapshot on `deepwiki update` and `index_repository`
- New tool: `get_architecture_trends`
  - Returns grade trajectory over last N snapshots
  - Per-dimension score trends
  - Smell count trend (adding vs resolving)
  - "Inflection points" — commits where grade changed by >3 points, with commit messages
- Parameters:
  - `repo_path: str` (required)
  - `last_n: int = 20` — number of snapshots
  - `since: str | None` — ISO date filter

**Surface through:**
- MCP tool
- `deepwiki trends` CLI command (ASCII sparkline chart)
- Web UI: trend charts on architecture dashboard

**Acceptance criteria:**
- Snapshots are lightweight (<1KB each) and append-only
- JSONL format handles concurrent appends safely
- Trend tool works even with only 1 snapshot (shows current state)
- Old snapshots auto-pruned after configurable retention (default: 100)

#### 3.2 CI Quality Gates

**Problem:** Architecture health is only checked manually. Regressions slip in unnoticed.

**New CLI command:** `deepwiki check`

**Behavior:**
- Runs architecture health check
- Compares against configurable thresholds in `pyproject.toml` (canonical location, version-controlled with the project):
  ```toml
  [tool.deepwiki.quality_gates]
  min_grade = "B"
  max_new_smells = 5
  block_on = ["god_class", "layer_violation"]

  [tool.deepwiki.quality_gates.dimensions]
  complexity = { min_score = 70 }
  coupling = { min_score = 60 }
  ```
- Configuration precedence: `pyproject.toml [tool.deepwiki]` > `~/.config/local-deepwiki/config.yaml` > defaults
- Exit code 0 (pass) or 1 (fail) or 2 (error) for CI integration
- Machine-readable output with `--json` flag
- Optional `--compare-base <ref>` flag runs architecture comparison (2.4) and fails on regression

**Optional integrations:**
- `--comment-pr` flag posts summary as PR comment (requires `GITHUB_TOKEN`)
- GitHub Actions compatible annotations output

**Acceptance criteria:**
- Works as a CI step with zero configuration (sensible defaults: min_grade=C, no block_on)
- Clear, actionable output on failure explaining what threshold was violated
- Exit codes follow CI conventions (0 = pass, 1 = fail, 2 = error)

#### 3.3 Interactive Architecture Dashboard (Web UI)

**Problem:** Web UI has wiki pages but no architecture-specific visualization.

**New route:** `/architecture` in web UI

**Tabs:**
1. **Overview** — health grade donut chart, dimension scores as gauges, trend sparklines (requires 3.1)
2. **Dependencies** — interactive module dependency graph using vis.js. Click node → see module detail. Edge thickness = import weight
3. **Hotspots** — treemap using Chart.js (treemap plugin) where rectangle size = line count, color intensity = cyclomatic complexity. Click → navigate to source
4. **Smells** — filterable, sortable table (vanilla JS). Filter by type, severity, file. Click → jump to source or wiki page

**Libraries:** vis.js for dependency graph, Chart.js with chartjs-chart-treemap plugin for hotspot visualization, vanilla JS for table filtering. No heavy frameworks.

**Data source:** Same analysis tools used by MCP, cached on `deepwiki update`

**Acceptance criteria:**
- Dashboard loads in <2 seconds with cached data
- All visualizations are interactive (click-to-drill-down)
- No build step required (CDN-loaded libraries or vendored)

#### 3.4 Guided Codebase Tours

**Status:** Aspirational — validate demand first. The onboarding guide (2.1) and existing `run_workflow("onboarding")` may satisfy the same need. Implement 2.1 first and assess whether users request step-by-step guided exploration on top of the narrative summary.

**Concept if validated:**
- Auto-generate tours from code analysis:
  1. **Request lifecycle** — trace a query from MCP tool call → handler → service → vectorstore → LLM → response (uses codemap BFS)
  2. **New contributor** — key abstractions, patterns, where to add features (from onboarding guide + health data)
  3. **Architecture** — layers, module boundaries, dependency flow (from layer analysis + cross-module deps)
- Each tour: a sequence of (wiki page | source file, line range) with LLM-generated narrative connecting steps
- Tour narrative generated during `deepwiki update`, cached as markdown in `.deepwiki/tours/`
- Regenerated on `deepwiki update` so tours stay current

**Surface through:**
- MCP tool: `get_tour(repo_path, tour_name)` — returns structured markdown
- CLI: `deepwiki tour <name>` — prints step-by-step with file excerpts
- Web UI: step-through interface with prev/next navigation, source code highlighting

**Acceptance criteria (if implemented):**
- Tours generated automatically from analysis data (no manual curation)
- Each tour has 5-10 steps
- Tour content updates when code changes

---

## New CLI Commands Summary

| Command | Phase | Description |
|---------|-------|-------------|
| `deepwiki onboard` | Phase 2a | Print codebase onboarding guide to terminal |
| `deepwiki compare [base] [head]` | Phase 2b | Compare architecture health between git refs |
| `deepwiki check` | Phase 3a | CI quality gate with exit codes |
| `deepwiki trends` | Phase 3a | ASCII trend chart of health grade over time |
| `deepwiki tour <name>` | Phase 3b | Step-through guided codebase tour (if validated) |

## Implementation Phases

| Phase | Items | Dependencies | Effort Estimate |
|-------|-------|-------------|-----------------|
| **Phase 1** | 1.1 Output overflow, 1.2 Smarter sorting, 1.3 Tool consolidation, 1.4 Composite analysis (without recommendations) | None | S-M per item |
| **Phase 2a** | 2.1 Onboarding guide, 2.2 Recommendations (+ integrate into 1.4) | Phase 1 (uses consolidated tools) | M per item |
| **Phase 2b** | 2.3 Enhanced file context, 2.4 Comparison enhancements | Phase 1 | M per item |
| **Phase 3a** | 3.1 Trend tracking, 3.2 CI quality gates | Phase 1, Phase 2.4 (for `--compare-base`) | M-L per item |
| **Phase 3b** | 3.3 Architecture dashboard, 3.4 Guided tours (if validated) | Phase 2a, Phase 3.1 | L per item |

## Housekeeping

- Update CLAUDE.md tool counts and architecture tables for new/modified tools after each phase
- Update tool descriptions to reflect new parameters
- Update `find_tools` keyword index for new tools

## Testing Strategy

- **Unit tests** for each new tool/parameter with mocked analysis backends
- **Integration tests** using the local-deepwiki repo itself as the test subject
- **Output size tests** — automated checks that default parameters produce output under size limits
- **Snapshot tests** for narrative output format stability
- **Backward compatibility tests** — existing tool calls without new parameters produce identical output
- **CLI tests** for new commands (`deepwiki onboard`, `deepwiki compare`, `deepwiki check`, `deepwiki trends`)

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Composite tool is slow (runs 5 analyses) | Cache sub-analysis results; `summary` detail level runs fewer analyses |
| Architecture comparison with worktrees is expensive | Already implemented and working; enhancements are additive |
| Trend data grows unbounded | Auto-prune after configurable retention; JSONL format ~1KB per snapshot |
| Narrative format is hard to maintain across changes | Snapshot tests for output format; narrative generation isolated in dedicated formatter functions |
| Concurrent writes to health history | JSONL append-only format is resilient to concurrent writes |
| Tours become stale between updates | Deferred pending demand validation; if built, warn on stale tours and auto-regenerate on `deepwiki update` |
