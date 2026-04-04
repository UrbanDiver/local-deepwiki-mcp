# File: `src/local_deepwiki/generators/analysis/duplication.py`

## File Overview

This file implements duplication detection capabilities for source code repositories, identifying both **Type 1** (exact) and **Type 2** (structural) clones. It is part of the analysis generators in the `local_deepwiki` project and is used to assess code duplication across a codebase.

The module is designed to be purely computational, relying on AST parsing and line-based fingerprinting without any external language model calls. It is intended for use in static analysis pipelines to support code quality metrics, refactorability assessments, and duplication-aware architecture reports.

## Key Concepts

### Duplication Detection Strategies

The file implements two distinct strategies for detecting code duplication:

1. **Type 1 Clones (Exact Duplication)**:
   - Uses a **sliding window fingerprinting** approach.
   - Normalizes source lines by stripping whitespace and ignoring comments.
   - Computes a hash over a fixed number of consecutive normalized lines.
   - Identifies groups of files/locations with identical fingerprints.

2. **Type 2 Clones (Structural Duplication)**:
   - Uses **AST node-type sequences** to compare function structures.
   - Extracts function nodes using [`find_nodes_by_type`](../../core/parser/ast_utils.md) and collects their node types recursively.
   - Computes a hash over the sequence of node types.
   - Groups functions with identical structural fingerprints.

### Design Rationale

- **Fingerprinting for Performance**: Instead of comparing every possible code block, fingerprinting allows for fast grouping of potentially duplicated code.
- **AST-based Structural Analysis**: Structural clones are identified by comparing the tree structure of functions, which is more robust than line-based matching.
- **Deduplication of Overlapping Windows**: For Type 1 clones, overlapping sliding windows are removed to avoid overcounting.
- **Modular Architecture**: Functions are kept small and focused, promoting reusability and testability.

## Integration

This module is used by the `test_duplication` test suite, which calls the `detect_type1_clones`, `detect_type2_clones`, and `analyze_duplication` functions. It is also likely used by CLI tools or other analysis modules such as `architecture_report.py` or `health_scoring.py` to provide duplication metrics as part of a broader code health assessment.

It integrates with:
- [`iter_python_files`](source_filter.md) from `source_filter` to enumerate Python source files.
- [`CodeParser`](../../core/parser/code_parser.md) and `ast_utils` for AST-based analysis.
- `FUNCTION_NODE_TYPES` to know which AST node types represent functions.
- [`get_logger`](../../logging.md) for logging warnings when files cannot be read.

## Design Notes

### Handling of Edge Cases

- **Blank Lines and Comments**: `_normalize_line` filters out blank lines and comment-only lines to ensure meaningful fingerprints.
- **File Read Errors**: If a file cannot be read, it is skipped with a warning.
- **Small Code Blocks**: Functions or code blocks with fewer than `_MIN_AST_NODES` or `min_lines` are ignored to prevent noise.
- **Overlapping Windows**: For Type 1 clones, `_deduplicate_clone_group` removes overlapping window instances to ensure accurate duplication counts.

### Performance Considerations

- **Sliding Window Hashing**: Efficiently scans all possible consecutive line sequences of a given length.
- **AST Node Collection**: Uses a recursive depth-first traversal to [collect](../../web/routes_chat.md) all node types for a function, ensuring structural integrity.
- **Hash-based Grouping**: Uses Python’s built-in `hash()` function for fast grouping, though it may have collisions (handled by deduplication).

### Constants and Configuration

- `_MIN_CLONE_LINES` and `_MIN_AST_NODES` are used to filter out very small code blocks that are unlikely to be meaningful clones. These are not defined in this file but are expected to be available in the module scope.
- `top_n` in `analyze_duplication` controls how many top clone groups are returned, preventing an overwhelming output.

This design allows for both fine-grained and high-level duplication analysis, making it suitable for both automated tools and interactive analysis workflows.

## API Reference

### Functions

#### `detect_type1_clones`

```python
def detect_type1_clones(repo_path: Path, min_lines: int = _MIN_CLONE_LINES, exclude_tests: bool = True) -> list[dict[str, Any]]
```

Detect exact code clones (Type 1) using line-based fingerprinting.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path` | - | Root of the repository to scan. |
| `min_lines` | `int` | `_MIN_CLONE_LINES` | Minimum consecutive lines for a clone block. |
| `exclude_tests` | `bool` | `True` | Skip test files when True. |

**Returns:** `list[dict[str, Any]]`



<details>
<summary>View Source (lines 109-148) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L109-L148">GitHub</a></summary>

```python
def detect_type1_clones(
    repo_path: Path,
    *,
    min_lines: int = _MIN_CLONE_LINES,
    exclude_tests: bool = True,
) -> list[dict[str, Any]]:
    """Detect exact code clones (Type 1) using line-based fingerprinting.

    Args:
        repo_path: Root of the repository to scan.
        min_lines: Minimum consecutive lines for a clone block.
        exclude_tests: Skip test files when True.

    Returns:
        List of clone groups sorted by number of instances descending.
    """
    repo_path = Path(repo_path)
    fingerprints = _build_fingerprints(repo_path, min_lines, exclude_tests)

    # Filter to groups with 2+ instances and deduplicate overlapping windows
    clone_groups: list[dict[str, Any]] = []
    for fp_hash, instances in fingerprints.items():
        if len(instances) < 2:
            continue

        unique_instances = _deduplicate_clone_group(instances)
        if len(unique_instances) < 2:
            continue

        clone_groups.append(
            {
                "fingerprint": hex(fp_hash & 0xFFFFFFFFFFFFFFFF),
                "line_count": min_lines,
                "instances": unique_instances,
            }
        )

    # Sort by number of instances descending
    clone_groups.sort(key=lambda g: len(g["instances"]), reverse=True)
    return clone_groups
```

</details>

#### `detect_type2_clones`

```python
def detect_type2_clones(repo_path: Path, exclude_tests: bool = True) -> list[dict[str, Any]]
```

Detect structural clones (Type 2) by comparing function AST structure.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path` | - | Root of the repository to scan. |
| `exclude_tests` | `bool` | `True` | Skip test files when True. |

**Returns:** `list[dict[str, Any]]`



<details>
<summary>View Source (lines 151-221) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L151-L221">GitHub</a></summary>

```python
def detect_type2_clones(
    repo_path: Path,
    *,
    exclude_tests: bool = True,
) -> list[dict[str, Any]]:
    """Detect structural clones (Type 2) by comparing function AST structure.

    Args:
        repo_path: Root of the repository to scan.
        exclude_tests: Skip test files when True.

    Returns:
        List of clone groups sorted by group size descending.
    """
    repo_path = Path(repo_path)
    parser = CodeParser()
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)

    # Build mapping: structural_hash -> list of function info dicts
    structural_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for full_path, rel_path in files:
        result = parser.parse_file(full_path)
        if result is None:
            continue

        root, language, source = result
        fn_types = FUNCTION_NODE_TYPES.get(language)
        if fn_types is None:
            continue

        fn_nodes = find_nodes_by_type(root, fn_types)
        for fn_node in fn_nodes:
            node_types = _collect_node_types(fn_node)
            if len(node_types) < _MIN_AST_NODES:
                continue

            struct_hash = hash(tuple(node_types))
            fn_name = get_node_name(fn_node, source, language) or "<anonymous>"
            structural_groups[struct_hash].append(
                {
                    "file": str(rel_path),
                    "function": fn_name,
                    "line": fn_node.start_point[0] + 1,
                    "node_count": len(node_types),
                }
            )

    # Filter to groups with 2+ members
    clone_groups: list[dict[str, Any]] = []
    for s_hash, instances in structural_groups.items():
        if len(instances) < 2:
            continue
        clone_groups.append(
            {
                "structural_hash": hex(s_hash & 0xFFFFFFFFFFFFFFFF),
                "node_count": instances[0]["node_count"],
                "instances": [
                    {
                        "file": inst["file"],
                        "function": inst["function"],
                        "line": inst["line"],
                    }
                    for inst in instances
                ],
            }
        )

    # Sort by group size descending
    clone_groups.sort(key=lambda g: len(g["instances"]), reverse=True)
    return clone_groups
```

</details>

#### `analyze_duplication`

```python
def analyze_duplication(repo_path: Path, min_lines: int = _MIN_CLONE_LINES, top_n: int = 20, exclude_tests: bool = True) -> dict[str, Any]
```

Run both detection types and compute summary statistics.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path` | - | Root of the repository to scan. |
| `min_lines` | `int` | `_MIN_CLONE_LINES` | Minimum consecutive lines for Type 1 clones. |
| `top_n` | `int` | `20` | Maximum number of clone groups to return per type. |
| `exclude_tests` | `bool` | `True` | Skip test files when True. |

**Returns:** `dict[str, Any]`




<details>
<summary>View Source (lines 224-280) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L224-L280">GitHub</a></summary>

```python
def analyze_duplication(
    repo_path: Path,
    *,
    min_lines: int = _MIN_CLONE_LINES,
    top_n: int = 20,
    exclude_tests: bool = True,
) -> dict[str, Any]:
    """Run both detection types and compute summary statistics.

    Args:
        repo_path: Root of the repository to scan.
        min_lines: Minimum consecutive lines for Type 1 clones.
        top_n: Maximum number of clone groups to return per type.
        exclude_tests: Skip test files when True.

    Returns:
        Dict with status, clone groups, and summary stats.
    """
    repo_path = Path(repo_path)

    # Compute total source lines across all scanned files
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)
    total_lines = 0
    for full_path, _rel_path in files:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            total_lines += len(content.splitlines())
        except OSError:
            continue

    # Run both detectors
    type1_clones = detect_type1_clones(repo_path, min_lines=min_lines, exclude_tests=exclude_tests)
    type2_clones = detect_type2_clones(repo_path, exclude_tests=exclude_tests)

    # Compute duplicated lines:
    # Each instance contributes line_count lines, but one copy per group is "original"
    duplicated_lines = sum(
        group["line_count"] * (len(group["instances"]) - 1) for group in type1_clones
    )

    largest_clone_lines = max((group["line_count"] for group in type1_clones), default=0)

    duplication_ratio = duplicated_lines / total_lines if total_lines > 0 else 0.0

    return {
        "status": "success",
        "type1_clones": type1_clones[:top_n],
        "type2_clones": type2_clones[:top_n],
        "stats": {
            "total_lines": total_lines,
            "duplicated_lines": duplicated_lines,
            "duplication_ratio": duplication_ratio,
            "type1_clone_groups": len(type1_clones),
            "type2_clone_groups": len(type2_clones),
            "largest_clone_lines": largest_clone_lines,
        },
    }
```

</details>

## Call Graph

```mermaid
flowchart TD
    N0[CodeParser]
    N1[Path]
    N2[_build_fingerprints]
    N3[_collect_node_types]
    N4[_deduplicate_clone_group]
    N5[_normalize_line]
    N6[add]
    N7[analyze_duplication]
    N8[defaultdict]
    N9[detect_type1_clones]
    N10[detect_type2_clones]
    N11[find_nodes_by_type]
    N12[get_node_name]
    N13[iter_python_files]
    N14[parse_file]
    N15[read_text]
    N16[sort]
    N17[splitlines]
    N3 --> N3
    N2 --> N13
    N2 --> N8
    N2 --> N15
    N2 --> N17
    N2 --> N5
    N4 --> N6
    N9 --> N1
    N9 --> N2
    N9 --> N4
    N9 --> N16
    N10 --> N1
    N10 --> N0
    N10 --> N13
    N10 --> N8
    N10 --> N14
    N10 --> N11
    N10 --> N3
    N10 --> N12
    N10 --> N16
    N7 --> N1
    N7 --> N13
    N7 --> N15
    N7 --> N17
    N7 --> N9
    N7 --> N10
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17 func
```

## Used By

Functions and methods in this file and their callers:

- **[`CodeParser`](../../core/parser/code_parser.md)**: called by `detect_type2_clones`
- **`Path`**: called by `analyze_duplication`, `detect_type1_clones`, `detect_type2_clones`
- **`_build_fingerprints`**: called by `detect_type1_clones`
- **`_collect_node_types`**: called by `_collect_node_types`, `detect_type2_clones`
- **`_deduplicate_clone_group`**: called by `detect_type1_clones`
- **`_normalize_line`**: called by `_build_fingerprints`
- **`add`**: called by `_deduplicate_clone_group`
- **`defaultdict`**: called by `_build_fingerprints`, `detect_type2_clones`
- **`detect_type1_clones`**: called by `analyze_duplication`
- **`detect_type2_clones`**: called by `analyze_duplication`
- **[`find_nodes_by_type`](../../core/parser/ast_utils.md)**: called by `detect_type2_clones`
- **[`get_node_name`](../../core/parser/ast_utils.md)**: called by `detect_type2_clones`
- **[`iter_python_files`](source_filter.md)**: called by `_build_fingerprints`, `analyze_duplication`, `detect_type2_clones`
- **`parse_file`**: called by `detect_type2_clones`
- **`read_text`**: called by `_build_fingerprints`, `analyze_duplication`
- **`sort`**: called by `detect_type1_clones`, `detect_type2_clones`
- **`splitlines`**: called by `_build_fingerprints`, `analyze_duplication`

## Usage Examples

*Examples extracted from test files*

### Example: `duplication`

From `test_duplication.py::test_detect_type1_clones_finds_exact_duplicates`:

```python
from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    _write_py(tmp_path / "src" / "a.py", _DUPLICATE_BLOCK + "\nx = 1\n")
    _write_py(tmp_path / "src" / "b.py", _DUPLICATE_BLOCK + "\ny = 2\n")
    clones = detect_type1_clones(tmp_path, min_lines=6)
    assert len(clones) >= 1
    assert clones[0]["line_count"] >= 6
```

### Example: `detect_type1_clones`

From `test_duplication.py::test_detect_type1_clones_finds_exact_duplicates`:

```python
from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    _write_py(tmp_path / "src" / "a.py", _DUPLICATE_BLOCK + "\nx = 1\n")
    _write_py(tmp_path / "src" / "b.py", _DUPLICATE_BLOCK + "\ny = 2\n")
    clones = detect_type1_clones(tmp_path, min_lines=6)
    assert len(clones) >= 1
    assert clones[0]["line_count"] >= 6
```

### Example: `detect_type1_clones`

From `test_duplication.py::test_detect_type1_clones_no_duplicates`:

```python
from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    _write_py(tmp_path / "src" / "a.py", "def foo():\n    return 1\n")
    _write_py(tmp_path / "src" / "b.py", "def bar():\n    return 2\n")
    clones = detect_type1_clones(tmp_path, min_lines=6)
    assert clones == []
```

### Example: `detect_type2_clones`

From `test_duplication.py::test_detect_type2_clones_finds_structural_duplicates`:

```python
from local_deepwiki.generators.analysis.duplication import detect_type2_clones

    # Two functions with same structure but different names/values
    _write_py(
        tmp_path / "src" / "a.py",
        """
def process_users(users):
    result = []
    for user in users:
        if user.is_active():
            name = user.get_name()
            result.append(name)
    return result

def process_orders(orders):
    result = []
    for order in orders:
        if order.is_valid():
            total = order.get_total()
            result.append(total)
    return result
""",
    )
    clones = detect_type2_clones(tmp_path)
    assert len(clones) >= 1
```

### Example: `detect_type2_clones`

From `test_duplication.py::test_detect_type2_clones_no_structural_duplicates`:

```python
from local_deepwiki.generators.analysis.duplication import detect_type2_clones

    _write_py(
        tmp_path / "src" / "a.py",
        """
def simple():
    return 1

def complex_fn(x, y, z):
    if x > 0:
        for i in range(y):
            z += i
    return z
""",
    )
    clones = detect_type2_clones(tmp_path)
    # These have different structures, should not be grouped
    assert all(len(c["instances"]) < 2 for c in clones) if clones else True
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `_build_fingerprints` | function | Brian Breidenbach | today | `a75af5c` refactor: extract helpers f... |
| `_deduplicate_clone_group` | function | Brian Breidenbach | today | `a75af5c` refactor: extract helpers f... |
| `detect_type1_clones` | function | Brian Breidenbach | today | `a75af5c` refactor: extract helpers f... |
| `analyze_duplication` | function | Brian Breidenbach | today | `3fed1da` feat: add duplication-based... |
| `_normalize_line` | function | Brian Breidenbach | today | `75290fc` feat: add clone detection e... |
| `_collect_node_types` | function | Brian Breidenbach | today | `75290fc` feat: add clone detection e... |
| `detect_type2_clones` | function | Brian Breidenbach | today | `75290fc` feat: add clone detection e... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_normalize_line`

<details>
<summary>View Source (lines 26-37) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L26-L37">GitHub</a></summary>

```python
def _normalize_line(line: str) -> str | None:
    """Normalize a source line for fingerprinting.

    Strips leading/trailing whitespace, returns None for blank lines
    and comment-only lines.
    """
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("#"):
        return None
    return stripped
```

</details>


#### `_collect_node_types`

<details>
<summary>View Source (lines 40-45) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L40-L45">GitHub</a></summary>

```python
def _collect_node_types(node: Any) -> list[str]:
    """Walk all descendants depth-first and collect node type strings."""
    types: list[str] = [node.type]
    for child in node.children:
        types.extend(_collect_node_types(child))
    return types
```

</details>


#### `_build_fingerprints`

<details>
<summary>View Source (lines 48-92) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L48-L92">GitHub</a></summary>

```python
def _build_fingerprints(
    repo_path: Path,
    min_lines: int,
    exclude_tests: bool,
) -> dict[int, list[dict[str, Any]]]:
    """Build hash -> location mapping from all files.

    Reads each file, normalizes lines, and computes sliding-window hashes.
    Returns a dict mapping fingerprint hash to list of location dicts.
    """
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)
    fingerprints: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for full_path, rel_path in files:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Cannot read %s, skipping", full_path)
            continue

        raw_lines = content.splitlines()

        # Build list of (original_line_number, normalized_text)
        normalized: list[tuple[int, str]] = []
        for i, line in enumerate(raw_lines, start=1):
            norm = _normalize_line(line)
            if norm is not None:
                normalized.append((i, norm))

        if len(normalized) < min_lines:
            continue

        # Sliding window over normalized lines
        for start_idx in range(len(normalized) - min_lines + 1):
            window = normalized[start_idx : start_idx + min_lines]
            key = hash(tuple(entry[1] for entry in window))
            fingerprints[key].append(
                {
                    "file": str(rel_path),
                    "start_line": window[0][0],
                    "end_line": window[-1][0],
                }
            )

    return fingerprints
```

</details>


#### `_deduplicate_clone_group`

<details>
<summary>View Source (lines 95-106) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/duplication.py#L95-L106">GitHub</a></summary>

```python
def _deduplicate_clone_group(
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove overlapping windows from a clone group, return unique instances."""
    seen: set[tuple[str, int]] = set()
    unique: list[dict[str, Any]] = []
    for inst in instances:
        loc = (inst["file"], inst["start_line"])
        if loc not in seen:
            seen.add(loc)
            unique.append(inst)
    return unique
```

</details>

## Relevant Source Files

- `src/local_deepwiki/generators/analysis/duplication.py:26-37`
