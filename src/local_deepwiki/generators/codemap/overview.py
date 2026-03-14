"""Overview mode: module-level architecture graph with LLM labeling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverviewModule:
    """A module (directory-level group) in the architecture overview."""

    id: str
    label: str
    description: str
    files: tuple[str, ...]
    function_count: int
    hub_functions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OverviewEdge:
    """A relationship between two modules."""

    source: str
    target: str
    weight: int
    description: str


@dataclass(frozen=True, slots=True)
class OverviewResult:
    """Complete overview graph with modules, edges, and summary."""

    modules: tuple[OverviewModule, ...]
    edges: tuple[OverviewEdge, ...]
    summary: str
