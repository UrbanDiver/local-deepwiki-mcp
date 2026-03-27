# Phase 3a: Health Trend Tracking + CI Quality Gates — Design Spec

## Goal

Add health snapshot storage with a `get_architecture_trends` MCP tool for viewing score history, and a `deepwiki check` CLI command for CI quality gates that fails builds when architecture metrics drop below configured thresholds.

## Constraints

- No new dependencies (JSONL storage, no SQLite/DB)
- Thresholds configured in `pyproject.toml` under `[tool.deepwiki.check]`, defaults to no thresholds (always passes)
- Snapshots saved on both `deepwiki check` and `deepwiki update`
- Snapshot failure is non-critical — never fails the parent operation
- Exit codes: 0 = pass, 1 = threshold violated, 2 = error
- Follow existing CLI pattern: lazy import via `SUBCOMMANDS` dict in `cli/main.py`

---

## 1. Health History Storage

### 1.1 Module: `core/health_history.py`

Append-only JSONL storage at `.deepwiki/health-history.jsonl`.

**Snapshot shape** (one JSON object per line):
```json
{
  "timestamp": "2026-03-27T14:30:00Z",
  "git_ref": "abc1234",
  "score": 61.4,
  "grade": "C",
  "dimensions": {
    "complexity": {"score": 77.5, "grade": "B"},
    "coupling": {"score": 44.4, "grade": "D"},
    "smells": {"score": 28.3, "grade": "F"},
    "layers": {"score": 100.0, "grade": "A"}
  }
}
```

**Functions:**

- `save_snapshot(wiki_path: Path, health_data: dict) -> None` — extracts overall score/grade and dimension scores from health data, appends one JSONL line. Gets git ref via `git rev-parse --short HEAD` (falls back to `"unknown"` if not a git repo). No-op if health_data is missing required fields.

- `load_snapshots(wiki_path: Path, *, since: str | None = None) -> list[dict]` — reads JSONL file, optionally filters by ISO timestamp. Returns list sorted by timestamp ascending. Returns empty list if file doesn't exist.

- `get_latest(wiki_path: Path) -> dict | None` — returns the most recent snapshot, or None if no history exists.

---

## 2. `deepwiki check` CLI

### 2.1 Module: `cli/check_cli.py`

**CLI interface:**
```bash
deepwiki check [repo_path]   # defaults to current directory
deepwiki check --json        # machine-readable output for CI parsing
```

**Config in `pyproject.toml`:**
```toml
[tool.deepwiki.check]
min_grade = "C"
min_score = 50
min_complexity = 40
min_coupling = 40
min_smells = 40
min_layers = 40
```

All thresholds are optional. Omitted thresholds are not checked. If no `[tool.deepwiki.check]` section exists, check always passes (exit 0) after printing the health report.

**Flow:**
1. Parse CLI args (repo_path, --json flag)
2. Resolve repo path (default: cwd)
3. Read thresholds from `pyproject.toml` `[tool.deepwiki.check]` section
4. Run `analyze_architecture_health(repo_path, project_name)`
5. Save snapshot via `save_snapshot(wiki_path, health_data)`
6. Compare overall grade and score + per-dimension scores against thresholds
7. Print rich table (or JSON) with pass/fail per dimension
8. Exit: 0 = all pass, 1 = threshold violated, 2 = error

**Terminal output:**
```
Architecture Health Check — myproject

Overall: C (61.4/100)

  Dimension    Score   Grade   Threshold   Status
  Complexity   77.5    B       40          PASS
  Coupling     44.4    D       40          PASS
  Smells       28.3    F       40          FAIL
  Layers       100.0   A       40          PASS

Result: FAIL (smells score 28.3 below threshold 40)
```

**JSON output (--json):**
```json
{
  "status": "fail",
  "overall": {"score": 61.4, "grade": "C"},
  "dimensions": {...},
  "violations": [
    {"dimension": "smells", "score": 28.3, "threshold": 40}
  ]
}
```

**Grade comparison:** Letter grades are compared ordinally: A > B > C > D > F. If `min_grade = "C"`, then grades D and F fail.

### 2.2 Registration

Add to `SUBCOMMANDS` in `cli/main.py`:
```python
"check": ("local_deepwiki.cli.check_cli", "main", "Run architecture quality gate"),
```

---

## 3. `get_architecture_trends` MCP Tool

### 3.1 Args Model

```python
class GetArchitectureTrendsArgs(BaseModel):
    repo_path: str = Field(max_length=4096, description="Path to the repository")
    since: str | None = Field(
        default=None,
        description="ISO date to filter from (e.g., '2026-03-01'). Default: last 30 days",
    )
```

### 3.2 Handler

Standard pattern. Resolves wiki path as `repo_path / ".deepwiki"`. If no wiki directory or no history file, returns success with empty snapshots and null summary.

Default `since`: 30 days before now if not specified.

### 3.3 Return Shape

```python
{
    "status": "success",
    "snapshots": [
        {"timestamp": "...", "git_ref": "...", "score": N, "grade": "X", "dimensions": {...}},
        ...
    ],
    "summary": {
        "snapshot_count": 15,
        "date_range": {"from": "2026-03-01", "to": "2026-03-27"},
        "score_change": 3.2,
        "current_grade": "C",
    },
    "tool": "get_architecture_trends",
}
```

If no snapshots: `{"status": "success", "snapshots": [], "summary": null}`.

### 3.4 Tool Definition

```python
Tool(
    name="get_architecture_trends",
    description=(
        "View architecture health score trends over time. Returns historical "
        "snapshots with overall and per-dimension scores. Snapshots are saved "
        "automatically by 'deepwiki check' and 'deepwiki update'. "
        "No prior indexing required (reads saved history)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the repository",
            },
            "since": {
                "type": "string",
                "description": "ISO date to filter from (default: last 30 days)",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
)
```

---

## 4. Auto-snapshot in `deepwiki update`

After wiki generation completes successfully in `cli/update_cli.py`, save a health snapshot:

```python
try:
    from local_deepwiki.core.health_history import save_snapshot
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )
    health = analyze_architecture_health(repo_path, project_name)
    save_snapshot(wiki_path, health)
except Exception:
    pass  # Non-critical — don't fail update if snapshot fails
```

Silent failure — snapshot is a side effect, not a reason to fail the update.

---

## 5. File Changes

### New Files

| File | Purpose |
|------|---------|
| `src/local_deepwiki/core/health_history.py` | `save_snapshot()`, `load_snapshots()`, `get_latest()` |
| `src/local_deepwiki/cli/check_cli.py` | `deepwiki check` CLI command |
| `tests/test_health_history.py` | Storage layer tests |
| `tests/test_check_cli.py` | CLI quality gate tests |
| `tests/test_architecture_trends.py` | MCP tool handler tests |

### Modified Files

| File | Change |
|------|--------|
| `cli/main.py` | Add `"check"` to SUBCOMMANDS |
| `cli/update_cli.py` | Add snapshot save after wiki generation |
| `models/tool_args.py` | Add `GetArchitectureTrendsArgs` |
| `models/__init__.py` | Export new args |
| `tool_defs/analysis.py` | Add `get_architecture_trends` tool definition |
| `handlers/analysis_architecture.py` | Add `handle_get_architecture_trends` |
| `handlers/analysis.py` | Export handler |
| `handlers/__init__.py` | Export handler |
| `handlers/agentic_data.py` | Add tool keywords |
| `server.py` | Register handler |
| `CLAUDE.md` | Update tool counts, add CLI command |

---

## 6. Testing Strategy

### Health History Tests (`test_health_history.py`)

**Storage tests:**
- `save_snapshot` creates JSONL file with correct shape
- `save_snapshot` appends (doesn't overwrite) on second call
- `save_snapshot` handles missing overall data gracefully (no-op)
- `load_snapshots` returns empty list when file doesn't exist
- `load_snapshots` returns all snapshots in chronological order
- `load_snapshots` with `since` filters correctly
- `get_latest` returns most recent snapshot
- `get_latest` returns None when no history

### Check CLI Tests (`test_check_cli.py`)

**CLI tests:**
- Exit 0 when all thresholds pass
- Exit 1 when overall grade below min_grade
- Exit 1 when dimension score below threshold
- Exit 0 when no `[tool.deepwiki.check]` config exists (no thresholds = pass)
- Exit 2 when repo path doesn't exist
- `--json` flag produces valid JSON output
- Snapshot is saved as side effect of check
- Grade comparison is ordinal (D < C, F < D)

### Trends MCP Tool Tests (`test_architecture_trends.py`)

**Handler tests:**
- Returns snapshots from history file
- `since` param filters correctly
- Returns empty snapshots + null summary when no history
- Returns error for missing repo
- Summary includes score_change calculation
- Default since = 30 days ago
