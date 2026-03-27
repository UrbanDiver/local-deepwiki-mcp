"""Tests for the onboarding guide generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from local_deepwiki.generators.analysis.onboarding import (
    format_onboarding_guide,
    generate_onboarding_guide,
)


@pytest.fixture
def synthetic_repo(tmp_path):
    """Create a synthetic repository structure for testing."""
    repo = tmp_path / "myproject"
    repo.mkdir()

    # pyproject.toml
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.0.0"\n'
        'description = "A test application"\n'
    )

    # Source package
    src = repo / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""My application."""\n')
    (src / "__main__.py").write_text(
        '"""Entry point."""\nif __name__ == "__main__":\n    pass\n'
    )
    (src / "cli.py").write_text('"""CLI interface."""\n')
    (src / "server.py").write_text('"""Server entry point."""\n')
    (src / "utils.py").write_text('"""Utilities."""\n')

    # Core subpackage
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "engine.py").write_text('"""Core engine."""\n')

    # Tests directory
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_utils.py").write_text('"""Tests for utils."""\n')

    # CI/CD and config files
    workflows = repo / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n")

    (repo / "Dockerfile").write_text("FROM python:3.12\n")

    return repo


def test_generate_onboarding_guide_standard(synthetic_repo):
    """Standard detail level returns all main sections."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="standard")

    assert "manifest" in data
    assert "directory_tree" in data
    assert "entry_points" in data
    assert "key_modules" in data
    assert "test_layout" in data
    assert "detail_level" in data
    assert data["detail_level"] == "standard"


def test_generate_onboarding_guide_has_entry_points(synthetic_repo):
    """Detects __main__.py and server.py as entry points."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="standard")

    entry_point_paths = [str(ep) for ep in data["entry_points"]]
    # Should find __main__.py and server.py (and cli.py)
    assert any("__main__.py" in p for p in entry_point_paths)
    assert any("server.py" in p for p in entry_point_paths)


def test_format_onboarding_guide_standard(synthetic_repo):
    """Formatted markdown has expected section headers for standard level."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="standard")
    md = format_onboarding_guide(data, detail_level="standard")

    assert "# Onboarding Guide" in md
    assert "## Project Overview" in md
    assert "## Getting Started" in md
    assert "## Repository Layout" in md
    assert "## Entry Points" in md
    assert "## Key Modules" in md
    assert "## Testing" in md


def test_format_onboarding_guide_summary(synthetic_repo):
    """Summary level only includes overview, getting started, and layout."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="summary")
    md = format_onboarding_guide(data, detail_level="summary")

    assert "## Project Overview" in md
    assert "## Getting Started" in md
    assert "## Repository Layout" in md
    # Should NOT include detailed sections
    assert "## Entry Points" not in md
    assert "## Key Modules" not in md
    assert "## Testing" not in md
    assert "## Configuration" not in md


def test_format_onboarding_guide_full(synthetic_repo):
    """Full level includes configuration section."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="full")
    md = format_onboarding_guide(data, detail_level="full")

    assert "## Configuration" in md
    assert "## Entry Points" in md
    assert "## Key Modules" in md
    assert "## Testing" in md


def test_generate_onboarding_guide_empty_repo(tmp_path):
    """Empty repo returns graceful minimal data without errors."""
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()

    data = generate_onboarding_guide(empty_repo, detail_level="standard")

    assert data["entry_points"] == []
    assert data["key_modules"] == []
    assert data["test_layout"] == []
    assert data["directory_tree"]  # Should still have a tree (just the root)
    assert data["manifest"] is not None

    # Formatting should also work gracefully
    md = format_onboarding_guide(data, detail_level="standard")
    assert "# Onboarding Guide" in md
