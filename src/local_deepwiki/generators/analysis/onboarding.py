"""Onboarding guide generator for repository newcomers.

Scans a repository to produce a structured onboarding guide covering
project overview, entry points, key modules, test layout, and configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from local_deepwiki.generators.dir_tree import get_directory_tree
from local_deepwiki.generators.manifest import ProjectManifest, get_cached_manifest
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OnboardingContext:
    """Immutable context for onboarding guide synthesis.

    Bundles the gathered project data passed through
    :func:`_build_onboarding_prompt_context` and
    :func:`_synthesize_onboarding_guide`.
    """

    manifest: ProjectManifest
    directory_tree: str
    entry_points: tuple[Path, ...] = ()
    codemaps: tuple[dict[str, Any], ...] = ()
    wiki_pages: tuple[str, ...] = ()
    test_layout: tuple[Path, ...] = ()
    config_files: tuple[Path, ...] = ()


# Well-known entry point filenames
ENTRY_POINT_PATTERNS: tuple[str, ...] = (
    "__main__.py",
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
)

# Well-known configuration files and directories
CONFIG_PATTERNS: tuple[str, ...] = (
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

# Maximum key modules by detail level
_KEY_MODULE_LIMITS: dict[str, int] = {
    "summary": 0,
    "standard": 5,
    "full": 8,
}

# Tree depth by detail level
_TREE_DEPTH: dict[str, int] = {
    "summary": 1,
    "standard": 3,
    "full": 5,
}


def _find_entry_points(repo_path: Path) -> list[Path]:
    """Discover entry point files by matching known filename patterns.

    Returns paths relative to repo_path, sorted alphabetically.
    """
    found: list[Path] = []
    for pattern in ENTRY_POINT_PATTERNS:
        for match in sorted(repo_path.rglob(pattern)):
            try:
                relative = match.relative_to(repo_path)
            except ValueError:
                continue
            # Skip hidden directories and common non-source locations
            parts = relative.parts
            if any(part.startswith(".") or part == "__pycache__" for part in parts):
                continue
            found.append(relative)
    return sorted(found)


def _find_key_modules(repo_path: Path, limit: int) -> list[dict[str, Any]]:
    """Identify key source modules by size (line count).

    Returns up to *limit* modules sorted by descending line count.
    Each entry has ``path`` (relative) and ``lines``.
    """
    if limit <= 0:
        return []

    source_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}
    modules: list[dict[str, Any]] = []

    for ext in source_extensions:
        for filepath in repo_path.rglob(f"*{ext}"):
            try:
                relative = filepath.relative_to(repo_path)
            except ValueError:
                continue
            parts = relative.parts
            if any(
                part.startswith(".") or part in ("__pycache__", "node_modules")
                for part in parts
            ):
                continue
            # Skip test files for key modules listing
            if any(part.startswith("test") for part in parts):
                continue
            try:
                line_count = len(filepath.read_text(errors="replace").splitlines())
            except OSError:
                continue
            modules.append({"path": relative, "lines": line_count})

    modules.sort(key=lambda m: m["lines"], reverse=True)
    return modules[:limit]


def _find_test_layout(repo_path: Path) -> list[Path]:
    """Find test directories and test files.

    Returns relative paths to directories containing test files.
    """
    test_dirs: set[Path] = set()
    test_patterns = ("test_*.py", "*_test.py", "test_*.ts", "*.test.ts", "*.spec.ts")

    for pattern in test_patterns:
        for match in repo_path.rglob(pattern):
            try:
                relative = match.relative_to(repo_path)
            except ValueError:
                continue
            parts = relative.parts
            if any(part.startswith(".") or part == "__pycache__" for part in parts):
                continue
            # Add the parent directory of the test file
            if len(relative.parts) > 1:
                test_dirs.add(Path(*relative.parts[:-1]))
            else:
                test_dirs.add(Path("."))

    return sorted(test_dirs)


def _find_config_files(repo_path: Path) -> list[Path]:
    """Discover configuration files and directories matching known patterns.

    Returns relative paths sorted alphabetically.
    """
    found: list[Path] = []
    for pattern in CONFIG_PATTERNS:
        candidate = repo_path / pattern
        if candidate.exists():
            found.append(Path(pattern))
    return sorted(found)


def generate_onboarding_guide(
    repo_path: Path, *, detail_level: str = "standard"
) -> dict[str, Any]:
    """Scan a repository and return structured onboarding data.

    Args:
        repo_path: Path to the repository root.
        detail_level: One of ``"summary"``, ``"standard"``, or ``"full"``.

    Returns:
        Dictionary with keys: ``manifest``, ``directory_tree``,
        ``entry_points``, ``key_modules``, ``test_layout``,
        ``config_files``, ``detail_level``.
    """
    tree_depth = _TREE_DEPTH.get(detail_level, 3)
    module_limit = _KEY_MODULE_LIMITS.get(detail_level, 5)

    manifest = get_cached_manifest(repo_path)
    directory_tree = get_directory_tree(repo_path, max_depth=tree_depth)
    entry_points = _find_entry_points(repo_path)
    key_modules = _find_key_modules(repo_path, limit=module_limit)
    test_layout = _find_test_layout(repo_path)
    config_files = _find_config_files(repo_path)

    return {
        "manifest": manifest,
        "directory_tree": directory_tree,
        "entry_points": entry_points,
        "key_modules": key_modules,
        "test_layout": test_layout,
        "config_files": config_files,
        "detail_level": detail_level,
    }


def _format_project_overview(manifest: ProjectManifest) -> str:
    """Format the Project Overview section."""
    lines = ["## Project Overview", ""]
    if manifest.name:
        lines.append(f"**{manifest.name}**")
        if manifest.version:
            lines[-1] += f" v{manifest.version}"
        lines.append("")
    if manifest.description:
        lines.append(manifest.description)
        lines.append("")
    tech_summary = manifest.get_tech_stack_summary()
    if tech_summary and tech_summary != "No package manifest found.":
        lines.append("### Tech Stack")
        lines.append("")
        lines.append(tech_summary)
        lines.append("")
    return "\n".join(lines)


def _format_getting_started(manifest: ProjectManifest) -> str:
    """Format the Getting Started section."""
    lines = ["## Getting Started", ""]
    if manifest.scripts:
        lines.append("Available scripts:")
        lines.append("")
        for name, cmd in sorted(manifest.scripts.items()):
            lines.append(f"- `{name}`: `{cmd}`")
        lines.append("")
    elif manifest.language:
        lines.append(f"This is a **{manifest.language}** project.")
        if manifest.manifest_files:
            lines.append(
                f"Check `{manifest.manifest_files[0]}` for build/run instructions."
            )
        lines.append("")
    else:
        lines.append(
            "No package manifest detected. Check the repository for setup instructions."
        )
        lines.append("")
    return "\n".join(lines)


def _format_repository_layout(directory_tree: str) -> str:
    """Format the Repository Layout section."""
    return "\n".join(
        [
            "## Repository Layout",
            "",
            "```",
            directory_tree,
            "```",
            "",
        ]
    )


def _format_entry_points(entry_points: list[Path]) -> str:
    """Format the Entry Points section."""
    lines = ["## Entry Points", ""]
    if entry_points:
        for ep in entry_points:
            lines.append(f"- `{ep}`")
    else:
        lines.append("No standard entry points detected.")
    lines.append("")
    return "\n".join(lines)


def _format_key_modules(key_modules: list[dict[str, Any]]) -> str:
    """Format the Key Modules section."""
    lines = ["## Key Modules", ""]
    if key_modules:
        lines.append("Largest source files (by line count):")
        lines.append("")
        for mod in key_modules:
            lines.append(f"- `{mod['path']}` ({mod['lines']} lines)")
    else:
        lines.append("No source modules detected.")
    lines.append("")
    return "\n".join(lines)


def _format_testing(test_layout: list[Path]) -> str:
    """Format the Testing section."""
    lines = ["## Testing", ""]
    if test_layout:
        lines.append("Test directories:")
        lines.append("")
        for td in test_layout:
            display = str(td) if str(td) != "." else "(root)"
            lines.append(f"- `{display}`")
    else:
        lines.append("No test files detected.")
    lines.append("")
    return "\n".join(lines)


def _format_configuration(config_files: list[Path]) -> str:
    """Format the Configuration section."""
    lines = ["## Configuration", ""]
    if config_files:
        for cf in config_files:
            lines.append(f"- `{cf}`")
    else:
        lines.append("No standard configuration files detected.")
    lines.append("")
    return "\n".join(lines)


def format_onboarding_guide(
    data: dict[str, Any], *, detail_level: str = "standard"
) -> str:
    """Format structured onboarding data into a markdown narrative.

    Args:
        data: Structured data from :func:`generate_onboarding_guide`.
        detail_level: One of ``"summary"``, ``"standard"``, or ``"full"``.

    Returns:
        Markdown string with appropriate sections for the detail level.
    """
    manifest: ProjectManifest = data["manifest"]
    sections = ["# Onboarding Guide", ""]

    # Always included: overview, getting started, layout
    sections.append(_format_project_overview(manifest))
    sections.append(_format_getting_started(manifest))
    sections.append(_format_repository_layout(data["directory_tree"]))

    if detail_level == "summary":
        return "\n".join(sections)

    # Standard and full: entry points, key modules, testing
    sections.append(_format_entry_points(data["entry_points"]))
    sections.append(_format_key_modules(data["key_modules"]))
    sections.append(_format_testing(data["test_layout"]))

    # Full only: configuration
    if detail_level == "full":
        sections.append(_format_configuration(data["config_files"]))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Rich onboarding (LLM + codemap powered)
# ---------------------------------------------------------------------------


def _build_flow_selection_prompt(
    manifest: ProjectManifest,
    entry_points: list[Path],
    directory_tree: str,
) -> str:
    """Construct the LLM prompt for selecting important newcomer flows."""
    entry_list = "\n".join(f"- {ep}" for ep in entry_points) or "- (none detected)"
    tech_stack = manifest.get_tech_stack_summary() or "Unknown"
    return (
        "You are helping a developer who is new to this codebase. "
        "Given the project structure below, pick the 3 most important "
        "execution flows a newcomer should understand first.\n\n"
        f"Project: {manifest.name or 'Unknown'}\n"
        f"Description: {manifest.description or 'No description'}\n"
        f"Tech stack: {tech_stack}\n\n"
        f"Entry points:\n{entry_list}\n\n"
        f"Directory structure:\n{directory_tree[:3000]}\n\n"
        "Return ONLY a JSON array of exactly 3 objects, each with:\n"
        '- "entry_point": function or filename to start tracing from\n'
        '- "query": a "How does X work?" question for the codemap\n'
        '- "title": short title for this flow (2-5 words)\n\n'
        "Return ONLY the JSON array, no other text."
    )


def _strip_code_fence(text: str) -> str:
    """Remove optional markdown code fence from LLM JSON output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return cleaned


def _parse_flow_json(raw: str) -> list[dict[str, str]] | None:
    """Parse LLM JSON response into a list of flow dicts, or return None on failure."""
    try:
        cleaned = _strip_code_fence(raw)
        flows = json.loads(cleaned)
        if isinstance(flows, list) and len(flows) > 0:
            return [
                {
                    "entry_point": f.get("entry_point", ""),
                    "query": f.get("query", ""),
                    "title": f.get("title", ""),
                }
                for f in flows[:3]
            ]
    except Exception:
        pass
    return None


def _fallback_flows(entry_points: list[Path]) -> list[dict[str, str]]:
    """Build heuristic flow list from entry points when LLM call fails."""
    fallback: list[dict[str, str]] = []
    for ep in entry_points[:3]:
        name = ep.stem
        fallback.append(
            {
                "entry_point": name,
                "query": f"How does {name} work?",
                "title": f"{name.replace('_', ' ').title()} Flow",
            }
        )
    return fallback


async def _select_flows_with_llm(
    llm: Any,
    manifest: ProjectManifest,
    entry_points: list[Path],
    directory_tree: str,
) -> list[dict[str, str]]:
    """Ask the LLM to pick the 3 most important flows for newcomers."""
    prompt = _build_flow_selection_prompt(manifest, entry_points, directory_tree)
    try:
        raw = await llm.generate(
            prompt, system_prompt="You are a code architecture expert."
        )
        parsed = _parse_flow_json(raw)
        if parsed is not None:
            return parsed
    except Exception:
        pass
    logger.warning("LLM flow selection failed, falling back to entry point heuristics")
    return _fallback_flows(entry_points)


async def _generate_codemaps_for_flows(
    flows: list[dict[str, str]],
    vector_store: Any,
    repo_path: Path,
    llm: Any,
) -> list[dict[str, Any]]:
    """Generate codemaps for each selected flow."""
    from local_deepwiki.generators.codemap.generator import generate_codemap

    results: list[dict[str, Any]] = []
    for flow in flows:
        try:
            codemap = await generate_codemap(
                query=flow["query"],
                vector_store=vector_store,
                repo_path=repo_path,
                llm=llm,
                entry_point=flow["entry_point"] or None,
                max_depth=5,
                max_nodes=30,
            )
            if codemap.total_nodes > 0:
                results.append(
                    {
                        "title": flow["title"],
                        "query": flow["query"],
                        "mermaid_diagram": codemap.mermaid_diagram,
                        "narrative": codemap.narrative,
                        "files_involved": codemap.files_involved,
                    }
                )
        except Exception:
            logger.warning("Codemap generation failed for %r", flow.get("query"))
    return results


def _format_codemap_text(codemaps: list[dict[str, Any]]) -> str:
    """Render codemap results into a text block for the onboarding prompt."""
    sections: list[str] = []
    for cm in codemaps:
        sections.append(
            f"### Flow: {cm['title']}\n"
            f"Question: {cm['query']}\n"
            f"Files: {', '.join(cm['files_involved'][:10])}\n\n"
            f"Mermaid diagram:\n{cm['mermaid_diagram']}\n\n"
            f"Narrative:\n{cm['narrative']}\n"
        )
    return "\n---\n".join(sections) if sections else "(no codemaps generated)"


def _join_paths_as_bullets(paths: list, default: str = "- (none detected)") -> str:
    """Join a list of paths as backtick bullet items, returning default when empty."""
    joined = "\n".join(f"- `{p}`" for p in paths)
    return joined if joined else default


def _build_onboarding_prompt_context(
    ctx: OnboardingContext,
) -> dict[str, str]:
    """Assemble all text substitutions needed for the onboarding synthesis prompt."""
    return {
        "codemap_text": _format_codemap_text(list(ctx.codemaps)),
        "entry_list": _join_paths_as_bullets(list(ctx.entry_points)),
        "test_list": _join_paths_as_bullets(list(ctx.test_layout)),
        "config_list": _join_paths_as_bullets(list(ctx.config_files)),
        "wiki_links": _join_paths_as_bullets(
            list(ctx.wiki_pages[:30]), default="- (none available)"
        ),
        "tech_stack": ctx.manifest.get_tech_stack_summary() or "Unknown",
        "project_name": ctx.manifest.name or "Unknown",
        "project_description": ctx.manifest.description or "No description",
    }


def _build_onboarding_synthesis_prompt(ctx: dict[str, str], directory_tree: str) -> str:
    """Format the full LLM prompt for onboarding guide synthesis."""
    return f"""Generate a comprehensive Developer Onboarding Guide for the project below.

PROJECT METADATA:
- Name: {ctx["project_name"]}
- Description: {ctx["project_description"]}
- Tech stack: {ctx["tech_stack"]}

ENTRY POINTS:
{ctx["entry_list"]}

DIRECTORY STRUCTURE:
{directory_tree[:3000]}

EXECUTION FLOW DIAGRAMS (include these verbatim):
{ctx["codemap_text"]}

AVAILABLE WIKI PAGES (use for linking):
{ctx["wiki_links"]}

TEST LAYOUT:
{ctx["test_list"]}

CONFIGURATION FILES:
{ctx["config_list"]}

INSTRUCTIONS:
Produce a single markdown document with these sections:

1. **What This Project Does** -- 2-3 paragraphs explaining the purpose, who it's for, \
and what problem it solves. Write narrative prose, not bullet lists.

2. **Architecture at a Glance** -- A Mermaid component diagram showing how the main \
subsystems connect. Below the diagram, briefly describe each layer and link to wiki pages \
where available using relative links like `[ComponentName](files/path/to/file.md)`.

3. **How It Works** -- For each execution flow diagram provided above, create a subsection \
with:
   - The flow title as an H3 heading
   - The Mermaid diagram inlined VERBATIM (do not modify it)
   - A narrative walkthrough that references wiki pages with links like \
`[FileName](files/path/to/file.md)`

4. **Getting Started** -- Prerequisites, install commands, how to run. Based on the tech \
stack and config files.

5. **Key Concepts** -- A markdown table of important terms/concepts a newcomer needs to \
know, derived from the code entities visible in the execution flows.

6. **Development Workflow** -- How to run tests, lint, and do common development tasks. \
Based on the test layout and config files.

7. **Further Reading** -- Links to Architecture, Dependencies, Glossary, and Changelog wiki \
pages using relative links: `[Architecture](architecture.md)`, \
`[Dependencies](dependencies.md)`, `[Glossary](glossary.md)`, `[Changelog](changelog.md)`.

CRITICAL RULES:
- Use relative wiki links for file references: `[Name](files/path/to/file.md)`
- Inline Mermaid diagrams from the execution flows VERBATIM -- do not regenerate them
- Write narrative prose, not bullet lists, for descriptive sections
- The Key Concepts table should have columns: Concept | What It Means
- Start the document with `# Developer Onboarding Guide`
"""


async def _synthesize_onboarding_guide(
    llm: Any,
    ctx: OnboardingContext,
) -> str:
    """Ask the LLM to synthesize the full onboarding guide."""
    prompt_ctx = _build_onboarding_prompt_context(ctx)
    prompt = _build_onboarding_synthesis_prompt(prompt_ctx, ctx.directory_tree)
    return await llm.generate(
        prompt,
        system_prompt="You are a technical writer creating developer documentation.",
    )


async def generate_rich_onboarding(
    repo_path: Path,
    vector_store: Any,
    llm: Any,
    *,
    detail_level: str = "full",
) -> dict[str, Any]:
    """Generate a rich onboarding guide with diagrams, narrative, and wiki links.

    Requires prior indexing -- uses vector store for codemap generation
    and LLM for flow selection and synthesis.

    Args:
        repo_path: Path to the indexed repository.
        vector_store: Initialized VectorStore instance.
        llm: LLM provider for flow selection and synthesis.
        detail_level: Detail level (currently always produces full output).

    Returns:
        Dict with ``status``, ``guide`` (markdown string), and ``codemaps``
        (list of codemap dicts).
    """
    basics = generate_onboarding_guide(repo_path, detail_level=detail_level)
    manifest: ProjectManifest = basics["manifest"]
    entry_points: list[Path] = basics["entry_points"]
    directory_tree: str = basics["directory_tree"]
    test_layout: list[Path] = basics["test_layout"]
    config_files: list[Path] = basics["config_files"]

    flows = await _select_flows_with_llm(llm, manifest, entry_points, directory_tree)

    codemaps = await _generate_codemaps_for_flows(flows, vector_store, repo_path, llm)

    wiki_path = repo_path / ".deepwiki"
    wiki_pages: list[str] = []
    if wiki_path.exists():
        for md_file in sorted(wiki_path.rglob("*.md")):
            try:
                wiki_pages.append(str(md_file.relative_to(wiki_path)))
            except ValueError:
                continue

    onboarding_ctx = OnboardingContext(
        manifest=manifest,
        directory_tree=directory_tree,
        entry_points=tuple(entry_points),
        codemaps=tuple(codemaps),
        wiki_pages=tuple(wiki_pages),
        test_layout=tuple(test_layout),
        config_files=tuple(config_files),
    )
    guide = await _synthesize_onboarding_guide(llm, onboarding_ctx)

    return {
        "status": "success",
        "guide": guide,
        "codemaps": codemaps,
    }
