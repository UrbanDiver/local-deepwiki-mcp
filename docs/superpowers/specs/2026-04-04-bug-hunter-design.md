# Bug Hunter — Static + LLM Bug Detection

## Goal

Add a `detect_bugs` MCP tool that scans a repository for potential bugs using AST pattern matching, with optional LLM enrichment for verification and explanation. Targets developers evaluating a new codebase for code quality alongside existing tools (hotspots, smells, coupling).

## Architecture

### New Files

| File | Responsibility |
|------|----------------|
| `src/local_deepwiki/generators/analysis/bug_patterns.py` | `BugPattern` dataclass, `BugConfidence` enum, `BugFinding` TypedDict, detector functions, `PATTERNS` registry |
| `src/local_deepwiki/generators/analysis/bug_detection.py` | `analyze_bugs()` orchestrator — walks files, runs detectors, collects findings |
| `src/local_deepwiki/handlers/analysis_bugs.py` | MCP handler — arg validation, RBAC, LLM enrichment, response formatting |

### Follows Existing Patterns

- `bug_detection.py` mirrors `design_smells.py` (AST scan -> structured findings)
- `bug_patterns.py` mirrors declarative pattern definitions in `hotspots.py`
- Handler mirrors `handle_detect_secrets` in `handlers/generators.py`
- `enrich=true` follows `get_recommendations(enrich=true)` pattern

### Data Flow

1. Handler validates args via Pydantic model, checks RBAC
2. `analyze_bugs(repo_path, min_confidence, languages, exclude_tests, file_path)` called
3. Scanner iterates source files via `iter_source_files`, parses each with tree-sitter
4. For each file, runs all registered detectors whose `languages` set includes the file's detected language
5. Filters findings by `min_confidence`, sorts by confidence then file path
6. If `enrich=true`, handler sends top N findings + surrounding code context to LLM
7. Returns structured JSON

## Data Types

### BugConfidence Enum

```python
class BugConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

Ordering: HIGH > MEDIUM > LOW. Used for both pattern definitions and filtering.

### BugPattern

```python
@dataclass(frozen=True, slots=True)
class BugPattern:
    name: str                          # e.g. "mutable-default-argument"
    description: str                   # Human-readable explanation
    languages: frozenset[str]          # {"python"}, {"go"}, {"python", "javascript"}
    confidence: BugConfidence          # HIGH, MEDIUM, LOW
    detect: Callable[[Node, bytes], list[BugFinding]]
```

Detectors receive a function/class AST node and source bytes, return findings. They never do I/O.

### BugFinding

```python
class BugFinding(TypedDict):
    pattern: str
    file: str
    line: int
    confidence: str
    message: str
    snippet: str
```

### EnrichedBugFinding (extends BugFinding)

Added by LLM enrichment pass:

```python
class EnrichedBugFinding(BugFinding):
    verified: bool       # LLM agrees it's a bug
    explanation: str     # Why it's a problem
    suggestion: str      # How to fix it
```

Findings marked `verified=false` are demoted to `"low"` confidence.

### Pattern Registry

Module-level list in `bug_patterns.py`:

```python
PATTERNS: list[BugPattern] = [
    BugPattern(
        name="mutable-default-argument",
        description="Mutable default arguments are shared across calls",
        languages=frozenset({"python"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_mutable_defaults,
    ),
    ...
]
```

Scanner filters PATTERNS by language and confidence before running.

## Initial Bug Patterns (22)

### High Confidence

| Pattern | Languages | What it catches |
|---------|-----------|----------------|
| `mutable-default-argument` | Python | `def f(x=[])` — shared mutable state |
| `bare-except` | Python | `except:` or `except Exception: pass` — swallowed errors |
| `unreachable-code` | Python, JS, TS, Go, Rust, Java, C, C++, C# | Code after `return`/`raise`/`break`/`continue` |
| `comparison-to-none` | Python | `x == None` instead of `x is None` |
| `f-string-no-expression` | Python | `f"no braces here"` — probably forgot `{}` |
| `empty-catch-block` | JS, TS, Java, Go, C#, Kotlin | `catch (e) {}` — swallowed errors |
| `sizeof-pointer` | C, C++ | `sizeof(ptr)` when `sizeof(*ptr)` or array size intended |
| `null-deref-after-check` | C, C++, C# | Dereference inside null-true branch |
| `missing-break-in-switch` | C, C++, C#, Java | Switch case falls through without break/return |
| `string-format-mismatch` | C, C++ | printf format specifier count doesn't match args |

### Medium Confidence

| Pattern | Languages | What it catches |
|---------|-----------|----------------|
| `unused-variable` | Python, JS, TS, Go, Rust | Assigned but never read (excluding `_` prefixed) |
| `exception-not-used` | Python | `except SomeError as e:` where `e` never referenced |
| `missing-await` | Python, JS, TS | Coroutine called without `await` |
| `redundant-condition` | Python, JS, TS | `if x: if x:` — duplicate check |
| `shadowed-variable` | Python, JS, TS | Inner scope redefines outer variable name |
| `reraised-without-chain` | Python | `raise NewError()` in except without `from` |
| `uninitialized-variable` | C, C++ | Local variable used before assignment |
| `disposing-not-called` | C# | `IDisposable` without `using` block |
| `async-void` | C# | `async void` method — can't be awaited, exceptions crash |
| `assignment-in-condition` | C, C++, JS | `if (x = 5)` instead of `if (x == 5)` |
| `integer-overflow-cast` | C, C++ | Narrowing cast without bounds check |
| `dangling-else` | C, C++ | Ambiguous else binding without braces |

## MCP Tool Interface

```
detect_bugs(
    repo_path: str,                           # required
    min_confidence: BugConfidence = "medium",  # filter threshold
    languages: list[str] | None = None,       # filter to specific languages
    enrich: bool = false,                     # LLM verification pass
    enrich_top_n: int = 10,                   # max findings to send to LLM
    exclude_tests: bool = true,               # skip test files
    file_path: str | None = None,             # scope to single file
    top_n: int = 50,                          # max findings to return
)
```

### Response Shape

```json
{
    "status": "success",
    "total_findings": 42,
    "returned": 42,
    "by_confidence": {"high": 8, "medium": 34},
    "by_pattern": {"bare-except": 5, "mutable-default-argument": 3},
    "findings": [
        {
            "pattern": "bare-except",
            "file": "src/myapp/handler.py",
            "line": 45,
            "confidence": "high",
            "message": "Bare except swallows all exceptions including KeyboardInterrupt",
            "snippet": "except:\n    pass",
            "verified": true,
            "explanation": "This catch block silently discards errors...",
            "suggestion": "Catch a specific exception type"
        }
    ],
    "patterns_checked": 18,
    "files_scanned": 135
}
```

Sorted by confidence (high first), then by file path. Fields `verified`, `explanation`, `suggestion` only present when `enrich=true`.

## LLM Enrichment

When `enrich=true`:

1. Take the top `enrich_top_n` findings (highest confidence first)
2. For each finding, extract ~20 lines of surrounding code context
3. Send to LLM with prompt asking: is this actually a bug? What would go wrong? How to fix?
4. LLM returns `verified`, `explanation`, `suggestion` per finding
5. Findings marked `verified=false` are demoted to `"low"` confidence

Uses the existing LLM provider infrastructure. No new provider code needed.

## Testing

- Each detector gets its own test with a minimal code snippet that triggers the pattern
- Detector tests are pure (AST node in, findings out, no I/O)
- Orchestrator tested with tmp_path repos (same pattern as `test_design_smells.py`)
- LLM enrichment tested with mocked LLM provider
- Handler tested with mocked access controller (same pattern as other handler tests)

## Not In Scope

- Adding bug detection as a health score dimension (future consideration)
- Auto-fix capability (detection only)
- Custom user-defined patterns (use the registry pattern, but no config-file-based patterns)
- Cross-file analysis (each detector sees one file at a time)
