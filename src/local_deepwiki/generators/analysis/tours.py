"""Guided tour generator for codebase exploration.

Generates topic-focused reading guides with ordered file stops
and explanations. Template-based by default; optional LLM enrichment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# File name patterns for topic detection
_TOPIC_PATTERNS: dict[str, list[str]] = {
    "data_flow": [
        "indexer",
        "pipeline",
        "processor",
        "store",
        "database",
        "ingest",
        "transform",
        "loader",
        "import",
        "export",
    ],
    "request_handling": [
        "server",
        "handler",
        "route",
        "app",
        "middleware",
        "api",
        "endpoint",
        "view",
        "controller",
    ],
    "testing": [
        "conftest",
        "fixture",
        "test_",
        "mock",
        "factory",
    ],
    "architecture": [
        "server",
        "handler",
        "core",
        "model",
        "provider",
        "generator",
        "cli",
        "web",
        "plugin",
    ],
}

_TOPIC_TITLES: dict[str, str] = {
    "architecture": "Architecture Overview",
    "data_flow": "How Data Flows Through the System",
    "request_handling": "Request Handling Lifecycle",
    "testing": "Testing Organization and Patterns",
}

_MODULE_EXPLANATIONS: dict[str, str] = {
    "server": "Entry point where requests arrive and are dispatched.",
    "handler": "Request handlers that orchestrate business logic.",
    "core": "Core domain logic and shared utilities.",
    "model": "Data models and domain objects.",
    "provider": "External service integrations (LLM, embedding, etc.).",
    "generator": "Content and analysis generators.",
    "cli": "Command-line interface entry points.",
    "web": "Web UI routes and templates.",
    "plugin": "Extension points and plugin interfaces.",
    "test": "Test infrastructure and fixtures.",
    "conftest": "Shared test fixtures and configuration.",
}


def generate_tour(
    repo_path: Path,
    *,
    topic: str = "architecture",
    max_stops: int = 10,
    enrich: bool = False,
) -> dict[str, Any]:
    """Generate a guided tour of the codebase.

    Args:
        repo_path: Path to the repository root.
        topic: Tour topic (architecture, data_flow, request_handling, testing).
        max_stops: Maximum number of stops.

    Returns:
        Dict with status, topic, title, stops list, and summary.
    """
    # Resolve topic patterns
    if topic.startswith("custom:"):
        query = topic[7:].lower()
        patterns = query.split()
    else:
        patterns = _TOPIC_PATTERNS.get(topic, _TOPIC_PATTERNS["architecture"])

    title = _TOPIC_TITLES.get(topic, f"Tour: {topic}")

    # Scan for matching files
    stops = _find_tour_stops(repo_path, patterns, topic)
    stops = stops[:max_stops]

    summary = _generate_summary(topic, stops)

    return {
        "status": "success",
        "topic": topic,
        "title": title,
        "stops": stops,
        "summary": summary,
        "tool": "get_guided_tour",
    }


def _find_tour_stops(
    repo_path: Path,
    patterns: list[str],
    topic: str,
) -> list[dict[str, Any]]:
    """Find and order tour stops by relevance and dependency flow."""
    scored: list[tuple[int, str, dict[str, Any]]] = []

    for py_file in sorted(repo_path.rglob("*.py")):
        try:
            rel = py_file.relative_to(repo_path)
        except ValueError:
            continue
        parts = rel.parts
        if any(
            p.startswith(".") or p in ("node_modules", "__pycache__") for p in parts
        ):
            continue

        file_str = str(rel)
        stem = py_file.stem
        module = _file_to_module(rel)

        # Score by pattern match
        score = 0
        for pattern in patterns:
            if pattern in stem.lower():
                score += 2
            if pattern in file_str.lower():
                score += 1

        if score > 0:
            explanation = _explain_file(stem, module, topic)
            stop = {
                "file": file_str,
                "module": module,
                "section": stem,
                "explanation": explanation,
                "line": 1,
            }
            scored.append((-score, file_str, stop))

    # Sort by score descending (negative score), then by path for stability
    scored.sort(key=lambda t: (t[0], t[1]))

    return [entry[2] for entry in scored]


def _file_to_module(rel_path: Path) -> str:
    """Convert relative file path to a module name."""
    parts = list(rel_path.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else "root"


def _explain_file(stem: str, module: str, topic: str) -> str:
    """Generate a template explanation for a file."""
    for key, explanation in _MODULE_EXPLANATIONS.items():
        if key in stem.lower() or key in module.lower():
            return explanation

    return f"Part of the {module} module."


def _generate_summary(topic: str, stops: list[dict[str, Any]]) -> str:
    """Generate a summary sentence for the tour."""
    if not stops:
        return "No relevant files found for this topic."

    modules = list(dict.fromkeys(s["module"].split(".")[0] for s in stops))
    module_list = ", ".join(modules[:5])

    summaries = {
        "architecture": f"The codebase is organized around {len(modules)} key areas: {module_list}.",
        "data_flow": f"Data flows through {len(stops)} processing stages across {module_list}.",
        "request_handling": f"Requests are handled through a {len(stops)}-step pipeline: {module_list}.",
        "testing": f"Tests are organized across {len(stops)} files covering {module_list}.",
    }
    return summaries.get(
        topic, f"This tour covers {len(stops)} files in {module_list}."
    )
