# Phase 2b: Enhanced File Context + Compare Architecture — Design Spec

## Goal

Add `detail_level` parameter to `get_file_context` and `compare_architecture`, enriching the "full" mode with entity summaries, related tests, recent commits, coupling changes, smell diffs, and an architecture verdict.

## Constraints

- No new files — modifications to existing generators, handlers, models, and tool defs only
- No new dependencies
- Standard detail = current behavior (backward compatible)
- Full detail is opt-in and may be slower (extra git/analysis calls)
- Follow existing patterns for `detail_level` (same as `get_architecture_health`, `analyze_architecture`, `get_onboarding_guide`)

---

## 1. Enhanced `get_file_context`

### 1.1 Args Change

Add to `GetFileContextArgs`:
```python
detail_level: str = Field(
    default="standard",
    description="Output detail: standard (imports, callers, related files) or full (+ entities, tests, commits)",
)
```

### 1.2 Tool Definition Change

Add to `get_file_context` tool properties:
```python
"detail_level": {
    "type": "string",
    "enum": ["standard", "full"],
    "description": "Output detail: standard (default) or full (adds entities, related tests, recent commits)",
},
```

### 1.3 Handler Changes

In `handle_get_file_context` (in `handlers/analysis_metadata.py`), when `detail_level == "full"`, compute and add three extra sections to the response:

**`entities`**: List of functions/classes defined in the file with line numbers. Use tree-sitter parsing (existing `parser.py` infrastructure) to extract:
```python
[
    {"name": "MyClass", "type": "class", "line": 15},
    {"name": "my_function", "type": "function", "line": 42},
]
```

**`related_tests`**: Test files that import from this module. Scan files in `tests/` directory for import statements matching the file's module path:
```python
["tests/test_server.py", "tests/test_handlers.py"]
```

**`recent_commits`**: Last 5 git commits touching this file via `git log --oneline -5 -- <file_path>`:
```python
[
    {"sha": "abc1234", "message": "fix: handle edge case in parser"},
    {"sha": "def5678", "message": "feat: add new parsing mode"},
]
```

All three are computed in private helper functions within the handler file (or a small utility), not in the existing `context_builder.py` generator — keeping the generator's interface unchanged.

Git operations use `subprocess.run` with timeout, falling back gracefully if not a git repo (empty list for commits).

### 1.4 Return Shape (full mode additions)

Standard response is unchanged. Full mode adds:
```python
{
    # ... existing fields (imports, callers, related_files) ...
    "entities": [{"name": "...", "type": "class|function", "line": N}],
    "related_tests": ["tests/test_foo.py"],
    "recent_commits": [{"sha": "...", "message": "..."}],
}
```

---

## 2. Enhanced `compare_architecture`

### 2.1 Args Change

Add to `CompareArchitectureArgs`:
```python
detail_level: str = Field(
    default="standard",
    description="Output detail: standard (scores + verdict) or full (+ coupling changes + smell diff)",
)
```

### 2.2 Tool Definition Change

Add to `compare_architecture` tool properties:
```python
"detail_level": {
    "type": "string",
    "enum": ["standard", "full"],
    "description": "Output detail: standard (default, scores + verdict) or full (adds coupling and smell diffs)",
},
```

### 2.3 Generator Changes

In `architecture_compare.py`:

**Verdict** (always computed, both detail levels): New `_compute_verdict()` helper that takes the deltas dict and returns:
```python
{
    "summary": "Architecture improved (+3.2)",
    "improved": ["complexity", "layers"],
    "degraded": ["coupling"],
    "unchanged": ["smells"],
}
```

Rules:
- Per-dimension: delta > +2 = improved, delta < -2 = degraded, else unchanged
- Overall summary: based on overall score delta with same ±2 threshold
- Summary text: "Architecture improved (+N.N)" / "Architecture degraded (N.N)" / "No significant change (±N.N)"

**Coupling changes** (full detail only): New `_compute_coupling_diff()` helper that runs `analyze_coupling_metrics()` on both refs (using the existing worktree mechanism already in the function) and returns:
```python
{
    "base_modules": 15,
    "head_modules": 17,
    "new_high_distance": [{"module": "core.indexer", "distance": 0.82}],
    "resolved_high_distance": [{"module": "web.app", "distance": 0.75}],
}
```

High distance threshold: D > 0.7 (same as recommendations).

**Smell diff** (full detail only): New `_compute_smell_diff()` helper comparing smells between refs:
```python
{
    "new_smells": [{"type": "god_class", "file": "src/big.py", "entity": "BigManager"}],
    "resolved_smells": [{"type": "long_method", "file": "src/old.py", "entity": "old_func"}],
}
```

Smell matching: a smell is "the same" if (type, file, entity) match. New = in head but not base. Resolved = in base but not head.

### 2.4 Return Shape Changes

The `compare_architecture()` function signature adds `detail_level` parameter. Return dict adds:
```python
{
    # ... existing fields (status, base_ref, head_ref, deltas, base_health, head_health) ...
    "verdict": {"summary": "...", "improved": [...], "degraded": [...], "unchanged": [...]},
    # Full detail only:
    "coupling_changes": {...},  # or absent in standard
    "smell_diff": {...},  # or absent in standard
}
```

### 2.5 Handler Changes

In `handle_compare_architecture`, pass `detail_level` through to the generator:
```python
result = compare_architecture(
    repo_path, project_name,
    base_ref=validated.base_ref, head_ref=validated.head_ref,
    detail_level=validated.detail_level,
)
```

---

## 3. Testing Strategy

### File Context Tests (in existing `tests/test_file_context.py` or similar)

- Standard detail returns existing fields only (no entities, tests, commits)
- Full detail includes `entities` list with function/class names and lines
- Full detail includes `related_tests` (create test file that imports the target)
- Full detail includes `recent_commits` (mock git subprocess)
- Full detail on non-git repo returns empty commits list gracefully
- Missing file returns error

### Compare Architecture Tests (in existing `tests/test_architecture_compare.py` or similar)

- Standard detail includes `verdict` with summary, improved, degraded, unchanged
- Verdict correctly categorizes dimensions (>+2 improved, <-2 degraded, else unchanged)
- Verdict summary text matches delta direction
- Full detail includes `coupling_changes` with new/resolved high-distance modules
- Full detail includes `smell_diff` with new/resolved smells
- Standard detail does NOT include coupling_changes or smell_diff
- Smell matching by (type, file, entity) tuple works correctly
