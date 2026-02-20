"""Wiki page generators for specific documentation pages."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.diagrams import generate_workflow_sequences
from local_deepwiki.generators.manifest import ProjectManifest, get_directory_tree
from local_deepwiki.logging import get_logger
from local_deepwiki.models import IndexStatus, WikiPage
from local_deepwiki.providers.base import LLMProvider

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Filenames to check for authoritative project descriptions, in priority order.
_AUTHORITATIVE_DOC_NAMES = [
    "CLAUDE.md",
    "README.md",
    "README.rst",
    "README.txt",
    "README",
]

# Maximum characters to include from authoritative docs to stay within
# reasonable prompt budgets while still capturing the project overview.
_MAX_AUTHORITATIVE_CHARS = 8000


def _read_authoritative_docs(repo_path: Path | None) -> str | None:
    """Read authoritative project documentation for LLM grounding.

    Checks for CLAUDE.md and README files in the repo root. Returns the
    first found, truncated to a reasonable size.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Content string if found, None otherwise.
    """
    if repo_path is None:
        return None

    for name in _AUTHORITATIVE_DOC_NAMES:
        doc_path = repo_path / name
        if doc_path.is_file():
            try:
                content = doc_path.read_text(encoding="utf-8")
                if content.strip():
                    logger.debug("Using %s as authoritative project doc", name)
                    truncated = content[:_MAX_AUTHORITATIVE_CHARS]
                    if len(content) > _MAX_AUTHORITATIVE_CHARS:
                        truncated += "\n\n[... truncated]"
                    return truncated
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Could not read %s: %s", name, e)

    return None


def _build_tech_stack_section(manifest: ProjectManifest, max_deps: int = 12) -> str:
    """Build technology stack section from manifest.

    Args:
        manifest: Project manifest with dependencies.
        max_deps: Maximum dependencies to list.

    Returns:
        Markdown section for tech stack.
    """
    if not manifest.dependencies:
        return ""

    lines = ["\n## Technology Stack\n"]
    if manifest.language:
        lang_str = manifest.language
        if manifest.language_version:
            lang_str += f" {manifest.language_version}"
        lines.append(f"- **{lang_str}**")

    key_deps = sorted(manifest.dependencies.keys())
    if key_deps:
        lines.append(f"- **Dependencies**: {', '.join(key_deps[:max_deps])}")
        if len(key_deps) > max_deps:
            lines.append(f"  - Plus {len(key_deps) - max_deps} more...")

    return "\n".join(lines)


def _build_directory_section(repo_path: Path) -> str:
    """Build directory structure section.

    Args:
        repo_path: Path to repository root.

    Returns:
        Markdown section for directory structure.
    """
    dir_tree = get_directory_tree(repo_path, max_depth=2, max_items=25)
    return f"\n## Directory Structure\n\n```\n{dir_tree}\n```"


def _build_quick_start_section(manifest: ProjectManifest) -> str:
    """Build quick start section from entry points.

    Args:
        manifest: Project manifest with entry points.

    Returns:
        Markdown section for quick start.
    """
    if not manifest.entry_points:
        return ""

    lines = ["\n## Quick Start\n"]
    for cmd, target in sorted(manifest.entry_points.items()):
        lines.append(f"- `{cmd}` → `{target}`")
    return "\n".join(lines)


async def _gather_code_context(
    vector_store: VectorStore,
    max_chunk_content_chars: int = 15000,
) -> list[str]:
    """Search for main entry points and key classes for context.

    Args:
        vector_store: Vector store for code search.
        max_chunk_content_chars: Max characters of chunk content in LLM prompt.

    Returns:
        List of formatted code context strings.
    """
    entry_search, key_class_search = await asyncio.gather(
        vector_store.search("main entry point init server app", limit=10),
        vector_store.search("class main core primary", limit=10),
    )

    seen_paths: set[str] = set()
    code_parts: list[str] = []
    for r in entry_search + key_class_search:
        if r.chunk.file_path not in seen_paths and len(code_parts) < 16:
            seen_paths.add(r.chunk.file_path)
            code_parts.append(
                f"File: {r.chunk.file_path}\n"
                f"Type: {r.chunk.chunk_type.value}\n"
                f"Name: {r.chunk.name}\n"
                f"```\n{r.chunk.content[:max_chunk_content_chars]}\n```"
            )
    return code_parts


def _build_overview_prompt(
    pre_generated: str,
    code_samples: str,
    authoritative_docs: str | None = None,
) -> str:
    """Build the LLM prompt for overview generation.

    Args:
        pre_generated: Already-generated content sections.
        code_samples: Formatted code samples for context.
        authoritative_docs: Optional high-priority project documentation
            (CLAUDE.md, README.md) that should be weighted heavily.

    Returns:
        Formatted prompt for LLM.
    """
    auth_section = ""
    auth_rule = ""
    if authoritative_docs:
        auth_section = f"""
AUTHORITATIVE PROJECT DOCUMENTATION (HIGH PRIORITY — the project maintainer wrote this):
{authoritative_docs}
"""
        auth_rule = (
            "- The AUTHORITATIVE PROJECT DOCUMENTATION is the most reliable source "
            "of truth. Align your description and features with it. Code samples "
            "provide supporting detail but should not contradict the authoritative docs.\n"
        )

    return f"""You are filling in sections of a README. Some sections are already written below. You need to write the "## Description" and "## Key Features" sections ONLY.

ALREADY WRITTEN (do not modify):
{pre_generated}
{auth_section}
CODE SAMPLES FOR CONTEXT:
{code_samples}

YOUR TASK:
Write ONLY these two sections:

1. **## Description** (2-3 sentences explaining what this project does)

2. **## Key Features** (bullet list of 3-5 features you can VERIFY from the sources shown)

RULES:
{auth_rule}- ONLY describe functionality visible in the provided sources
- Do NOT invent features not shown
- Do NOT mention libraries not in the Technology Stack section
- Keep it factual and grounded

Return ONLY the Description and Key Features sections as markdown."""


async def generate_overview_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    *,
    manifest: ProjectManifest | None,
    repo_path: Path | None,
    max_chunk_content_chars: int = 15000,
) -> WikiPage:
    """Generate the main overview/index page with grounded facts.

    This method generates structured sections programmatically (tech stack,
    directory structure, quick start) to avoid LLM hallucination, and only
    uses the LLM to generate the description and features sections.

    Args:
        index_status: Index status with repository information.
        vector_store: Vector store for code search.
        llm: LLM provider for content generation.
        system_prompt: System prompt for the LLM.
        manifest: Parsed project manifest (dependencies, entry points).
        repo_path: Path to the repository root.
        max_chunk_content_chars: Max characters of chunk content in LLM prompt.

    Returns:
        WikiPage with overview content.
    """
    repo_name = Path(index_status.repo_path).name

    # Gather code context for LLM
    code_context_parts = await _gather_code_context(
        vector_store, max_chunk_content_chars
    )
    code_samples = (
        "\n\n".join(code_context_parts)
        if code_context_parts
        else "No code samples available."
    )

    # Read authoritative project docs (CLAUDE.md, README.md, etc.)
    authoritative_docs = _read_authoritative_docs(repo_path)

    # Build pre-generated sections for LLM context
    prompt_parts = [f"# {repo_name}\n"]
    if manifest and manifest.description:
        prompt_parts.append(f"\n{manifest.description}\n")
    prompt_parts.append(
        '\nBased on the code samples below, write a "## Key Features" section '
        "listing 3-5 features you can VERIFY from the actual code.\n"
    )
    if manifest:
        tech_section = _build_tech_stack_section(manifest, max_deps=10)
        if tech_section:
            prompt_parts.append(tech_section)
    if repo_path:
        prompt_parts.append(_build_directory_section(repo_path) + "\n")
    if manifest:
        qs_section = _build_quick_start_section(manifest)
        if qs_section:
            prompt_parts.append(qs_section)

    pre_generated = "\n".join(prompt_parts)
    prompt = _build_overview_prompt(pre_generated, code_samples, authoritative_docs)
    llm_content = await llm.generate(prompt, system_prompt=system_prompt)

    # Build final content
    final_parts = [f"# {repo_name}\n"]
    if manifest and manifest.description:
        final_parts.append(f"\n{manifest.description}\n")
    final_parts.append(llm_content)
    if manifest:
        tech_section = _build_tech_stack_section(manifest)
        if tech_section:
            final_parts.append(tech_section)
    if repo_path:
        final_parts.append(_build_directory_section(repo_path))
    if manifest:
        qs_section = _build_quick_start_section(manifest)
        if qs_section:
            final_parts.append(qs_section)

    return WikiPage(
        path="index.md",
        title="Overview",
        content="\n".join(final_parts),
        generated_at=time.time(),
    )


async def generate_architecture_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    *,
    manifest: ProjectManifest | None,
    repo_path: Path | None,
    max_chunk_content_chars: int = 15000,
) -> WikiPage:
    """Generate architecture documentation with diagrams and grounded facts.

    Args:
        index_status: Index status with repository information.
        vector_store: Vector store for code search.
        llm: LLM provider for content generation.
        system_prompt: System prompt for the LLM.
        manifest: Parsed project manifest.
        repo_path: Path to the repository root.
        max_chunk_content_chars: Max characters of chunk content in LLM prompt.

    Returns:
        WikiPage with architecture documentation.
    """
    # Read authoritative project docs (CLAUDE.md, README.md, etc.)
    authoritative_docs = _read_authoritative_docs(repo_path)

    # Gather multiple types of context for comprehensive architecture view (parallel)
    core_results, pattern_results, flow_results, class_results = await asyncio.gather(
        # 1. Search for core/main components
        vector_store.search("main core primary class module", limit=15),
        # 2. Search for architectural patterns
        vector_store.search("factory provider service handler controller", limit=10),
        # 3. Search for data flow / pipeline
        vector_store.search("process pipeline flow parse index generate", limit=10),
        # 4. Get all classes for class list
        vector_store.search("class def __init__", limit=30),
    )

    # Combine and deduplicate results
    seen_chunks = set()
    all_chunks = []
    for r in core_results + pattern_results + flow_results:
        chunk_key = (r.chunk.file_path, r.chunk.name)
        if chunk_key not in seen_chunks:
            seen_chunks.add(chunk_key)
            all_chunks.append(r)

    # Build detailed context with more content per chunk
    context_parts = []
    for r in all_chunks[:40]:
        context_parts.append(
            f"File: {r.chunk.file_path}\n"
            f"Type: {r.chunk.chunk_type.value}\n"
            f"Name: {r.chunk.name}\n"
            f"```\n{r.chunk.content[:max_chunk_content_chars]}\n```"
        )

    code_context = "\n\n".join(context_parts)

    # Extract class names for reference
    class_names = set()
    for r in class_results:
        if r.chunk.chunk_type.value == "class" and r.chunk.name:
            class_names.add(r.chunk.name)

    class_list = (
        ", ".join(sorted(class_names)[:30]) if class_names else "No classes found"
    )

    # Include directory structure for module organization
    dir_structure = ""
    if repo_path:
        dir_structure = get_directory_tree(repo_path, max_depth=2, max_items=25)

    # Include dependencies for technology context
    dep_context = ""
    if manifest and manifest.dependencies:
        dep_context = "Key dependencies: " + ", ".join(
            sorted(manifest.dependencies.keys())[:15]
        )

    auth_section = ""
    if authoritative_docs:
        auth_section = f"""AUTHORITATIVE PROJECT DOCUMENTATION (HIGH PRIORITY — the project maintainer wrote this):
{authoritative_docs}

"""

    prompt = f"""Generate architecture documentation based ONLY on the code provided below.

{auth_section}CLASSES FOUND IN CODEBASE:
{class_list}

DIRECTORY STRUCTURE:
```
{dir_structure}
```

{dep_context}

CODE CONTEXT:
{code_context}

Generate documentation that includes:
1. **System Overview** - Describe how the system works based on the classes and code shown
2. **Key Components** - For each major class shown in the code, explain its responsibility. Write class names as plain text in sentences (not in backticks) so they can be cross-linked.
3. **Data Flow** - Explain how data moves through the components based on what you see in the code
4. **Component Diagram** - Create a Mermaid diagram (```mermaid) showing relationships between the classes you found. Only include classes that actually exist in the code.
5. **Key Design Decisions** - Describe architectural choices visible in the code

CRITICAL CONSTRAINTS:
- ONLY describe classes and components that are shown in the code above
- ONLY mention design patterns if you can point to specific classes implementing them
- Do NOT invent components, patterns, or data flows not shown in the code
- If you're uncertain about a relationship, omit it rather than guess
- Write class names as plain text (e.g., "The WikiGenerator class") so they can be cross-linked

Format as markdown with clear sections."""

    content = await llm.generate(prompt, system_prompt=system_prompt)

    # Add workflow sequence diagrams
    content += "\n\n## Workflow Sequences\n\n"
    content += "The following diagrams show how data flows through key operations:\n\n"
    content += generate_workflow_sequences()

    # Add link to detailed dependency graph
    content += "\n\n## Module Dependencies\n\n"
    content += (
        "For a detailed view of module interdependencies including circular dependency "
    )
    content += "detection, see the [Dependency Graph](dependency-graph.md) page.\n"

    return WikiPage(
        path="architecture.md",
        title="Architecture",
        content=content,
        generated_at=time.time(),
    )


async def generate_dependencies_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    *,
    manifest: ProjectManifest | None,
    import_search_limit: int,
) -> tuple[WikiPage, list[str]]:
    """Generate dependencies documentation with grounded facts from manifest.

    Args:
        index_status: Index status with repository information.
        vector_store: Vector store for code search.
        llm: LLM provider for content generation.
        system_prompt: System prompt for the LLM.
        manifest: Parsed project manifest.
        import_search_limit: Max import chunks to search.

    Returns:
        Tuple of (WikiPage, list of source files that contributed).
    """
    from local_deepwiki.generators.diagrams import generate_dependency_graph

    # Build grounded dependency context
    facts_sections = []

    # 1. External dependencies from manifest (GROUNDED FACTS)
    if manifest and manifest.dependencies:
        deps_list = []
        for name, version in sorted(manifest.dependencies.items()):
            version_str = f" ({version})" if version and version != "*" else ""
            deps_list.append(f"- {name}{version_str}")
        facts_sections.append(
            "EXTERNAL DEPENDENCIES (from package manifest):\n"
            + "\n".join(deps_list[:30])
        )

    # 2. Dev dependencies from manifest (GROUNDED FACTS)
    if manifest and manifest.dev_dependencies:
        dev_deps_list = []
        for name, version in sorted(manifest.dev_dependencies.items()):
            version_str = f" ({version})" if version and version != "*" else ""
            dev_deps_list.append(f"- {name}{version_str}")
        facts_sections.append(
            "DEV DEPENDENCIES (from package manifest):\n"
            + "\n".join(dev_deps_list[:20])
        )

    # 3. Get import chunks for internal dependency analysis
    # Use higher limit to capture more modules for a complete dependency graph
    search_results = await vector_store.search(
        "import require include from",
        limit=500,
    )

    import_chunks = [r for r in search_results if r.chunk.chunk_type.value == "import"]

    # Collect source files from import chunks, prioritizing non-test files
    seen_files: set[str] = set()
    source_files: list[str] = []
    test_files: list[str] = []

    for r in import_chunks:
        file_path = r.chunk.file_path
        if file_path not in seen_files:
            seen_files.add(file_path)
            if "/test" in file_path or file_path.startswith("test"):
                test_files.append(file_path)
            else:
                source_files.append(file_path)

    # Combine: source files first, then test files
    all_relevant_files = source_files + test_files

    # Build import context
    import_context = "\n\n".join(
        [f"File: {r.chunk.file_path}\n{r.chunk.content}" for r in import_chunks[:25]]
    )

    if import_context:
        facts_sections.append(f"IMPORT STATEMENTS FROM CODE:\n{import_context}")

    grounded_context = "\n\n".join(facts_sections)

    prompt = f"""Generate a dependencies overview based ONLY on the facts provided below.

{grounded_context}

Generate documentation that includes:
1. **External Dependencies** - List the third-party libraries shown in the manifest above and briefly explain their purpose (infer from common knowledge about these libraries)
2. **Dev Dependencies** - List development dependencies if shown
3. **Internal Module Dependencies** - Based on the import statements, describe how internal modules depend on each other. Write class names as plain text for cross-linking.

CRITICAL CONSTRAINTS:
- ONLY list dependencies that appear in the manifest or imports above
- Do NOT invent or guess additional dependencies
- For internal dependencies, only describe relationships visible in the import statements
- When mentioning class names, write them as plain text (e.g., "WikiGenerator depends on VectorStore")
- Do NOT include a Mermaid diagram - one will be auto-generated

Format as markdown."""

    content = await llm.generate(prompt, system_prompt=system_prompt)

    # Generate auto-generated module dependency graph with enhanced features
    dep_graph = generate_dependency_graph(
        import_chunks,
        "local_deepwiki",
        detect_circular=True,
        show_external=True,
        max_external=10,
        wiki_base_path="files/",
    )
    if dep_graph:
        content += "\n\n## Module Dependency Graph\n\n"
        content += "The following diagram shows module dependencies. "
        content += "Click on a module to view its documentation. "
        content += "External dependencies are shown with dashed borders.\n\n"
        content += dep_graph

    page = WikiPage(
        path="dependencies.md",
        title="Dependencies",
        content=content,
        generated_at=time.time(),
    )
    return page, all_relevant_files


async def generate_changelog_page(repo_path: Path | None) -> WikiPage | None:
    """Generate changelog page from git history.

    Args:
        repo_path: Path to the repository root.

    Returns:
        WikiPage with changelog content, or None if not a git repo.
    """
    if repo_path is None:
        return None

    from local_deepwiki.generators.changelog import generate_changelog_content

    content = generate_changelog_content(repo_path)
    if not content:
        logger.debug("No changelog generated (not a git repo or no commits)")
        return None

    return WikiPage(
        path="changelog.md",
        title="Changelog",
        content=content,
        generated_at=time.time(),
    )
