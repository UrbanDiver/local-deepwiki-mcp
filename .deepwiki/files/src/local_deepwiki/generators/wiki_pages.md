# File Overview

This file, `src/local_deepwiki/generators/wiki_pages.py`, provides functions for generating structured wiki pages for a project. It focuses on creating overview, architecture, and dependencies documentation using a combination of manifest data, vector store search results, and LLM-based generation. The module integrates with [`VectorStore`](../core/vectorstore.md) for code context, [`ProjectManifest`](manifest.md) for project metadata, and [`LLMProvider`](../providers/base.md) for natural language generation.

## Key Features

- Generates structured documentation sections programmatically to avoid hallucinations
- Uses vector search to gather code context for LLM prompts
- Supports multiple page types: overview, architecture, dependencies, and changelog
- Integrates with logging and project manifest parsing

## Dependencies

- `asyncio`, `time`, `pathlib.Path`, `typing.TYPE_CHECKING`
- [`local_deepwiki.core.vectorstore.VectorStore`](../core/vectorstore.md)
- `local_deepwiki.generators.diagrams`: [`generate_workflow_sequences`](diagrams.md), [`generate_dependency_graph`](diagrams.md)
- `local_deepwiki.generators.manifest`: [`ProjectManifest`](manifest.md), [`get_directory_tree`](manifest.md)
- [`local_deepwiki.logging.get_logger`](../logging.md)
- `local_deepwiki.models`: [`IndexStatus`](../models.md), [`WikiPage`](../export/streaming.md)
- `local_deepwiki.providers.base`: [`LLMProvider`](../providers/base.md)
- `local_deepwiki.generators.changelog`: [`generate_changelog_content`](changelog.md)

## Integration

This module is used by:
- `wiki` ([main](../export/pdf.md) CLI entry point)
- `test_wiki_pages_coverage` (test suite)

It is part of the documentation generation pipeline, working closely with:
- `src/local_deepwiki/core/__init__.py`
- `src/local_deepwiki/generators/source_refs.py`
- `src/local_deepwiki/plugins/base.py`
- `tests/test_plugins.py`

# Functions

## `_build_tech_stack_section`

```python
def _build_tech_stack_section(manifest: ProjectManifest, max_deps: int = 12) -> str
```

Build technology stack section from manifest.

**Parameters:**
- `manifest`: Project manifest with dependencies.
- `max_deps`: Maximum dependencies to list.

**Returns:**
- Markdown section for tech stack.

## `_build_directory_section`

```python
def _build_directory_section(repo_path: Path) -> str
```

Build directory structure section.

**Parameters:**
- `repo_path`: Path to repository root.

**Returns:**
- Markdown section for directory structure.

## `_build_quick_start_section`

```python
def _build_quick_start_section(manifest: ProjectManifest) -> str
```

Build quick start section from entry points.

**Parameters:**
- `manifest`: Project manifest with entry points.

**Returns:**
- Markdown section for quick start.

## `_gather_code_context`

```python
async def _gather_code_context(vector_store: VectorStore) -> list[str]
```

Search for [main](../export/pdf.md) entry points and key classes for context.

**Parameters:**
- `vector_store`: Vector store for code search.

**Returns:**
- List of formatted code context strings.

## `_build_overview_prompt`

```python
def _build_overview_prompt(pre_generated: str, code_samples: str) -> str
```

Build the LLM prompt for overview generation.

**Parameters:**
- `pre_generated`: Already-generated content sections.
- `code_samples`: Formatted code samples for context.

**Returns:**
- Formatted prompt for LLM.

## `generate_overview_page`

```python
async def generate_overview_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    manifest: ProjectManifest | None,
    repo_path: Path | None,
) -> WikiPage
```

Generate the [main](../export/pdf.md) overview/index page with grounded facts.

This method generates structured sections programmatically (tech stack, directory structure, quick start) to avoid LLM hallucination, and only uses the LLM to generate the description and features sections.

**Parameters:**
- `index_status`: Index status with repository information.
- `vector_store`: Vector store for code search.
- `llm`: LLM provider for content generation.
- `system_prompt`: System prompt for the LLM.
- `manifest`: Parsed project manifest.
- `repo_path`: Path to repository root.

**Returns:**
- [`WikiPage`](../export/streaming.md) with generated overview content.

## `generate_architecture_page`

```python
async def generate_architecture_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    manifest: ProjectManifest | None,
    repo_path: Path | None,
) -> WikiPage
```

Generate architecture documentation with diagrams and grounded facts.

**Parameters:**
- `index_status`: Index status with repository information.
- `vector_store`: Vector store for code search.
- `llm`: LLM provider for content generation.
- `system_prompt`: System prompt for the LLM.
- `manifest`: Parsed project manifest.
- `repo_path`: Path to repository root.

**Returns:**
- [`WikiPage`](../export/streaming.md) with generated architecture content.

## `generate_dependencies_page`

```python
async def generate_dependencies_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    manifest: ProjectManifest | None,
    import_search_limit: int,
) -> tuple[WikiPage, list[str]]
```

Generate dependencies documentation with grounded facts from manifest.

**Parameters:**
- `index_status`: Index status with repository information.
- `vector_store`: Vector store for code search.
- `llm`: LLM provider for content generation.
- `system_prompt`: System prompt for the LLM.
- `manifest`: Parsed project manifest.
- `import_search_limit`: Limit for import search results.

**Returns:**
- Tuple of [`WikiPage`](../export/streaming.md) with generated dependencies content and list of import paths.

## `generate_changelog_page`

```python
async def generate_changelog_page(repo_path: Path | None) -> WikiPage | None
```

Generate changelog page from git history.

**Parameters:**
- `repo_path`: Path to the repository root.

**Returns:**
- [`WikiPage`](../export/streaming.md) with changelog content, or `None` if not a git repo.

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

**Returns:** [`WikiPage`](../export/streaming.md)



<details>
<summary>View Source (lines 143-218) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_pages.py#L143-L218">GitHub</a></summary>

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

    # Gather code context for LLM
    code_context_parts = await _gather_code_context(vector_store)
    code_samples = "\n\n".join(code_context_parts) if code_context_parts else "No code samples available."

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
    prompt = _build_overview_prompt(pre_generated, code_samples)
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

**Returns:** [`WikiPage`](../export/streaming.md)



<details>
<summary>View Source (lines 221-341) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_pages.py#L221-L341">GitHub</a></summary>

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

    # Add link to detailed dependency graph
    content += "\n\n## Module Dependencies\n\n"
    content += "For a detailed view of module interdependencies including circular dependency "
    content += "detection, see the [Dependency Graph](dependency-graph.md) page.\n"

    return [WikiPage](../export/streaming.md)(
        path="architecture.md",
        title="Architecture",
        content=content,
        generated_at=time.time(),
    )
```

</details>

#### `generate_dependencies_page`

```python
async def generate_dependencies_page(index_status: [IndexStatus](../models.md), vector_store: [VectorStore](../core/vectorstore.md), llm: [LLMProvider](../providers/base.md), system_prompt: str, manifest: [ProjectManifest](manifest.md) | None, import_search_limit: int) -> tuple[[WikiPage](../export/streaming.md), list[str]]
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
<summary>View Source (lines 344-468) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L344-L468">GitHub</a></summary>

```python
async def generate_dependencies_page(
    index_status: [IndexStatus](../models.md),
    vector_store: [VectorStore](../core/vectorstore.md),
    llm: [LLMProvider](../providers/base.md),
    system_prompt: str,
    manifest: [ProjectManifest](manifest.md) | None,
    import_search_limit: int,
) -> tuple[[WikiPage](../export/streaming.md), list[str]]:
    """Generate dependencies documentation with grounded facts from manifest.

    Args:
        index_status: Index status with repository information.
        vector_store: Vector store for code search.
        llm: LLM provider for content generation.
        system_prompt: System prompt for the LLM.
        manifest: Parsed project manifest.
        import_search_limit: Max import chunks to search.

    Returns:
        Tuple of ([WikiPage](../export/streaming.md), list of source files that contributed).
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
        content += "\n\n## Module [Dependency Graph](dependency_graph.md)\n\n"
        content += "The following diagram shows module dependencies. "
        content += "Click on a module to view its documentation. "
        content += "External dependencies are shown with dashed borders.\n\n"
        content += dep_graph

    page = [WikiPage](../export/streaming.md)(
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
async def generate_changelog_page(repo_path: Path | None) -> [WikiPage](../export/streaming.md) | None
```

Generate changelog page from git history.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path | None` | - | Path to the repository root. |

**Returns:** `WikiPage | None`




<details>
<summary>View Source (lines 471-495) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L471-L495">GitHub</a></summary>

```python
async def generate_changelog_page(repo_path: Path | None) -> [WikiPage](../export/streaming.md) | None:
    """Generate changelog page from git history.

    Args:
        repo_path: Path to the repository root.

    Returns:
        [WikiPage](../export/streaming.md) with changelog content, or None if not a git repo.
    """
    if repo_path is None:
        return None

    from local_deepwiki.generators.changelog import [generate_changelog_content](changelog.md)

    content = [generate_changelog_content](changelog.md)(repo_path)
    if not content:
        logger.debug("No changelog generated (not a git repo or no commits)")
        return None

    return [WikiPage](../export/streaming.md)(
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
    N1[[WikiPage](../export/streaming.md)]
    N2[_build_directory_section]
    N3[_build_overview_prompt]
    N4[_build_quick_start_section]
    N5[_build_tech_stack_section]
    N6[_gather_code_context]
    N7[add]
    N8[gather]
    N9[generate]
    N10[generate_architecture_page]
    N11[[generate_changelog_content](changelog.md)]
    N12[generate_changelog_page]
    N13[generate_dependencies_page]
    N14[[generate_dependency_graph](diagrams.md)]
    N15[generate_overview_page]
    N16[[generate_workflow_sequences](diagrams.md)]
    N17[[get_directory_tree](manifest.md)]
    N18[search]
    N19[time]
    N2 --> N17
    N6 --> N8
    N6 --> N18
    N6 --> N7
    N15 --> N0
    N15 --> N6
    N15 --> N5
    N15 --> N2
    N15 --> N4
    N15 --> N3
    N15 --> N9
    N15 --> N1
    N15 --> N19
    N10 --> N8
    N10 --> N18
    N10 --> N7
    N10 --> N17
    N10 --> N9
    N10 --> N16
    N10 --> N1
    N10 --> N19
    N13 --> N18
    N13 --> N7
    N13 --> N9
    N13 --> N14
    N13 --> N1
    N13 --> N19
    N12 --> N11
    N12 --> N1
    N12 --> N19
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19 func
```

## Used By

Functions and methods in this file and their callers:

- **`Path`**: called by `generate_overview_page`
- **`WikiPage`**: called by `generate_architecture_page`, `generate_changelog_page`, `generate_dependencies_page`, `generate_overview_page`
- **`_build_directory_section`**: called by `generate_overview_page`
- **`_build_overview_prompt`**: called by `generate_overview_page`
- **`_build_quick_start_section`**: called by `generate_overview_page`
- **`_build_tech_stack_section`**: called by `generate_overview_page`
- **`_gather_code_context`**: called by `generate_overview_page`
- **`add`**: called by `_gather_code_context`, `generate_architecture_page`, `generate_dependencies_page`
- **`gather`**: called by `_gather_code_context`, `generate_architecture_page`
- **`generate`**: called by `generate_architecture_page`, `generate_dependencies_page`, `generate_overview_page`
- **`generate_changelog_content`**: called by `generate_changelog_page`
- **`generate_dependency_graph`**: called by `generate_dependencies_page`
- **`generate_workflow_sequences`**: called by `generate_architecture_page`
- **`get_directory_tree`**: called by `_build_directory_section`, `generate_architecture_page`
- **`search`**: called by `_gather_code_context`, `generate_architecture_page`, `generate_dependencies_page`
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


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `generate_architecture_page` | function | Brian Breidenbach | 1 week ago | `a64166a` Add seven medium-priority e... |
| `_build_tech_stack_section` | function | Brian Breidenbach | 2 weeks ago | `106b11c` Refactor generate_overview_... |
| `_build_directory_section` | function | Brian Breidenbach | 2 weeks ago | `106b11c` Refactor generate_overview_... |
| `_build_quick_start_section` | function | Brian Breidenbach | 2 weeks ago | `106b11c` Refactor generate_overview_... |
| `_gather_code_context` | function | Brian Breidenbach | 2 weeks ago | `106b11c` Refactor generate_overview_... |
| `_build_overview_prompt` | function | Brian Breidenbach | 2 weeks ago | `106b11c` Refactor generate_overview_... |
| `generate_overview_page` | function | Brian Breidenbach | 2 weeks ago | `106b11c` Refactor generate_overview_... |
| `generate_dependencies_page` | function | Brian Breidenbach | 3 weeks ago | `b8f8b68` Refactor: Extract page gene... |
| `generate_changelog_page` | function | Brian Breidenbach | 3 weeks ago | `b8f8b68` Refactor: Extract page gene... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_build_tech_stack_section`

<details>
<summary>View Source (lines 21-47) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L21-L47">GitHub</a></summary>

```python
def _build_tech_stack_section(manifest: [ProjectManifest](manifest.md), max_deps: int = 12) -> str:
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
```

</details>


#### `_build_directory_section`

<details>
<summary>View Source (lines 50-60) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L50-L60">GitHub</a></summary>

```python
def _build_directory_section(repo_path: Path) -> str:
    """Build directory structure section.

    Args:
        repo_path: Path to repository root.

    Returns:
        Markdown section for directory structure.
    """
    dir_tree = [get_directory_tree](manifest.md)(repo_path, max_depth=2, max_items=25)
    return f"\n## Directory Structure\n\n```\n{dir_tree}\n```"
```

</details>


#### `_build_quick_start_section`

<details>
<summary>View Source (lines 63-78) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L63-L78">GitHub</a></summary>

```python
def _build_quick_start_section(manifest: [ProjectManifest](manifest.md)) -> str:
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
```

</details>


#### `_gather_code_context`

<details>
<summary>View Source (lines 81-106) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L81-L106">GitHub</a></summary>

```python
async def _gather_code_context(vector_store: [VectorStore](../core/vectorstore.md)) -> list[str]:
    """Search for [main](../export/pdf.md) entry points and key classes for context.

    Args:
        vector_store: Vector store for code search.

    Returns:
        List of formatted code context strings.
    """
    entry_search, key_class_search = await asyncio.gather(
        vector_store.search("[main](../export/pdf.md) entry point init server app", limit=10),
        vector_store.search("class [main](../export/pdf.md) core primary", limit=10),
    )

    seen_paths: set[str] = set()
    code_parts: list[str] = []
    for r in entry_search + key_class_search:
        if r.chunk.file_path not in seen_paths and len(code_parts) < 8:
            seen_paths.add(r.chunk.file_path)
            code_parts.append(
                f"File: {r.chunk.file_path}\n"
                f"Type: {r.chunk.chunk_type.value}\n"
                f"Name: {r.chunk.name}\n"
                f"```\n{r.chunk.content[:400]}\n```"
            )
    return code_parts
```

</details>


#### `_build_overview_prompt`

<details>
<summary>View Source (lines 109-140) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/wiki_pages.py#L109-L140">GitHub</a></summary>

```python
def _build_overview_prompt(pre_generated: str, code_samples: str) -> str:
    """Build the LLM prompt for overview generation.

    Args:
        pre_generated: Already-generated content sections.
        code_samples: Formatted code samples for context.

    Returns:
        Formatted prompt for LLM.
    """
    return f"""You are filling in sections of a README. Some sections are already written below. You need to write the "## Description" and "## Key Features" sections ONLY.

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
```

</details>

## Relevant Source Files

- `src/local_deepwiki/generators/wiki_pages.py:21-47`
