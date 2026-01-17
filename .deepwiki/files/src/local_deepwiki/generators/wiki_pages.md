# Wiki Pages Generator

## File Overview

The `wiki_pages.py` module is responsible for generating various types of wiki pages for documentation. Based on the code shown, it handles the creation of changelog pages from git repository history and appears to support other page types like overview and architecture pages.

## Functions

### generate_changelog_page

```python
async def generate_changelog_page(repo_path: Path | None) -> WikiPage | None
```

Generates a changelog page from git repository history.

**Parameters:**
- `repo_path`: Path to the repository root, can be None

**Returns:**
- [WikiPage](../models.md) object containing the changelog content, or None if the repository is not a git repository

**Behavior:**
- Returns None immediately if no repository path is provided
- Uses the [`generate_changelog_content`](changelog.md) function from the changelog generator module
- Returns None if no changelog content is generated (not a git repo or no commits)
- Creates and returns a [WikiPage](../models.md) object when changelog content is successfully generated

### Other Functions

The module also contains additional functions that are referenced but not fully shown in the provided code:
- `generate_overview_page`
- `generate_arch` (likely generates architecture documentation)

## Related Components

This module integrates with several other components of the local_deepwiki system:

- **[VectorStore](../core/vectorstore.md)**: From `local_deepwiki.core.vectorstore` for vector storage operations
- **[WikiPage](../models.md)**: From `local_deepwiki.models` as the return type for generated pages
- **[IndexStatus](../models.md)**: From `local_deepwiki.models` for tracking indexing status
- **[LLMProvider](../providers/base.md)**: From `local_deepwiki.providers.base` for language model operations
- **[ProjectManifest](manifest.md)**: From `local_deepwiki.generators.manifest` for project structure information
- **Diagram generators**: From `local_deepwiki.generators.diagrams` for creating workflow sequences and dependency graphs
- **Changelog generator**: From `local_deepwiki.generators.changelog` for generating changelog content

## Usage Example

```python
from pathlib import Path
from local_deepwiki.generators.wiki_pages import generate_changelog_page

# Generate changelog for a repository
repo_path = Path("/path/to/repository")
changelog_page = await generate_changelog_page(repo_path)

if changelog_page:
    print("Changelog generated successfully")
else:
    print("No changelog generated - not a git repo or no commits")
```

The module uses asynchronous functions, so it should be used within an async context. The changelog generation depends on the repository being a valid git repository with commit history.

## API Reference

### Functions

#### `generate_overview_page`

```python
async def generate_overview_page(index_status: IndexStatus, vector_store: VectorStore, llm: LLMProvider, system_prompt: str, manifest: ProjectManifest | None, repo_path: Path | None) -> WikiPage
```

Generate the [main](../export/pdf.md) overview/index page with grounded facts.  This method generates structured sections programmatically (tech stack, directory structure, quick start) to avoid LLM hallucination, and only uses the LLM to generate the description and features sections.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | [`IndexStatus`](../models.md) | - | Index status with repository information. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Vector store for code search. |
| `llm` | [`LLMProvider`](../providers/base.md) | - | LLM provider for content generation. |
| `system_prompt` | `str` | - | System prompt for the LLM. |
| `manifest` | `ProjectManifest | None` | - | Parsed project manifest (dependencies, entry points). |
| `repo_path` | `Path | None` | - | Path to the repository root. |

**Returns:** [`WikiPage`](../models.md)



<details>
<summary>View Source (lines 20-192) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_pages.py#L20-L192">GitHub</a></summary>

```python
async def generate_overview_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    manifest: ProjectManifest | None,
    repo_path: Path | None,
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

    Returns:
        WikiPage with overview content.
    """
    repo_name = Path(index_status.repo_path).name

    # Search for main entry points and key classes for context
    entry_search = await vector_store.search(
        "main entry point init server app",
        limit=10,
    )
    key_class_search = await vector_store.search(
        "class main core primary",
        limit=10,
    )

    # Combine and deduplicate
    seen_paths: set[str] = set()
    code_context_parts: list[str] = []
    for r in entry_search + key_class_search:
        if r.chunk.file_path not in seen_paths and len(code_context_parts) < 8:
            seen_paths.add(r.chunk.file_path)
            code_context_parts.append(
                f"File: {r.chunk.file_path}\n"
                f"Type: {r.chunk.chunk_type.value}\n"
                f"Name: {r.chunk.name}\n"
                f"```\n{r.chunk.content[:400]}\n```"
            )

    # Build a more structured prompt that leaves less room for hallucination
    prompt_parts = [f"# {repo_name}\n"]

    # Use manifest description directly if available
    if manifest and manifest.description:
        prompt_parts.append(f"\n{manifest.description}\n")

    # Key features - extract from README if available, otherwise from code
    prompt_parts.append(
        """
Based on the code samples below, write a "## Key Features" section listing 3-5 features you can VERIFY from the actual code. Each feature must reference specific code you see.
"""
    )

    # Technology stack - generate this programmatically, not via LLM
    if manifest and manifest.dependencies:
        tech_lines = ["\n## Technology Stack\n"]
        if manifest.language:
            lang_str = manifest.language
            if manifest.language_version:
                lang_str += f" {manifest.language_version}"
            tech_lines.append(f"- **{lang_str}**")

        # Group key dependencies
        key_deps = []
        for dep in sorted(manifest.dependencies.keys()):
            key_deps.append(dep)
        if key_deps:
            tech_lines.append(f"- **Dependencies**: {', '.join(key_deps[:10])}")
            if len(key_deps) > 10:
                tech_lines.append(f"  - Plus {len(key_deps) - 10} more...")

        prompt_parts.append("\n".join(tech_lines))

    # Directory structure - use actual tree
    if repo_path:
        dir_tree = get_directory_tree(repo_path, max_depth=2, max_items=25)
        prompt_parts.append(f"\n## Directory Structure\n\n```\n{dir_tree}\n```\n")

    # Quick start - use actual entry points
    if manifest and manifest.entry_points:
        qs_lines = ["\n## Quick Start\n"]
        for cmd, target in sorted(manifest.entry_points.items()):
            qs_lines.append(f"- `{cmd}` - runs `{target}`")
        prompt_parts.append("\n".join(qs_lines))

    # Now ask LLM only for the description/features part
    pre_generated = "\n".join(prompt_parts)

    # Build code samples context
    code_samples = (
        "\n\n".join(code_context_parts) if code_context_parts else "No code samples available."
    )

    prompt = f"""You are filling in sections of a README. Some sections are already written below. You need to write the "## Description" and "## Key Features" sections ONLY.

ALREADY WRITTEN (do not modify):
{pre_generated}

CODE SAMPLES FOR CONTEXT:
{code_samples}

YOUR TASK:
Write ONLY these two sections:

1. **## Description** (2-3 sentences explaining what this project does based on the code samples and existing content)

2. **## Key Features** (bullet list of 3-5 features you can VERIFY from the code samples shown)

RULES:
- ONLY describe functionality visible in the code samples
- Do NOT invent features not shown
- Do NOT mention libraries not in the Technology Stack section
- Keep it factual and grounded

Return ONLY the Description and Key Features sections as markdown."""

    llm_content = await llm.generate(prompt, system_prompt=system_prompt)

    # Build final content: title + LLM sections + pre-generated sections
    final_parts = [f"# {repo_name}\n"]

    # Add manifest description as subtitle if available
    if manifest and manifest.description:
        final_parts.append(f"\n{manifest.description}\n")

    # Add LLM-generated description and features
    final_parts.append(llm_content)

    # Add pre-generated sections (tech stack, directory, quick start)
    if manifest and manifest.dependencies:
        tech_lines = ["\n## Technology Stack\n"]
        if manifest.language:
            lang_str = manifest.language
            if manifest.language_version:
                lang_str += f" {manifest.language_version}"
            tech_lines.append(f"- **{lang_str}**")

        key_deps = sorted(manifest.dependencies.keys())
        if key_deps:
            tech_lines.append(f"- **Dependencies**: {', '.join(key_deps[:12])}")
            if len(key_deps) > 12:
                tech_lines.append(f"  - Plus {len(key_deps) - 12} more...")
        final_parts.append("\n".join(tech_lines))

    if repo_path:
        dir_tree = get_directory_tree(repo_path, max_depth=2, max_items=25)
        final_parts.append(f"\n## Directory Structure\n\n```\n{dir_tree}\n```")

    if manifest and manifest.entry_points:
        qs_lines = ["\n## Quick Start\n"]
        for cmd, target in sorted(manifest.entry_points.items()):
            qs_lines.append(f"- `{cmd}` → `{target}`")
        final_parts.append("\n".join(qs_lines))

    content = "\n".join(final_parts)

    return WikiPage(
        path="index.md",
        title="Overview",
        content=content,
        generated_at=time.time(),
    )
```

</details>

#### `generate_architecture_page`

```python
async def generate_architecture_page(index_status: IndexStatus, vector_store: VectorStore, llm: LLMProvider, system_prompt: str, manifest: ProjectManifest | None, repo_path: Path | None) -> WikiPage
```

Generate architecture documentation with diagrams and grounded facts.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | [`IndexStatus`](../models.md) | - | Index status with repository information. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Vector store for code search. |
| `llm` | [`LLMProvider`](../providers/base.md) | - | LLM provider for content generation. |
| `system_prompt` | `str` | - | System prompt for the LLM. |
| `manifest` | `ProjectManifest | None` | - | Parsed project manifest. |
| `repo_path` | `Path | None` | - | Path to the repository root. |

**Returns:** [`WikiPage`](../models.md)



<details>
<summary>View Source (lines 195-324) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_pages.py#L195-L324">GitHub</a></summary>

```python
async def generate_architecture_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    manifest: ProjectManifest | None,
    repo_path: Path | None,
) -> WikiPage:
    """Generate architecture documentation with diagrams and grounded facts.

    Args:
        index_status: Index status with repository information.
        vector_store: Vector store for code search.
        llm: LLM provider for content generation.
        system_prompt: System prompt for the LLM.
        manifest: Parsed project manifest.
        repo_path: Path to the repository root.

    Returns:
        WikiPage with architecture documentation.
    """
    # Gather multiple types of context for comprehensive architecture view

    # 1. Search for core/main components
    core_results = await vector_store.search(
        "main core primary class module",
        limit=15,
    )

    # 2. Search for architectural patterns
    pattern_results = await vector_store.search(
        "factory provider service handler controller",
        limit=10,
    )

    # 3. Search for data flow / pipeline
    flow_results = await vector_store.search(
        "process pipeline flow parse index generate",
        limit=10,
    )

    # 4. Get all classes for class list
    class_results = await vector_store.search(
        "class def __init__",
        limit=30,
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
    for r in all_chunks[:20]:
        context_parts.append(
            f"File: {r.chunk.file_path}\n"
            f"Type: {r.chunk.chunk_type.value}\n"
            f"Name: {r.chunk.name}\n"
            f"```\n{r.chunk.content[:800]}\n```"
        )

    code_context = "\n\n".join(context_parts)

    # Extract class names for reference
    class_names = set()
    for r in class_results:
        if r.chunk.chunk_type.value == "class" and r.chunk.name:
            class_names.add(r.chunk.name)

    class_list = ", ".join(sorted(class_names)[:30]) if class_names else "No classes found"

    # Include directory structure for module organization
    dir_structure = ""
    if repo_path:
        dir_structure = get_directory_tree(repo_path, max_depth=2, max_items=25)

    # Include dependencies for technology context
    dep_context = ""
    if manifest and manifest.dependencies:
        dep_context = "Key dependencies: " + ", ".join(sorted(manifest.dependencies.keys())[:15])

    prompt = f"""Generate architecture documentation based ONLY on the code provided below.

CLASSES FOUND IN CODEBASE:
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
- Write class names as plain text (e.g., "The [WikiGenerator](wiki.md) class") so they can be cross-linked

Format as markdown with clear sections."""

    content = await llm.generate(prompt, system_prompt=system_prompt)

    # Add workflow sequence diagrams
    content += "\n\n## Workflow Sequences\n\n"
    content += "The following diagrams show how data flows through key operations:\n\n"
    content += [generate_workflow_sequences](diagrams.md)()

    return [WikiPage](../models.md)(
        path="architecture.md",
        title="Architecture",
        content=content,
        generated_at=time.time(),
    )
```

</details>

#### `generate_dependencies_page`

```python
async def generate_dependencies_page(index_status: [IndexStatus](../models.md), vector_store: [VectorStore](../core/vectorstore.md), llm: [LLMProvider](../providers/base.md), system_prompt: str, manifest: [ProjectManifest](manifest.md) | None, import_search_limit: int) -> tuple[[WikiPage](../models.md), list[str]]
```

Generate dependencies documentation with grounded facts from manifest.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | `IndexStatus` | - | Index status with repository information. |
| `vector_store` | `VectorStore` | - | Vector store for code search. |
| `llm` | `LLMProvider` | - | LLM provider for content generation. |
| `system_prompt` | `str` | - | System prompt for the LLM. |
| `manifest` | `ProjectManifest | None` | - | Parsed project manifest. |
| `import_search_limit` | `int` | - | Max import chunks to search. |

**Returns:** `tuple[WikiPage, list[str]]`



<details>
<summary>View Source (lines 327-451) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L327-L451">GitHub</a></summary>

```python
async def generate_dependencies_page(
    index_status: [IndexStatus](../models.md),
    vector_store: [VectorStore](../core/vectorstore.md),
    llm: [LLMProvider](../providers/base.md),
    system_prompt: str,
    manifest: [ProjectManifest](manifest.md) | None,
    import_search_limit: int,
) -> tuple[[WikiPage](../models.md), list[str]]:
    """Generate dependencies documentation with grounded facts from manifest.

    Args:
        index_status: Index status with repository information.
        vector_store: Vector store for code search.
        llm: LLM provider for content generation.
        system_prompt: System prompt for the LLM.
        manifest: Parsed project manifest.
        import_search_limit: Max import chunks to search.

    Returns:
        Tuple of ([WikiPage](../models.md), list of source files that contributed).
    """
    from local_deepwiki.generators.diagrams import [generate_dependency_graph](diagrams.md)

    # Build grounded dependency context
    facts_sections = []

    # 1. External dependencies from manifest (GROUNDED FACTS)
    if manifest and manifest.dependencies:
        deps_list = []
        for name, version in sorted(manifest.dependencies.items()):
            version_str = f" ({version})" if version and version != "*" else ""
            deps_list.append(f"- {name}{version_str}")
        facts_sections.append(
            "EXTERNAL DEPENDENCIES (from package manifest):\n" + "\n".join(deps_list[:30])
        )

    # 2. Dev dependencies from manifest (GROUNDED FACTS)
    if manifest and manifest.dev_dependencies:
        dev_deps_list = []
        for name, version in sorted(manifest.dev_dependencies.items()):
            version_str = f" ({version})" if version and version != "*" else ""
            dev_deps_list.append(f"- {name}{version_str}")
        facts_sections.append(
            "DEV DEPENDENCIES (from package manifest):\n" + "\n".join(dev_deps_list[:20])
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
- When mentioning class names, write them as plain text (e.g., "[WikiGenerator](wiki.md) depends on [VectorStore](../core/vectorstore.md)")
- Do NOT include a Mermaid diagram - one will be auto-generated

Format as markdown."""

    content = await llm.generate(prompt, system_prompt=system_prompt)

    # Generate auto-generated module dependency graph with enhanced features
    dep_graph = [generate_dependency_graph](diagrams.md)(
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

    page = [WikiPage](../models.md)(
        path="dependencies.md",
        title="Dependencies",
        content=content,
        generated_at=time.time(),
    )
    return page, all_relevant_files
```

</details>

#### `generate_changelog_page`

```python
async def generate_changelog_page(repo_path: Path | None) -> [WikiPage](../models.md) | None
```

Generate changelog page from git history.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path | None` | - | Path to the repository root. |

**Returns:** `WikiPage | None`




<details>
<summary>View Source (lines 454-478) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L454-L478">GitHub</a></summary>

```python
async def generate_changelog_page(repo_path: Path | None) -> [WikiPage](../models.md) | None:
    """Generate changelog page from git history.

    Args:
        repo_path: Path to the repository root.

    Returns:
        [WikiPage](../models.md) with changelog content, or None if not a git repo.
    """
    if repo_path is None:
        return None

    from local_deepwiki.generators.changelog import [generate_changelog_content](changelog.md)

    content = [generate_changelog_content](changelog.md)(repo_path)
    if not content:
        logger.debug("No changelog generated (not a git repo or no commits)")
        return None

    return [WikiPage](../models.md)(
        path="changelog.md",
        title="Changelog",
        content=content,
        generated_at=time.time(),
    )
```

</details>

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[[WikiPage](../models.md)]
    N2[add]
    N3[generate]
    N4[generate_architecture_page]
    N5[[generate_changelog_content](changelog.md)]
    N6[generate_changelog_page]
    N7[generate_dependencies_page]
    N8[[generate_dependency_graph](diagrams.md)]
    N9[generate_overview_page]
    N10[[generate_workflow_sequences](diagrams.md)]
    N11[[get_directory_tree](manifest.md)]
    N12[search]
    N13[time]
    N9 --> N0
    N9 --> N12
    N9 --> N2
    N9 --> N11
    N9 --> N3
    N9 --> N1
    N9 --> N13
    N4 --> N12
    N4 --> N2
    N4 --> N11
    N4 --> N3
    N4 --> N10
    N4 --> N1
    N4 --> N13
    N7 --> N12
    N7 --> N2
    N7 --> N3
    N7 --> N8
    N7 --> N1
    N7 --> N13
    N6 --> N5
    N6 --> N1
    N6 --> N13
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13 func
```

## Used By

Functions and methods in this file and their callers:

- **`Path`**: called by `generate_overview_page`
- **`WikiPage`**: called by `generate_architecture_page`, `generate_changelog_page`, `generate_dependencies_page`, `generate_overview_page`
- **`add`**: called by `generate_architecture_page`, `generate_dependencies_page`, `generate_overview_page`
- **`generate`**: called by `generate_architecture_page`, `generate_dependencies_page`, `generate_overview_page`
- **`generate_changelog_content`**: called by `generate_changelog_page`
- **`generate_dependency_graph`**: called by `generate_dependencies_page`
- **`generate_workflow_sequences`**: called by `generate_architecture_page`
- **`get_directory_tree`**: called by `generate_architecture_page`, `generate_overview_page`
- **`search`**: called by `generate_architecture_page`, `generate_dependencies_page`, `generate_overview_page`
- **`time`**: called by `generate_architecture_page`, `generate_changelog_page`, `generate_dependencies_page`, `generate_overview_page`

## Usage Examples

*Examples extracted from test files*

### Test generates basic overview page

From `test_wiki_pages_coverage.py::TestGenerateOverviewPage::test_generates_basic_overview`:

```python
result = await generate_overview_page(
    index_status=index_status,
    vector_store=mock_vector_store,
    llm=mock_llm,
    system_prompt="You are a documentation expert.",
    manifest=None,
    repo_path=repo_path,
)

assert result.path == "index.md"
assert result.title == "Overview"
```

### Test includes manifest description in content

From `test_wiki_pages_coverage.py::TestGenerateOverviewPage::test_includes_manifest_description`:

```python
result = await generate_overview_page(
    index_status=index_status,
    vector_store=mock_vector_store,
    llm=mock_llm,
    system_prompt="You are a documentation expert.",
    manifest=manifest,
    repo_path=repo_path,
)

assert "A great project for testing." in result.content
```

### Test generates basic architecture page

From `test_wiki_pages_coverage.py::TestGenerateArchitecturePage::test_generates_basic_architecture`:

```python
result = await generate_architecture_page(
    index_status=index_status,
    vector_store=mock_vector_store,
    llm=mock_llm,
    system_prompt="Architecture expert",
    manifest=None,
    repo_path=repo_path,
)

assert result.path == "architecture.md"
assert result.title == "Architecture"
```

### Test searches for multiple types of architectural context

From `test_wiki_pages_coverage.py::TestGenerateArchitecturePage::test_searches_multiple_context_types`:

```python
await generate_architecture_page(
    index_status=index_status,
    vector_store=mock_vector_store,
    llm=mock_llm,
    system_prompt="Architecture expert",
    manifest=None,
    repo_path=repo_path,
)

# Should have made multiple search calls
assert mock_vector_store.search.call_count >= 3
```

### Test returns None when repo_path is None

From `test_wiki_pages_coverage.py::TestGenerateChangelogPage::test_returns_none_when_no_repo_path`:

```python
result = await generate_changelog_page(repo_path=None)
assert result is None
```


 PROTECTED0 

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `generate_overview_page` | function | Brian Breidenbach | today | `0d91a70` Apply Python best practices... |
| `generate_architecture_page` | function | Brian Breidenbach | today | `0d91a70` Apply Python best practices... |
| `generate_dependencies_page` | function | Brian Breidenbach | yesterday | `b8f8b68` Refactor: Extract page gene... |
| `generate_changelog_page` | function | Brian Breidenbach | yesterday | `b8f8b68` Refactor: Extract page gene... |

## Relevant Source Files

- `src/local_deepwiki/generators/wiki_pages.py:20-192`
