# Phase 2a: Onboarding Guide + Recommendations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `get_onboarding_guide` and `get_recommendations` MCP tools, and integrate template recommendations into the existing `analyze_architecture` composite output.

**Architecture:** Two new generator modules (`onboarding.py`, `recommendations.py`) following the existing pure-function pattern. Each gets a Pydantic args model, tool definition, and handler. The recommendations generator also integrates into `architecture_composite.py` → `architecture_report.py` for the composite tool. No LLM calls by default; optional LLM enrichment in the standalone recommendations tool only.

**Tech Stack:** Python 3.11+, Pydantic, FastMCP, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-27-phase2a-onboarding-recommendations-design.md`

---

### Task 1: Create onboarding guide generator

**Files:**
- Create: `src/local_deepwiki/generators/analysis/onboarding.py`
- Test: `tests/test_onboarding.py`

- [ ] **Step 1: Write failing test for generator**

```python
# tests/test_onboarding.py
"""Tests for the get_onboarding_guide tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a repo with known structure for onboarding tests."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.0.0"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    # Source code
    src = tmp_path / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "__main__.py").write_text("from .cli import main\nmain()\n")
    (src / "cli.py").write_text("def main():\n    print('hello')\n")
    (src / "server.py").write_text("def run_server():\n    pass\n")
    (src / "utils.py").write_text("def helper():\n    return 1\n")
    # Sub-package
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "engine.py").write_text("class Engine:\n    pass\n")
    # Tests
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_cli.py").write_text("def test_main():\n    pass\n")
    # Config files
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    return tmp_path


def test_generate_onboarding_guide_standard(sample_repo):
    """Standard detail returns all main sections."""
    from local_deepwiki.generators.analysis.onboarding import generate_onboarding_guide

    result = generate_onboarding_guide(sample_repo)
    assert result["status"] == "success"
    data = result["data"]
    assert data["project_name"] == "myapp"
    assert "entry_points" in data
    assert len(data["entry_points"]) > 0
    assert "key_modules" in data
    assert "test_layout" in data


def test_generate_onboarding_guide_has_entry_points(sample_repo):
    """Detects __main__.py, cli.py, and server.py as entry points."""
    from local_deepwiki.generators.analysis.onboarding import generate_onboarding_guide

    result = generate_onboarding_guide(sample_repo)
    entry_files = [e["file"] for e in result["data"]["entry_points"]]
    assert any("__main__" in f for f in entry_files)
    assert any("server" in f for f in entry_files)


def test_format_onboarding_guide_standard(sample_repo):
    """Formatter produces markdown with expected sections."""
    from local_deepwiki.generators.analysis.onboarding import (
        format_onboarding_guide,
        generate_onboarding_guide,
    )

    result = generate_onboarding_guide(sample_repo)
    md = format_onboarding_guide(result["data"])
    assert "## Project Overview" in md
    assert "## Getting Started" in md
    assert "## Repository Layout" in md
    assert "## Entry Points" in md
    assert "## Key Modules" in md
    assert "## Testing" in md


def test_format_onboarding_guide_summary(sample_repo):
    """Summary detail returns only overview + getting started + layout."""
    from local_deepwiki.generators.analysis.onboarding import (
        format_onboarding_guide,
        generate_onboarding_guide,
    )

    result = generate_onboarding_guide(sample_repo, detail_level="summary")
    md = format_onboarding_guide(result["data"], detail_level="summary")
    assert "## Project Overview" in md
    assert "## Getting Started" in md
    assert "## Repository Layout" in md
    assert "## Entry Points" not in md
    assert "## Key Modules" not in md


def test_format_onboarding_guide_full(sample_repo):
    """Full detail includes configuration section."""
    from local_deepwiki.generators.analysis.onboarding import (
        format_onboarding_guide,
        generate_onboarding_guide,
    )

    result = generate_onboarding_guide(sample_repo, detail_level="full")
    md = format_onboarding_guide(result["data"], detail_level="full")
    assert "## Configuration" in md


def test_generate_onboarding_guide_empty_repo(tmp_path):
    """Empty repo returns graceful minimal data."""
    from local_deepwiki.generators.analysis.onboarding import generate_onboarding_guide

    result = generate_onboarding_guide(tmp_path)
    assert result["status"] == "success"
    assert result["data"]["entry_points"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_onboarding.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement onboarding generator**

Create `src/local_deepwiki/generators/analysis/onboarding.py`:

```python
"""Onboarding guide generator for developer codebase orientation.

Scans repository structure, manifest, entry points, and test layout
to produce a structured onboarding guide. No LLM calls, no indexing required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.dir_tree import get_directory_tree
from local_deepwiki.generators.manifest import get_cached_manifest
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_ENTRY_POINT_PATTERNS = (
    "__main__.py",
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
)

_CONFIG_PATTERNS = (
    ".github",
    ".gitlab-ci.yml",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
    ".eslintrc",
    "tsconfig.json",
    "Cargo.toml",
    "go.mod",
)


def generate_onboarding_guide(
    repo_path: Path,
    *,
    detail_level: str = "standard",
) -> dict[str, Any]:
    """Generate structured onboarding data by scanning the repository.

    Args:
        repo_path: Path to the repository root.
        detail_level: "summary", "standard", or "full".

    Returns:
        Dict with status and data containing project info, entry points,
        key modules, test layout, and config files.
    """
    manifest = get_cached_manifest(repo_path)
    project_name = manifest.name or repo_path.name

    max_depth = {"summary": 1, "standard": 2, "full": 3}.get(detail_level, 2)
    dir_tree = get_directory_tree(repo_path, max_depth=max_depth)

    entry_points = _find_entry_points(repo_path)
    key_modules = _find_key_modules(repo_path, detail_level)
    test_layout = _detect_test_layout(repo_path, manifest)
    config_files = _detect_config_files(repo_path) if detail_level == "full" else []

    return {
        "status": "success",
        "data": {
            "project_name": project_name,
            "manifest": {
                "version": manifest.version,
                "description": manifest.description,
                "language": manifest.language,
                "tech_stack": manifest.get_tech_stack_summary(),
                "scripts": dict(manifest.scripts),
            },
            "directory_tree": dir_tree,
            "entry_points": entry_points,
            "key_modules": key_modules,
            "test_layout": test_layout,
            "config_files": config_files,
        },
    }


def format_onboarding_guide(
    data: dict[str, Any],
    *,
    detail_level: str = "standard",
) -> str:
    """Format onboarding data into a markdown narrative."""
    sections: list[str] = []
    sections.append(_format_project_overview(data))
    sections.append(_format_getting_started(data))
    sections.append(_format_repo_layout(data))

    if detail_level in ("standard", "full"):
        sections.append(_format_entry_points(data))
        top_n = 8 if detail_level == "full" else 5
        sections.append(_format_key_modules(data, top_n))
        sections.append(_format_testing(data))

    if detail_level == "full":
        sections.append(_format_configuration(data))

    return "\n\n".join(s for s in sections if s)


def _find_entry_points(repo_path: Path) -> list[dict[str, str]]:
    """Find common entry point files in the repository."""
    results: list[dict[str, str]] = []
    for py_file in sorted(repo_path.rglob("*.py")):
        try:
            rel = py_file.relative_to(repo_path)
        except ValueError:
            continue
        parts = rel.parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__") for p in parts):
            continue
        if rel.name in _ENTRY_POINT_PATTERNS:
            reason = {
                "__main__.py": "Package entry point (python -m)",
                "main.py": "Application main entry",
                "app.py": "Application/web framework entry",
                "server.py": "Server entry point",
                "cli.py": "CLI entry point",
                "manage.py": "Management commands (Django-style)",
                "wsgi.py": "WSGI server entry",
                "asgi.py": "ASGI server entry",
            }.get(rel.name, "Entry point")
            results.append({"file": str(rel), "reason": reason})
    return results


def _find_key_modules(
    repo_path: Path, detail_level: str,
) -> list[dict[str, Any]]:
    """Find the most important packages by file count."""
    max_modules = {"summary": 3, "standard": 5, "full": 8}.get(detail_level, 5)
    pkg_counts: dict[str, int] = {}
    for py_file in repo_path.rglob("*.py"):
        try:
            rel = py_file.relative_to(repo_path)
        except ValueError:
            continue
        parts = rel.parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__", "tests", "test") for p in parts):
            continue
        if len(parts) >= 2:
            pkg = parts[0] if parts[0] != "src" else (parts[1] if len(parts) >= 3 else parts[0])
            pkg_counts[pkg] = pkg_counts.get(pkg, 0) + 1

    sorted_pkgs = sorted(pkg_counts.items(), key=lambda x: -x[1])[:max_modules]
    return [{"name": name, "file_count": count} for name, count in sorted_pkgs]


def _detect_test_layout(
    repo_path: Path, manifest: Any,
) -> dict[str, Any]:
    """Detect test directory structure and framework."""
    test_dirs: list[str] = []
    for candidate in ("tests", "test", "spec", "specs"):
        if (repo_path / candidate).is_dir():
            test_dirs.append(candidate)

    test_count = sum(
        1
        for d in test_dirs
        for _ in (repo_path / d).rglob("test_*.py")
    )

    framework = "unknown"
    all_deps = {**manifest.dependencies, **manifest.dev_dependencies}
    if "pytest" in all_deps:
        framework = "pytest"
    elif "unittest" in all_deps or "nose" in all_deps:
        framework = "unittest"
    elif "jest" in all_deps:
        framework = "jest"
    elif "mocha" in all_deps:
        framework = "mocha"

    return {
        "test_dirs": test_dirs,
        "test_file_count": test_count,
        "framework": framework,
    }


def _detect_config_files(repo_path: Path) -> list[dict[str, str]]:
    """Detect configuration files in the repository root."""
    results: list[dict[str, str]] = []
    descriptions = {
        ".github": "GitHub Actions CI/CD",
        ".gitlab-ci.yml": "GitLab CI/CD",
        "Dockerfile": "Docker container",
        "docker-compose.yml": "Docker Compose",
        "Makefile": "Build automation",
        ".pre-commit-config.yaml": "Pre-commit hooks",
        "pyproject.toml": "Python project config",
        "setup.cfg": "Python setup config",
        "tox.ini": "Tox test runner",
        ".eslintrc": "ESLint config",
        "tsconfig.json": "TypeScript config",
        "Cargo.toml": "Rust project config",
        "go.mod": "Go module config",
    }
    for pattern in _CONFIG_PATTERNS:
        path = repo_path / pattern
        if path.exists():
            results.append({
                "file": pattern,
                "description": descriptions.get(pattern, "Config file"),
            })
    return results


def _format_project_overview(data: dict[str, Any]) -> str:
    manifest = data.get("manifest", {})
    name = data.get("project_name", "Unknown")
    parts = [f"## Project Overview\n\n**{name}**"]
    if manifest.get("description"):
        parts.append(f" — {manifest['description']}")
    parts.append("\n")
    if manifest.get("language"):
        parts.append(f"- **Language**: {manifest['language']}")
    if manifest.get("version"):
        parts.append(f"- **Version**: {manifest['version']}")
    tech = manifest.get("tech_stack", "")
    if tech:
        parts.append(f"\n{tech}")
    return "\n".join(parts)


def _format_getting_started(data: dict[str, Any]) -> str:
    scripts = data.get("manifest", {}).get("scripts", {})
    parts = ["## Getting Started\n"]
    if scripts:
        parts.append("**Available scripts:**\n")
        for name, cmd in list(scripts.items())[:10]:
            parts.append(f"- `{name}`: `{cmd}`")
    else:
        parts.append("No scripts found in project manifest.")
    return "\n".join(parts)


def _format_repo_layout(data: dict[str, Any]) -> str:
    tree = data.get("directory_tree", "")
    return f"## Repository Layout\n\n```\n{tree}\n```"


def _format_entry_points(data: dict[str, Any]) -> str:
    entries = data.get("entry_points", [])
    if not entries:
        return ""
    parts = ["## Entry Points\n"]
    for e in entries:
        parts.append(f"- `{e['file']}` — {e['reason']}")
    return "\n".join(parts)


def _format_key_modules(data: dict[str, Any], top_n: int = 5) -> str:
    modules = data.get("key_modules", [])[:top_n]
    if not modules:
        return ""
    parts = ["## Key Modules\n"]
    for m in modules:
        parts.append(f"- **{m['name']}** ({m['file_count']} files)")
    return "\n".join(parts)


def _format_testing(data: dict[str, Any]) -> str:
    test = data.get("test_layout", {})
    parts = ["## Testing\n"]
    fw = test.get("framework", "unknown")
    dirs = test.get("test_dirs", [])
    count = test.get("test_file_count", 0)
    parts.append(f"- **Framework**: {fw}")
    if dirs:
        parts.append(f"- **Test directories**: {', '.join(dirs)}")
    parts.append(f"- **Test files**: {count}")
    return "\n".join(parts)


def _format_configuration(data: dict[str, Any]) -> str:
    configs = data.get("config_files", [])
    if not configs:
        return ""
    parts = ["## Configuration\n"]
    for c in configs:
        parts.append(f"- `{c['file']}` — {c['description']}")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_onboarding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/onboarding.py tests/test_onboarding.py
git commit -m "feat: add onboarding guide generator"
```

---

### Task 2: Create onboarding guide handler + tool registration

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py` (add `GetOnboardingGuideArgs` after `AnalyzeArchitectureArgs` at ~line 724)
- Modify: `src/local_deepwiki/models/__init__.py` (export new args)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (add tool definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (add handler)
- Modify: `src/local_deepwiki/handlers/analysis.py` (export handler)
- Modify: `src/local_deepwiki/handlers/__init__.py` (export handler)
- Modify: `src/local_deepwiki/server.py` (register handler)
- Test: `tests/test_onboarding.py` (add handler tests)

- [ ] **Step 1: Write failing handler test**

Append to `tests/test_onboarding.py`:

```python
async def test_handler_returns_success(mock_access_control, sample_repo):
    """Handler returns formatted markdown in a success response."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_onboarding_guide,
    )

    result = await handle_get_onboarding_guide({"repo_path": str(sample_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "## Project Overview" in data["guide"]


async def test_handler_missing_repo(mock_access_control, tmp_path):
    """Handler returns error for non-existent repo."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_onboarding_guide,
    )

    result = await handle_get_onboarding_guide(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_handler_invalid_detail_level(mock_access_control, sample_repo):
    """Invalid detail_level falls back to standard (no crash)."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_onboarding_guide,
    )

    result = await handle_get_onboarding_guide(
        {"repo_path": str(sample_repo), "detail_level": "verbose"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_onboarding.py::test_handler_returns_success -v`
Expected: FAIL (handler does not exist)

- [ ] **Step 3: Add args model**

In `src/local_deepwiki/models/tool_args.py`, add after `AnalyzeArchitectureArgs` (after line ~723):

```python
class GetOnboardingGuideArgs(BaseModel):
    """Arguments for the get_onboarding_guide tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~1K), standard (~3K), full (~6K)",
    )
```

In `src/local_deepwiki/models/__init__.py`, add `GetOnboardingGuideArgs` to both the import and `__all__`.

- [ ] **Step 4: Add tool definition**

In `src/local_deepwiki/tool_defs/analysis.py`, add before the `get_module_health` tool:

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
            "repo_path": {
                "type": "string",
                "description": "Path to the repository",
            },
            "detail_level": {
                "type": "string",
                "enum": ["summary", "standard", "full"],
                "description": "Output detail level (default: standard)",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
),
```

- [ ] **Step 5: Add handler**

In `src/local_deepwiki/handlers/analysis_architecture.py`:

1. Add `GetOnboardingGuideArgs` to the import from `local_deepwiki.models`.

2. Add handler function (before `handle_get_module_health`):

```python
@handle_tool_errors
async def handle_get_onboarding_guide(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_onboarding_guide tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetOnboardingGuideArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.onboarding import (
        format_onboarding_guide,
        generate_onboarding_guide,
    )

    result = generate_onboarding_guide(repo_path, detail_level=validated.detail_level)
    guide = format_onboarding_guide(result["data"], detail_level=validated.detail_level)

    logger.info("Onboarding guide generated for %s", repo_path)
    return make_tool_text_content("get_onboarding_guide", {
        "status": "success",
        "guide": guide,
        "tool": "get_onboarding_guide",
    })
```

- [ ] **Step 6: Export and register**

In `src/local_deepwiki/handlers/analysis.py`, add `handle_get_onboarding_guide` to the import and `__all__`.

In `src/local_deepwiki/handlers/__init__.py`, add `handle_get_onboarding_guide` to the import and `__all__`.

In `src/local_deepwiki/server.py`:
1. Add `handle_get_onboarding_guide` to the import from handlers.
2. Add `"get_onboarding_guide": handle_get_onboarding_guide` to `TOOL_HANDLERS`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_onboarding.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/models/__init__.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py src/local_deepwiki/handlers/analysis.py src/local_deepwiki/handlers/__init__.py src/local_deepwiki/server.py tests/test_onboarding.py
git commit -m "feat: add get_onboarding_guide handler and tool registration"
```

---

### Task 3: Create recommendations generator

**Files:**
- Create: `src/local_deepwiki/generators/analysis/recommendations.py`
- Test: `tests/test_recommendations.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_recommendations.py
"""Tests for the get_recommendations tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


def _make_health_data(
    *,
    hotspots=None,
    smells=None,
    god_classes=None,
    layer_violations=None,
    coupling_metrics=None,
):
    """Build a minimal health_data dict for testing recommendations."""
    return {
        "status": "success",
        "overall": {
            "score": 70,
            "grade": "C",
            "dimensions": {
                "complexity": {"score": 75, "grade": "B"},
                "coupling": {"score": 60, "grade": "C"},
                "smells": {"score": 50, "grade": "D"},
                "layers": {"score": 100, "grade": "A"},
            },
        },
        "top_findings": {
            "hotspots": hotspots or [],
            "high_severity_smells": smells or [],
            "god_classes": god_classes or [],
            "layer_violations": layer_violations or [],
        },
        "stats": {
            "total_lines": 10000,
            "total_functions": 200,
            "files_scanned": 50,
            "total_modules": 10,
            "total_smells": len(smells or []) + len(god_classes or []),
        },
        "_coupling_metrics": coupling_metrics or [],
    }


def test_recommendations_from_god_class():
    """God class finding generates 'Split class' recommendation."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(god_classes=[
        {
            "type": "god_class",
            "severity": "high",
            "file": "src/big.py",
            "line": 1,
            "entity": "BigManager",
            "description": "20 methods, 800 lines",
        }
    ])
    result = generate_recommendations(Path("/fake"), health_data=health)
    assert result["status"] == "success"
    recs = result["recommendations"]
    assert len(recs) >= 1
    assert "BigManager" in recs[0]["title"]
    assert recs[0]["category"] == "smells"


def test_recommendations_from_long_method():
    """Long method finding generates 'Extract helpers' recommendation."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(smells=[
        {
            "type": "long_method",
            "severity": "high",
            "file": "src/parser.py",
            "line": 42,
            "entity": "_parse_node",
            "description": "CC=23, 145 lines",
        }
    ])
    result = generate_recommendations(Path("/fake"), health_data=health)
    recs = result["recommendations"]
    assert any("_parse_node" in r["title"] for r in recs)
    matching = [r for r in recs if "_parse_node" in r["title"]][0]
    assert matching["category"] == "complexity"


def test_recommendations_sorted_by_priority():
    """Recommendations are sorted by priority descending."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        god_classes=[{
            "type": "god_class", "severity": "high",
            "file": "a.py", "line": 1, "entity": "A",
            "description": "big",
        }],
        smells=[{
            "type": "long_parameter_list", "severity": "medium",
            "file": "b.py", "line": 10, "entity": "func_b",
            "description": "7 params",
        }],
    )
    result = generate_recommendations(Path("/fake"), health_data=health)
    priorities = [r["priority"] for r in result["recommendations"]]
    assert priorities == sorted(priorities, reverse=True)


def test_recommendations_max_items():
    """max_items limits the number of returned recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    smells = [
        {
            "type": "long_method", "severity": "high",
            "file": f"f{i}.py", "line": 1, "entity": f"func_{i}",
            "description": "long",
        }
        for i in range(20)
    ]
    health = _make_health_data(smells=smells)
    result = generate_recommendations(Path("/fake"), health_data=health, max_items=3)
    assert len(result["recommendations"]) == 3


def test_recommendations_category_filter():
    """category_filter restricts to one category."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        god_classes=[{
            "type": "god_class", "severity": "high",
            "file": "a.py", "line": 1, "entity": "A",
            "description": "big",
        }],
        layer_violations=[{
            "from_layer": "core", "to_layer": "handlers",
            "file": "core/bad.py", "import_module": "handlers.api",
        }],
    )
    result = generate_recommendations(
        Path("/fake"), health_data=health, category_filter="layers",
    )
    for r in result["recommendations"]:
        assert r["category"] == "layers"


def test_recommendations_empty_health():
    """Empty health data returns empty recommendations list."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data()
    result = generate_recommendations(Path("/fake"), health_data=health)
    assert result["recommendations"] == []


def test_recommendations_reuses_health_data():
    """When health_data is provided, no re-analysis happens."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(god_classes=[{
        "type": "god_class", "severity": "high",
        "file": "a.py", "line": 1, "entity": "A",
        "description": "big",
    }])
    # If it tried to call analyze_architecture_health on /fake, it would fail
    result = generate_recommendations(Path("/fake"), health_data=health)
    assert result["status"] == "success"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_recommendations.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement recommendations generator**

Create `src/local_deepwiki/generators/analysis/recommendations.py`:

```python
"""Refactoring recommendation generator.

Maps architecture health findings to prioritized, actionable recommendations.
Template-based by default; optional LLM enrichment via enrich_recommendations().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_IMPACT_WEIGHTS = {"high": 3, "medium": 2, "low": 1}
_EFFORT_WEIGHTS = {"low": 1, "medium": 2, "high": 3}


# Maps (finding_type) -> (category, title_template, effort, impact)
_RECOMMENDATION_TEMPLATES: dict[str, tuple[str, str, str, str]] = {
    "god_class": (
        "smells",
        "Split {entity} into focused components",
        "medium",
        "high",
    ),
    "long_method": (
        "complexity",
        "Extract helpers from {entity}",
        "low",
        "high",
    ),
    "long_parameter_list": (
        "smells",
        "Introduce parameter object for {entity}",
        "low",
        "medium",
    ),
    "feature_envy": (
        "smells",
        "Move {entity} to the class it envies",
        "medium",
        "medium",
    ),
    "large_file": (
        "smells",
        "Split {file} into focused modules",
        "medium",
        "high",
    ),
    "deep_nesting": (
        "complexity",
        "Flatten nesting in {entity}",
        "low",
        "medium",
    ),
}


def generate_recommendations(
    repo_path: Path,
    *,
    health_data: dict[str, Any] | None = None,
    max_items: int = 10,
    category_filter: str | None = None,
) -> dict[str, Any]:
    """Generate prioritized recommendations from health analysis.

    Args:
        repo_path: Repository path (used only if health_data is None).
        health_data: Pre-computed health data. If None, runs analysis.
        max_items: Maximum recommendations to return.
        category_filter: Restrict to one category.

    Returns:
        Dict with status, recommendations list, and stats.
    """
    if health_data is None:
        from local_deepwiki.generators.analysis.architecture_health import (
            analyze_architecture_health,
        )

        health_data = analyze_architecture_health(repo_path, repo_path.name)

    recommendations = _extract_from_findings(health_data)
    recommendations.extend(_extract_from_coupling(health_data))
    recommendations.extend(_extract_from_layer_violations(health_data))
    recommendations.extend(_extract_from_hotspots(health_data))

    # Deduplicate by (file, line, category)
    seen: set[tuple[str, int, str]] = set()
    unique: list[dict[str, Any]] = []
    for r in recommendations:
        key = (r["file"], r["line"], r["category"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    recommendations = unique

    if category_filter:
        recommendations = [r for r in recommendations if r["category"] == category_filter]

    recommendations.sort(key=lambda r: r["priority"], reverse=True)
    total = len(recommendations)
    recommendations = recommendations[:max_items]

    return {
        "status": "success",
        "recommendations": recommendations,
        "stats": {
            "total_findings": total,
            "returned": len(recommendations),
            "category": category_filter or "all",
        },
    }


async def enrich_recommendations(
    recommendations: list[dict[str, Any]],
    llm_provider: Any,
) -> list[dict[str, Any]]:
    """Enrich recommendations with LLM-generated descriptions.

    Adds an 'enriched_description' field to each recommendation.
    Returns a new list (no mutation). Async because LLM providers are async.
    """
    enriched: list[dict[str, Any]] = []
    for rec in recommendations:
        prompt = (
            f"Suggest specific refactoring steps for: {rec['title']}.\n"
            f"File: {rec['file']}:{rec['line']}\n"
            f"Context: {rec['description']}\n"
            f"Keep it to 2-3 sentences."
        )
        try:
            response = await llm_provider.generate(prompt)
            enriched.append({**rec, "enriched_description": response.strip()})
        except Exception:
            enriched.append(rec)
    return enriched


def _compute_priority(effort: str, impact: str) -> float:
    """Compute priority score: higher impact + lower effort = higher priority."""
    return _IMPACT_WEIGHTS.get(impact, 1) * (1 / _EFFORT_WEIGHTS.get(effort, 2))


def _extract_from_findings(health: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract recommendations from smells and god classes."""
    findings = health.get("top_findings", {})
    results: list[dict[str, Any]] = []

    for smell in findings.get("high_severity_smells", []):
        template = _RECOMMENDATION_TEMPLATES.get(smell.get("type", ""))
        if template is None:
            continue
        category, title_tmpl, effort, impact = template
        results.append({
            "title": title_tmpl.format(
                entity=smell.get("entity", "?"),
                file=smell.get("file", "?"),
            ),
            "category": category,
            "description": smell.get("description", ""),
            "file": smell.get("file", ""),
            "line": smell.get("line", 0),
            "effort": effort,
            "impact": impact,
            "priority": _compute_priority(effort, impact),
        })

    for gc in findings.get("god_classes", []):
        template = _RECOMMENDATION_TEMPLATES["god_class"]
        category, title_tmpl, effort, impact = template
        results.append({
            "title": title_tmpl.format(entity=gc.get("entity", "?")),
            "category": category,
            "description": gc.get("description", ""),
            "file": gc.get("file", ""),
            "line": gc.get("line", 0),
            "effort": effort,
            "impact": impact,
            "priority": _compute_priority(effort, impact),
        })

    return results


def _extract_from_coupling(health: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract recommendations from coupling metrics (high distance)."""
    metrics = health.get("_coupling_metrics", [])
    results: list[dict[str, Any]] = []
    for m in metrics:
        if m.get("distance", 0) > 0.7:
            results.append({
                "title": f"Reduce coupling in module {m['module']}",
                "category": "coupling",
                "description": (
                    f"Distance from main sequence: {m['distance']:.2f} "
                    f"(I={m.get('instability', '?')}, A={m.get('abstractness', '?')})"
                ),
                "file": m.get("module", ""),
                "line": 0,
                "effort": "high",
                "impact": "medium",
                "priority": _compute_priority("high", "medium"),
            })
    return results


def _extract_from_layer_violations(health: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract recommendations from layer violations."""
    violations = health.get("top_findings", {}).get("layer_violations", [])
    results: list[dict[str, Any]] = []
    for v in violations:
        results.append({
            "title": f"Fix upward dependency: {v['from_layer']} \u2192 {v['to_layer']}",
            "category": "layers",
            "description": f"{v['file']} imports {v.get('import_module', '?')}",
            "file": v.get("file", ""),
            "line": 0,
            "effort": "low",
            "impact": "high",
            "priority": _compute_priority("low", "high"),
        })
    return results


def _extract_from_hotspots(health: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract recommendations from complexity hotspots (CC > 15)."""
    hotspots = health.get("top_findings", {}).get("hotspots", [])
    results: list[dict[str, Any]] = []
    for h in hotspots:
        cc = h.get("details", {}).get("cyclomatic", 0)
        if cc > 15:
            results.append({
                "title": f"Reduce complexity in {h['function']}",
                "category": "complexity",
                "description": (
                    f"Cyclomatic complexity {cc}, "
                    f"{h.get('details', {}).get('length', '?')} lines"
                ),
                "file": h.get("file", ""),
                "line": h.get("line", 0),
                "effort": "medium",
                "impact": "high",
                "priority": _compute_priority("medium", "high"),
            })
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_recommendations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/recommendations.py tests/test_recommendations.py
git commit -m "feat: add recommendations generator with template mapping"
```

---

### Task 4: Create recommendations handler + tool registration

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py` (add `GetRecommendationsArgs`)
- Modify: `src/local_deepwiki/models/__init__.py` (export)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (add tool def)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (add handler)
- Modify: `src/local_deepwiki/handlers/analysis.py` (export)
- Modify: `src/local_deepwiki/handlers/__init__.py` (export)
- Modify: `src/local_deepwiki/server.py` (register)
- Test: `tests/test_recommendations.py` (add handler tests)

- [ ] **Step 1: Write failing handler test**

Append to `tests/test_recommendations.py`:

```python
async def test_handler_returns_success(mock_access_control, tmp_path):
    """Handler returns recommendations."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_recommendations,
    )

    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")
    result = await handle_get_recommendations({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "recommendations" in data
    assert "stats" in data


async def test_handler_missing_repo(mock_access_control, tmp_path):
    """Handler returns error for non-existent repo."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_recommendations,
    )

    result = await handle_get_recommendations(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_handler_enrich_no_llm_fallback(mock_access_control, tmp_path):
    """enrich=True with no LLM configured falls back to template-only."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_recommendations,
    )

    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")
    result = await handle_get_recommendations(
        {"repo_path": str(tmp_path), "enrich": True}
    )
    data = json.loads(result[0].text)
    # Should succeed with template-only results, no error
    assert data["status"] == "success"


async def test_enrich_adds_enriched_description():
    """enrich_recommendations adds enriched_description field via LLM."""
    from unittest.mock import AsyncMock

    from local_deepwiki.generators.analysis.recommendations import (
        enrich_recommendations,
    )

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value="Refactoring step details here.")

    recs = [{
        "title": "Extract helpers from parse_node",
        "category": "complexity",
        "description": "CC=23",
        "file": "src/parser.py",
        "line": 42,
        "effort": "low",
        "impact": "high",
        "priority": 3.0,
    }]
    result = await enrich_recommendations(recs, mock_provider)
    assert len(result) == 1
    assert "enriched_description" in result[0]
    assert "Refactoring" in result[0]["enriched_description"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_recommendations.py::test_handler_returns_success -v`
Expected: FAIL

- [ ] **Step 3: Add args model**

In `src/local_deepwiki/models/tool_args.py`, add after `GetOnboardingGuideArgs`:

```python
class GetRecommendationsArgs(BaseModel):
    """Arguments for the get_recommendations tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    max_items: int = Field(
        default=10,
        ge=1,
        le=50,
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

In `src/local_deepwiki/models/__init__.py`, add `GetRecommendationsArgs` to both the import and `__all__`.

- [ ] **Step 4: Add tool definition**

In `src/local_deepwiki/tool_defs/analysis.py`, add after `get_onboarding_guide`:

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
            "repo_path": {
                "type": "string",
                "description": "Path to the repository",
            },
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
),
```

- [ ] **Step 5: Add handler**

In `src/local_deepwiki/handlers/analysis_architecture.py`:

1. Add `GetRecommendationsArgs` to the import from `local_deepwiki.models`.

2. Add handler (after `handle_get_onboarding_guide`):

```python
@handle_tool_errors
async def handle_get_recommendations(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_recommendations tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetRecommendationsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.recommendations import (
        enrich_recommendations,
        generate_recommendations,
    )

    result = generate_recommendations(
        repo_path,
        max_items=validated.max_items,
        category_filter=validated.category_filter,
    )

    if validated.enrich and result["recommendations"]:
        try:
            from local_deepwiki.providers.llm import get_llm_provider

            provider = get_llm_provider()
            result = {
                **result,
                "recommendations": await enrich_recommendations(
                    result["recommendations"], provider
                ),
            }
        except Exception:
            logger.debug("LLM enrichment unavailable, using template-only")

    logger.info(
        "Recommendations: %d returned (of %d) in %s",
        result["stats"]["returned"],
        result["stats"]["total_findings"],
        repo_path,
    )
    return make_tool_text_content("get_recommendations", result)
```

- [ ] **Step 6: Export and register**

Same pattern as Task 2 Step 6 — add `handle_get_recommendations` to `analysis.py`, `__init__.py`, and `server.py`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_recommendations.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/models/__init__.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py src/local_deepwiki/handlers/analysis.py src/local_deepwiki/handlers/__init__.py src/local_deepwiki/server.py tests/test_recommendations.py
git commit -m "feat: add get_recommendations handler and tool registration"
```

---

### Task 5: Integrate recommendations into analyze_architecture composite

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/architecture_composite.py`
- Modify: `src/local_deepwiki/generators/analysis/architecture_report.py`
- Test: `tests/test_architecture_composite.py` (add integration tests)
- Test: `tests/test_architecture_report.py` (add formatter test)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_architecture_composite.py`:

```python
async def test_analyze_architecture_standard_has_recommendations_section(
    mock_access_control, simple_repo,
):
    """Standard detail report includes recommendations section when findings exist."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "detail_level": "standard"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    # The report may or may not have recommendations depending on repo findings,
    # but structure should be valid markdown
    assert "## Executive Summary" in data["report"]


async def test_analyze_architecture_summary_no_recommendations(
    mock_access_control, simple_repo,
):
    """Summary detail does NOT include recommendations section."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "detail_level": "summary"}
    )
    data = json.loads(result[0].text)
    assert "## Recommendations" not in data["report"]
```

Append to `tests/test_architecture_report.py`:

```python
def test_format_recommendations_section():
    """Recommendations are formatted as numbered list."""
    from local_deepwiki.generators.analysis.architecture_report import (
        _format_recommendations,
    )

    recs = [
        {
            "title": "Extract helpers from parse_node",
            "category": "complexity",
            "description": "CC=23, 145 lines",
            "file": "src/parser.py",
            "line": 42,
            "effort": "low",
            "impact": "high",
            "priority": 3.0,
        },
        {
            "title": "Split BigManager into focused components",
            "category": "smells",
            "description": "20 methods, 800 lines",
            "file": "src/big.py",
            "line": 1,
            "effort": "medium",
            "impact": "high",
            "priority": 1.5,
        },
    ]
    result = _format_recommendations(recs)
    assert "## Recommendations" in result
    assert "parse_node" in result
    assert "BigManager" in result
    assert "1." in result
    assert "2." in result


def test_format_recommendations_empty():
    """Empty recommendations returns empty string."""
    from local_deepwiki.generators.analysis.architecture_report import (
        _format_recommendations,
    )

    assert _format_recommendations([]) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_report.py::test_format_recommendations_section tests/test_architecture_composite.py::test_analyze_architecture_summary_no_recommendations -v`
Expected: FAIL

- [ ] **Step 3: Add `_format_recommendations` to report formatter**

In `src/local_deepwiki/generators/analysis/architecture_report.py`, add function:

```python
def _format_recommendations(recommendations: list[dict[str, Any]]) -> str:
    """Format recommendations as a numbered markdown list."""
    if not recommendations:
        return ""
    parts = ["## Recommendations\n"]
    for i, r in enumerate(recommendations, 1):
        parts.append(
            f"{i}. **{r['title']}** ({r['category']}, "
            f"effort: {r['effort']}, impact: {r['impact']})\n"
            f"   `{r['file']}:{r['line']}` — {r['description']}"
        )
    return "\n".join(parts)
```

Update `format_architecture_report` signature to accept recommendations:

```python
def format_architecture_report(
    health: dict[str, Any],
    deps: dict[str, Any] | None,
    *,
    detail_level: str = "standard",
    recommendations: list[dict[str, Any]] | None = None,
) -> str:
```

Add recommendations section after concerns, before deps:

```python
    sections.append(_format_strengths(health))
    sections.append(_format_concerns(health))
    if recommendations:
        sections.append(_format_recommendations(recommendations))
    if deps is not None:
        sections.append(_format_dependency_structure(deps))
```

- [ ] **Step 4: Update composite orchestrator**

In `src/local_deepwiki/generators/analysis/architecture_composite.py`, add after deps analysis and before `format_architecture_report`:

```python
    # Generate template-only recommendations (no LLM)
    recs_count = {"summary": 0, "standard": 5, "full": 10}.get(detail_level, 5)
    recommendations: list[dict[str, Any]] = []
    if recs_count > 0:
        from local_deepwiki.generators.analysis.recommendations import (
            generate_recommendations,
        )

        recs_result = generate_recommendations(
            repo_path, health_data=health, max_items=recs_count,
        )
        recommendations = recs_result.get("recommendations", [])
```

Update the `format_architecture_report` call to pass recommendations:

```python
    report = format_architecture_report(
        health, deps, detail_level=detail_level, recommendations=recommendations,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_architecture_report.py tests/test_architecture_composite.py -v`
Expected: All PASS

- [ ] **Step 6: Run full regression**

Run: `uv run pytest tests/test_architecture_composite.py tests/test_architecture_report.py tests/test_architecture_health.py tests/test_output_sizes.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/generators/analysis/architecture_composite.py src/local_deepwiki/generators/analysis/architecture_report.py tests/test_architecture_composite.py tests/test_architecture_report.py
git commit -m "feat: integrate template recommendations into analyze_architecture"
```

---

### Task 6: Add tool keywords and update CLAUDE.md

**Files:**
- Modify: `src/local_deepwiki/handlers/agentic_data.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add tool keywords**

In `src/local_deepwiki/handlers/agentic_data.py`, add to `_TOOL_KEYWORDS`:

```python
"get_onboarding_guide": [
    "onboard",
    "onboarding",
    "getting started",
    "new developer",
    "orientation",
    "entry point",
    "overview",
],
"get_recommendations": [
    "recommend",
    "recommendation",
    "refactor",
    "improve",
    "suggestion",
    "priority",
    "action",
    "fix",
],
```

- [ ] **Step 2: Update CLAUDE.md**

Update Analysis & Search Tools count from 11 to 13. Add `get_onboarding_guide` and `get_recommendations` to the tool list in the ASCII diagram and to the Analysis & Search Tools table.

Add to `generators/analysis/` component table:
```
| Onboarding | `analysis/onboarding.py` | Developer onboarding guide generator |
| Recommendations | `analysis/recommendations.py` | Prioritized refactoring recommendations |
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All pass (the pre-existing `test_wiki_output_quality` failure is unrelated)

- [ ] **Step 4: Commit**

```bash
git add src/local_deepwiki/handlers/agentic_data.py CLAUDE.md
git commit -m "docs: add tool keywords and update CLAUDE.md for Phase 2a tools"
```

---
