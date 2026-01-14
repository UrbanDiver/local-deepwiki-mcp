"""Wiki documentation generator using LLM providers."""

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

from local_deepwiki.config import Config, get_config
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.api_docs import get_file_api_docs
from local_deepwiki.generators.callgraph import get_file_call_graph
from local_deepwiki.generators.test_examples import get_file_examples
from local_deepwiki.generators.crosslinks import EntityRegistry, add_cross_links
from local_deepwiki.generators.diagrams import (
    generate_class_diagram,
    generate_dependency_graph,
    generate_language_pie_chart,
    generate_module_overview,
)
from local_deepwiki.generators.manifest import (
    ProjectManifest,
    get_cached_manifest,
    get_directory_tree,
)
from local_deepwiki.generators.search import write_search_index
from local_deepwiki.generators.see_also import RelationshipAnalyzer, add_see_also_sections
from local_deepwiki.generators.source_refs import add_source_refs_sections
from local_deepwiki.generators.toc import generate_toc, write_toc
from local_deepwiki.models import (
    IndexStatus,
    ProgressCallback,
    WikiGenerationStatus,
    WikiPage,
    WikiPageStatus,
    WikiStructure,
)
from local_deepwiki.providers.llm import get_llm_provider

SYSTEM_PROMPT = """You are a technical documentation expert. Generate clear, concise documentation for code.

FORMATTING:
- Use markdown formatting
- Include code examples where helpful
- When mentioning class or function names in prose explanations, write them as plain text (e.g., "The WikiGenerator class") rather than inline code, so they can be cross-linked
- Only use backticks for code snippets, variable names in context, or when showing exact syntax

ACCURACY CONSTRAINTS - CRITICAL:
- ONLY describe what you can verify from the code/context provided
- NEVER invent or guess features, libraries, patterns, or capabilities not explicitly shown
- NEVER fabricate CLI commands, API endpoints, or configuration options
- If the context doesn't show something, DO NOT mention it
- When uncertain, omit the information rather than guess
- Stick to facts from the provided code - do not extrapolate or assume

CONTENT GUIDELINES:
- Focus on explaining what the code does and how to use it
- Keep explanations practical and actionable
- Base technology stack descriptions ONLY on actual dependencies shown
- Base directory structure descriptions ONLY on actual files listed"""


class WikiGenerator:
    """Generate wiki documentation from indexed code."""

    WIKI_STATUS_FILE = "wiki_status.json"

    def __init__(
        self,
        wiki_path: Path,
        vector_store: VectorStore,
        config: Config | None = None,
        llm_provider_name: str | None = None,
    ):
        """Initialize the wiki generator.

        Args:
            wiki_path: Path to wiki output directory.
            vector_store: Vector store with indexed code.
            config: Optional configuration.
            llm_provider_name: Override LLM provider ("ollama", "anthropic", "openai").
        """
        self.wiki_path = wiki_path
        self.vector_store = vector_store
        self.config = config or get_config()

        # Override LLM provider if specified
        if llm_provider_name:
            self.config.llm.provider = llm_provider_name  # type: ignore

        self.llm = get_llm_provider(self.config.llm)

        # Entity registry for cross-linking
        self.entity_registry = EntityRegistry()

        # Relationship analyzer for See Also sections
        self.relationship_analyzer = RelationshipAnalyzer()

        # Track file hashes from index_status for incremental generation
        self._file_hashes: dict[str, str] = {}

        # Previous wiki generation status for incremental updates
        self._previous_status: WikiGenerationStatus | None = None

        # New page statuses for current generation
        self._page_statuses: dict[str, WikiPageStatus] = {}

        # Cached project manifest (parsed from package files)
        self._manifest: ProjectManifest | None = None

        # Repository path (set during generation)
        self._repo_path: Path | None = None

        # Line info for source files (computed from chunks)
        self._file_line_info: dict[str, tuple[int, int]] = {}

    def _get_main_definition_lines(self) -> dict[str, tuple[int, int]]:
        """Get line range of main definition (first class or function) per file.

        Returns:
            Dict mapping file_path to (start_line, end_line) tuple.
        """
        table = self.vector_store._get_table()
        if table is None:
            return {}

        df = table.to_pandas()
        result: dict[str, tuple[int, int]] = {}

        for file_path, group in df.groupby("file_path"):
            # Sort by start_line to get first definitions
            classes = group[group["chunk_type"] == "class"].sort_values("start_line")
            functions = group[group["chunk_type"] == "function"].sort_values("start_line")

            if not classes.empty:
                # Use first class definition
                row = classes.iloc[0]
                result[str(file_path)] = (int(row["start_line"]), int(row["end_line"]))
            elif not functions.empty:
                # Use first function definition
                row = functions.iloc[0]
                result[str(file_path)] = (int(row["start_line"]), int(row["end_line"]))

        return result

    async def _load_wiki_status(self) -> WikiGenerationStatus | None:
        """Load previous wiki generation status.

        Returns:
            WikiGenerationStatus or None if not found.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        if not status_path.exists():
            return None

        def _read_status() -> WikiGenerationStatus | None:
            try:
                with open(status_path) as f:
                    data = json.load(f)
                return WikiGenerationStatus.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to load wiki status from {status_path}: {e}")
                return None

        return await asyncio.to_thread(_read_status)

    async def _save_wiki_status(self, status: WikiGenerationStatus) -> None:
        """Save wiki generation status.

        Args:
            status: The WikiGenerationStatus to save.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        data = status.model_dump()

        def _write_status() -> None:
            with open(status_path, "w") as f:
                json.dump(data, f, indent=2)

        await asyncio.to_thread(_write_status)

    def _compute_content_hash(self, content: str) -> str:
        """Compute hash of page content.

        Args:
            content: Page content.

        Returns:
            SHA256 hash of content.
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _needs_regeneration(
        self,
        page_path: str,
        source_files: list[str],
    ) -> bool:
        """Check if a page needs regeneration based on source file changes.

        Args:
            page_path: Wiki page path.
            source_files: List of source files that contribute to this page.

        Returns:
            True if page needs regeneration, False if it can be skipped.
        """
        if self._previous_status is None:
            return True

        prev_page = self._previous_status.pages.get(page_path)
        if prev_page is None:
            return True

        # Check if any source file has changed
        for source_file in source_files:
            current_hash = self._file_hashes.get(source_file)
            prev_hash = prev_page.source_hashes.get(source_file)

            if current_hash is None or prev_hash is None:
                return True
            if current_hash != prev_hash:
                return True

        # Check if source files list changed
        if set(source_files) != set(prev_page.source_files):
            return True

        return False

    async def _load_existing_page(self, page_path: str) -> WikiPage | None:
        """Load an existing wiki page from disk.

        Args:
            page_path: Relative path to the page.

        Returns:
            WikiPage if found, None otherwise.
        """
        full_path = self.wiki_path / page_path
        if not full_path.exists():
            return None

        # Capture values needed for the sync function
        prev_page = self._previous_status.pages.get(page_path) if self._previous_status else None
        title = Path(page_path).stem.replace("_", " ").title()
        generated_at = prev_page.generated_at if prev_page else time.time()

        def _read_page() -> WikiPage | None:
            try:
                content = full_path.read_text()
                return WikiPage(
                    path=page_path,
                    title=title,
                    content=content,
                    generated_at=generated_at,
                )
            except Exception as e:
                logger.warning(f"Failed to load existing page {page_path}: {e}")
                return None

        return await asyncio.to_thread(_read_page)

    def _record_page_status(
        self,
        page: WikiPage,
        source_files: list[str],
    ) -> None:
        """Record status for a generated/loaded page.

        Args:
            page: The wiki page.
            source_files: Source files that contributed to this page.
        """
        source_hashes = {f: self._file_hashes.get(f, "") for f in source_files}

        # Include line info for source files that have it
        source_line_info = {
            f: {"start_line": self._file_line_info[f][0], "end_line": self._file_line_info[f][1]}
            for f in source_files
            if f in self._file_line_info
        }

        self._page_statuses[page.path] = WikiPageStatus(
            path=page.path,
            source_files=source_files,
            source_hashes=source_hashes,
            source_line_info=source_line_info,
            content_hash=self._compute_content_hash(page.content),
            generated_at=page.generated_at,
        )

    async def generate(
        self,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None = None,
        full_rebuild: bool = False,
    ) -> WikiStructure:
        """Generate wiki documentation for the indexed repository.

        Args:
            index_status: The index status with file information.
            progress_callback: Optional progress callback.
            full_rebuild: If True, regenerate all pages. Otherwise, only regenerate changed pages.

        Returns:
            WikiStructure with generated pages.
        """
        logger.info(f"Starting wiki generation for {index_status.repo_path}")
        logger.debug(f"Full rebuild: {full_rebuild}, Total files: {index_status.total_files}")

        pages: list[WikiPage] = []
        total_steps = (
            9  # overview, architecture, modules, files, dependencies, changelog, cross-links, see-also, search
        )
        pages_generated = 0
        pages_skipped = 0

        # Store repo path and parse manifest for grounded generation (with caching)
        self._repo_path = Path(index_status.repo_path)
        self._manifest = get_cached_manifest(self._repo_path, cache_dir=self.wiki_path)

        # Build file hash map for incremental generation
        self._file_hashes = {f.path: f.hash for f in index_status.files}
        all_source_files = list(self._file_hashes.keys())

        # Load previous wiki status for incremental updates
        if not full_rebuild:
            self._previous_status = await self._load_wiki_status()

        # Pre-compute line info for source files (for source refs with line numbers)
        self._file_line_info = self._get_main_definition_lines()

        # Generate index page (overview) - depends on all files
        if progress_callback:
            progress_callback("Generating overview", 0, total_steps)

        overview_path = "index.md"
        if full_rebuild or self._needs_regeneration(overview_path, all_source_files):
            overview_page = await self._generate_overview(index_status)
            pages_generated += 1
        else:
            overview_page = await self._load_existing_page(overview_path)
            if overview_page is None:
                overview_page = await self._generate_overview(index_status)
                pages_generated += 1
            else:
                pages_skipped += 1

        pages.append(overview_page)
        self._record_page_status(overview_page, all_source_files)
        await self._write_page(overview_page)

        # Generate architecture page - depends on all files
        if progress_callback:
            progress_callback("Generating architecture docs", 1, total_steps)

        architecture_path = "architecture.md"
        if full_rebuild or self._needs_regeneration(architecture_path, all_source_files):
            architecture_page = await self._generate_architecture(index_status)
            pages_generated += 1
        else:
            architecture_page = await self._load_existing_page(architecture_path)
            if architecture_page is None:
                architecture_page = await self._generate_architecture(index_status)
                pages_generated += 1
            else:
                pages_skipped += 1

        pages.append(architecture_page)
        self._record_page_status(architecture_page, all_source_files)
        await self._write_page(architecture_page)

        # Collect import chunks for relationship analysis (needed for See Also)
        import_results = await self.vector_store.search(
            "import require include",
            limit=self.config.wiki.import_search_limit,
        )
        import_chunks = [r.chunk for r in import_results if r.chunk.chunk_type.value == "import"]
        self.relationship_analyzer.analyze_chunks(import_chunks)

        # Generate module pages
        if progress_callback:
            progress_callback("Generating module documentation", 2, total_steps)

        module_pages, gen_count, skip_count = await self._generate_module_docs(
            index_status, full_rebuild
        )
        pages_generated += gen_count
        pages_skipped += skip_count
        for page in module_pages:
            pages.append(page)
            await self._write_page(page)

        # Generate file-level documentation
        if progress_callback:
            progress_callback("Generating file documentation", 3, total_steps)

        file_pages, gen_count, skip_count = await self._generate_file_docs(
            index_status, progress_callback, full_rebuild
        )
        pages_generated += gen_count
        pages_skipped += skip_count
        for page in file_pages:
            pages.append(page)
            await self._write_page(page)

        # Generate dependencies page - depends on all files
        if progress_callback:
            progress_callback("Generating dependencies", 4, total_steps)

        deps_path = "dependencies.md"
        if full_rebuild or self._needs_regeneration(deps_path, all_source_files):
            deps_page = await self._generate_dependencies(index_status)
            pages_generated += 1
        else:
            deps_page = await self._load_existing_page(deps_path)
            if deps_page is None:
                deps_page = await self._generate_dependencies(index_status)
                pages_generated += 1
            else:
                pages_skipped += 1

        pages.append(deps_page)
        self._record_page_status(deps_page, all_source_files)
        await self._write_page(deps_page)

        # Generate changelog page from git history
        if progress_callback:
            progress_callback("Generating changelog", 5, total_steps)

        changelog_page = await self._generate_changelog()
        if changelog_page:
            pages.append(changelog_page)
            self._record_page_status(changelog_page, all_source_files)
            await self._write_page(changelog_page)
            pages_generated += 1

        # Apply cross-links to all pages
        if progress_callback:
            progress_callback("Adding cross-links", 6, total_steps)

        pages = add_cross_links(pages, self.entity_registry)

        # Add Relevant Source Files sections (with GitHub/GitLab links if available)
        pages = add_source_refs_sections(pages, self._page_statuses, self._repo_path)

        # Add See Also sections
        if progress_callback:
            progress_callback("Adding See Also sections", 7, total_steps)

        pages = add_see_also_sections(pages, self.relationship_analyzer)

        # Re-write pages with cross-links and See Also sections
        for page in pages:
            await self._write_page(page)

        # Generate search index
        if progress_callback:
            progress_callback("Generating search index", 8, total_steps)

        write_search_index(self.wiki_path, pages)

        # Generate table of contents with hierarchical numbering
        page_list = [{"path": p.path, "title": p.title} for p in pages]
        toc = generate_toc(page_list)
        write_toc(toc, self.wiki_path)

        # Save wiki generation status
        wiki_status = WikiGenerationStatus(
            repo_path=index_status.repo_path,
            generated_at=time.time(),
            total_pages=len(pages),
            index_status_hash=hashlib.sha256(
                json.dumps(index_status.model_dump(), sort_keys=True).encode()
            ).hexdigest()[:16],
            pages=self._page_statuses,
        )
        await self._save_wiki_status(wiki_status)

        if progress_callback:
            progress_callback(
                f"Wiki generation complete ({pages_generated} generated, {pages_skipped} unchanged)",
                total_steps,
                total_steps,
            )

        logger.info(
            f"Wiki generation complete: {pages_generated} pages generated, "
            f"{pages_skipped} pages unchanged, {len(pages)} total pages"
        )
        return WikiStructure(root=str(self.wiki_path), pages=pages)

    async def _generate_overview(self, index_status: IndexStatus) -> WikiPage:
        """Generate the main overview/index page with grounded facts.

        This method generates structured sections programmatically (tech stack,
        directory structure, quick start) to avoid LLM hallucination, and only
        uses the LLM to generate the description and features sections.
        """
        repo_name = Path(index_status.repo_path).name

        # Search for main entry points and key classes for context
        entry_search = await self.vector_store.search(
            "main entry point init server app",
            limit=10,
        )
        key_class_search = await self.vector_store.search(
            "class main core primary",
            limit=10,
        )

        # Combine and deduplicate
        seen_paths = set()
        code_context_parts = []
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
        if self._manifest and self._manifest.description:
            prompt_parts.append(f"\n{self._manifest.description}\n")

        # Key features - extract from README if available, otherwise from code
        prompt_parts.append(
            """
Based on the code samples below, write a "## Key Features" section listing 3-5 features you can VERIFY from the actual code. Each feature must reference specific code you see.
"""
        )

        # Technology stack - generate this programmatically, not via LLM
        if self._manifest and self._manifest.dependencies:
            tech_lines = ["\n## Technology Stack\n"]
            if self._manifest.language:
                lang_str = self._manifest.language
                if self._manifest.language_version:
                    lang_str += f" {self._manifest.language_version}"
                tech_lines.append(f"- **{lang_str}**")

            # Group key dependencies
            key_deps = []
            for dep in sorted(self._manifest.dependencies.keys()):
                key_deps.append(dep)
            if key_deps:
                tech_lines.append(f"- **Dependencies**: {', '.join(key_deps[:10])}")
                if len(key_deps) > 10:
                    tech_lines.append(f"  - Plus {len(key_deps) - 10} more...")

            prompt_parts.append("\n".join(tech_lines))

        # Directory structure - use actual tree
        if self._repo_path:
            dir_tree = get_directory_tree(self._repo_path, max_depth=2, max_items=25)
            prompt_parts.append(f"\n## Directory Structure\n\n```\n{dir_tree}\n```\n")

        # Quick start - use actual entry points
        if self._manifest and self._manifest.entry_points:
            qs_lines = ["\n## Quick Start\n"]
            for cmd, target in sorted(self._manifest.entry_points.items()):
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

        llm_content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        # Build final content: title + LLM sections + pre-generated sections
        final_parts = [f"# {repo_name}\n"]

        # Add manifest description as subtitle if available
        if self._manifest and self._manifest.description:
            final_parts.append(f"\n{self._manifest.description}\n")

        # Add LLM-generated description and features
        final_parts.append(llm_content)

        # Add pre-generated sections (tech stack, directory, quick start)
        if self._manifest and self._manifest.dependencies:
            tech_lines = ["\n## Technology Stack\n"]
            if self._manifest.language:
                lang_str = self._manifest.language
                if self._manifest.language_version:
                    lang_str += f" {self._manifest.language_version}"
                tech_lines.append(f"- **{lang_str}**")

            key_deps = sorted(self._manifest.dependencies.keys())
            if key_deps:
                tech_lines.append(f"- **Dependencies**: {', '.join(key_deps[:12])}")
                if len(key_deps) > 12:
                    tech_lines.append(f"  - Plus {len(key_deps) - 12} more...")
            final_parts.append("\n".join(tech_lines))

        if self._repo_path:
            dir_tree = get_directory_tree(self._repo_path, max_depth=2, max_items=25)
            final_parts.append(f"\n## Directory Structure\n\n```\n{dir_tree}\n```")

        if self._manifest and self._manifest.entry_points:
            qs_lines = ["\n## Quick Start\n"]
            for cmd, target in sorted(self._manifest.entry_points.items()):
                qs_lines.append(f"- `{cmd}` → `{target}`")
            final_parts.append("\n".join(qs_lines))

        content = "\n".join(final_parts)

        return WikiPage(
            path="index.md",
            title="Overview",
            content=content,
            generated_at=time.time(),
        )

    async def _generate_architecture(self, index_status: IndexStatus) -> WikiPage:
        """Generate architecture documentation with diagrams and grounded facts."""
        # Gather multiple types of context for comprehensive architecture view

        # 1. Search for core/main components
        core_results = await self.vector_store.search(
            "main core primary class module",
            limit=15,
        )

        # 2. Search for architectural patterns
        pattern_results = await self.vector_store.search(
            "factory provider service handler controller",
            limit=10,
        )

        # 3. Search for data flow / pipeline
        flow_results = await self.vector_store.search(
            "process pipeline flow parse index generate",
            limit=10,
        )

        # 4. Get all classes for class list
        class_results = await self.vector_store.search(
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
        if self._repo_path:
            dir_structure = get_directory_tree(self._repo_path, max_depth=2, max_items=25)

        # Include dependencies for technology context
        dep_context = ""
        if self._manifest and self._manifest.dependencies:
            dep_context = "Key dependencies: " + ", ".join(
                sorted(self._manifest.dependencies.keys())[:15]
            )

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
- Write class names as plain text (e.g., "The WikiGenerator class") so they can be cross-linked

Format as markdown with clear sections."""

        content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        return WikiPage(
            path="architecture.md",
            title="Architecture",
            content=content,
            generated_at=time.time(),
        )

    async def _generate_module_docs(
        self, index_status: IndexStatus, full_rebuild: bool = False
    ) -> tuple[list[WikiPage], int, int]:
        """Generate documentation for each module/directory.

        Args:
            index_status: Index status with file information.
            full_rebuild: If True, regenerate all pages.

        Returns:
            Tuple of (pages list, generated count, skipped count).
        """
        pages = []
        pages_generated = 0
        pages_skipped = 0

        # Group files by top-level directory
        directories: dict[str, list[str]] = {}
        for file_info in index_status.files:
            parts = Path(file_info.path).parts
            if len(parts) > 1:
                dir_name = parts[0]
            else:
                dir_name = "root"
            directories.setdefault(dir_name, []).append(file_info.path)

        # Generate a page for each significant directory
        for dir_name, files in directories.items():
            if len(files) < 2:
                continue

            page_path = f"modules/{dir_name}.md"

            # Check if page needs regeneration (module pages depend on all files in that module)
            if not full_rebuild and not self._needs_regeneration(page_path, files):
                existing_page = await self._load_existing_page(page_path)
                if existing_page is not None:
                    pages.append(existing_page)
                    self._record_page_status(existing_page, files)
                    pages_skipped += 1
                    continue

            # Get chunks for this directory
            search_results = await self.vector_store.search(
                f"module {dir_name}",
                limit=15,
            )

            # Filter to chunks from this directory
            relevant_chunks = [r for r in search_results if r.chunk.file_path.startswith(dir_name)]

            if not relevant_chunks:
                continue

            context = "\n\n".join(
                [
                    f"File: {r.chunk.file_path}\nType: {r.chunk.chunk_type.value}\nName: {r.chunk.name}\n{r.chunk.content[:400]}"
                    for r in relevant_chunks[:10]
                ]
            )

            prompt = f"""Generate documentation for the '{dir_name}' module based ONLY on the code provided.

Files in module: {', '.join(files[:10])}{'...' if len(files) > 10 else ''}

Code context:
{context}

Generate documentation that includes:
1. **Module Purpose** - Explain what this module does based on the code shown
2. **Key Classes and Functions** - Describe each class/function visible in the code above. Write class names as plain text for cross-linking.
3. **How Components Interact** - Explain how the components shown work together
4. **Usage Examples** - Show how to use the components (use code blocks)
5. **Dependencies** - What other modules this depends on (based on imports shown)

CRITICAL CONSTRAINTS:
- ONLY describe classes and functions that appear in the code context above
- Do NOT invent additional components not shown
- Do NOT fabricate usage patterns or APIs not visible in the code
- Write class names as plain text (e.g., "The CodeParser class") for cross-linking

Format as markdown."""

            content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

            page = WikiPage(
                path=page_path,
                title=f"Module: {dir_name}",
                content=content,
                generated_at=time.time(),
            )
            pages.append(page)
            self._record_page_status(page, files)
            pages_generated += 1

        # Create modules index (always regenerate since it depends on module pages)
        if pages:
            modules_index = WikiPage(
                path="modules/index.md",
                title="Modules",
                content=self._generate_modules_index(pages),
                generated_at=time.time(),
            )
            pages.insert(0, modules_index)
            # Index depends on all files in all modules
            all_module_files = [f for files in directories.values() for f in files]
            self._record_page_status(modules_index, all_module_files)

        return pages, pages_generated, pages_skipped

    def _generate_modules_index(self, module_pages: list[WikiPage]) -> str:
        """Generate index page for modules."""
        lines = ["# Modules\n", "This section contains documentation for each module.\n"]

        for page in module_pages:
            if page.path != "modules/index.md":
                name = Path(page.path).stem
                lines.append(f"- [{page.title}]({name}.md)")

        return "\n".join(lines)

    async def _generate_file_docs(
        self,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None = None,
        full_rebuild: bool = False,
    ) -> tuple[list[WikiPage], int, int]:
        """Generate documentation for individual source files.

        Args:
            index_status: Index status with file information.
            progress_callback: Optional progress callback.
            full_rebuild: If True, regenerate all pages.

        Returns:
            Tuple of (pages list, generated count, skipped count).
        """
        pages = []
        pages_generated = 0
        pages_skipped = 0

        # Filter to significant files (skip __init__.py, test files for now)
        significant_files = [
            f
            for f in index_status.files
            if not f.path.endswith("__init__.py") and f.chunk_count >= 2  # Has meaningful content
        ]

        # Limit to avoid too many LLM calls
        max_files = self.config.wiki.max_file_docs
        if len(significant_files) > max_files:
            # Prioritize files with more chunks (more complex)
            significant_files = sorted(
                significant_files, key=lambda x: x.chunk_count, reverse=True
            )[:max_files]

        for file_info in significant_files:
            file_path = Path(file_info.path)

            # Create nested path structure: files/module/filename.md
            parts = file_path.parts
            if len(parts) > 1:
                wiki_path = f"files/{'/'.join(parts[:-1])}/{file_path.stem}.md"
            else:
                wiki_path = f"files/{file_path.stem}.md"

            # Check if this file page needs regeneration (depends only on this source file)
            source_files = [file_info.path]
            if not full_rebuild and not self._needs_regeneration(wiki_path, source_files):
                existing_page = await self._load_existing_page(wiki_path)
                if existing_page is not None:
                    # Still need to register entities for cross-linking
                    all_file_chunks = await self.vector_store.get_chunks_by_file(file_info.path)
                    self.entity_registry.register_from_chunks(all_file_chunks, wiki_path)
                    pages.append(existing_page)
                    self._record_page_status(existing_page, source_files)
                    pages_skipped += 1
                    continue

            # Get all chunks for this file
            search_results = await self.vector_store.search(
                f"file:{file_info.path}",
                limit=self.config.wiki.context_search_limit,
            )

            # Filter to chunks from this specific file
            file_chunks = [r for r in search_results if r.chunk.file_path == file_info.path]

            if not file_chunks:
                # Fallback: search by filename
                search_results = await self.vector_store.search(
                    file_path.stem,
                    limit=self.config.wiki.fallback_search_limit,
                )
                file_chunks = [r for r in search_results if r.chunk.file_path == file_info.path]

            if not file_chunks:
                continue

            # Build context from chunks
            context_parts = []
            for r in file_chunks[:15]:  # Limit context size
                chunk = r.chunk
                context_parts.append(
                    f"Type: {chunk.chunk_type.value}\n"
                    f"Name: {chunk.name}\n"
                    f"Lines: {chunk.start_line}-{chunk.end_line}\n"
                    f"```\n{chunk.content[:600]}\n```"
                )

            context = "\n\n".join(context_parts)

            prompt = f"""Generate documentation for the file '{file_info.path}' based ONLY on the code provided.

Language: {file_info.language}
Total code chunks: {file_info.chunk_count}

Code contents:
{context}

Generate documentation that includes:
1. **File Overview**: Purpose of this file based on the code shown
2. **Classes**: Document each class visible in the code with its purpose and key methods
3. **Functions**: Document each function with parameters and return values as shown
4. **Usage Examples**: Show how to use the components (based on their actual signatures)
5. **Related Components**: Mention other classes this file works with (based on imports/references shown)

CRITICAL CONSTRAINTS:
- ONLY document classes, methods, and functions that appear in the code above
- Do NOT invent additional methods or parameters not shown
- Do NOT fabricate usage examples with APIs not visible in the code
- Write class names as plain text (e.g., "The WikiGenerator class") for cross-linking
- Only use backticks for actual code snippets

Format as markdown with clear sections.
Do NOT include mermaid class diagrams - they will be auto-generated."""

            content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

            # Strip any LLM-generated class diagram sections (we add our own)
            # Remove "## Class Diagram" section and any mermaid classDiagram blocks
            content = re.sub(
                r"\n*##\s*Class\s*Diagram\s*\n+```mermaid\s*\n+classDiagram.*?```",
                "",
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )

            # Generate API reference section with type signatures
            abs_file_path = Path(index_status.repo_path) / file_info.path
            if abs_file_path.exists():
                api_docs = get_file_api_docs(abs_file_path)
                if api_docs:
                    content += "\n\n## API Reference\n\n" + api_docs

            # Generate class diagram if file has classes
            # Use get_chunks_by_file for complete chunk list (not just search results)
            all_file_chunks = await self.vector_store.get_chunks_by_file(file_info.path)
            class_diagram = generate_class_diagram(all_file_chunks)
            if class_diagram:
                content += "\n\n## Class Diagram\n\n" + class_diagram

            # Generate call graph diagram
            abs_file_path = Path(index_status.repo_path) / file_info.path
            if abs_file_path.exists():
                call_graph = get_file_call_graph(abs_file_path, Path(index_status.repo_path))
                if call_graph:
                    content += "\n\n## Call Graph\n\n```mermaid\n" + call_graph + "\n```"

            # Add usage examples from test files
            entity_names = [
                chunk.name for chunk in all_file_chunks
                if chunk.name and len(chunk.name) > 2
            ]
            if entity_names:
                examples_md = get_file_examples(
                    source_file=abs_file_path,
                    repo_root=Path(index_status.repo_path),
                    entity_names=entity_names,
                    max_examples=5,
                )
                if examples_md:
                    content += "\n\n" + examples_md

            # Register entities for cross-linking
            self.entity_registry.register_from_chunks(all_file_chunks, wiki_path)

            page = WikiPage(
                path=wiki_path,
                title=f"{file_path.name}",
                content=content,
                generated_at=time.time(),
            )
            pages.append(page)
            self._record_page_status(page, source_files)
            pages_generated += 1

        # Create files index (always regenerate since it depends on all file pages)
        if pages:
            all_file_paths = [f.path for f in significant_files]
            files_index = WikiPage(
                path="files/index.md",
                title="Source Files",
                content=self._generate_files_index(pages),
                generated_at=time.time(),
            )
            pages.insert(0, files_index)
            self._record_page_status(files_index, all_file_paths)

        return pages, pages_generated, pages_skipped

    def _generate_files_index(self, file_pages: list[WikiPage]) -> str:
        """Generate index page for file documentation."""
        lines = [
            "# Source Files\n",
            "Detailed documentation for individual source files.\n",
        ]

        # Group by directory
        by_dir: dict[str, list[WikiPage]] = {}
        for page in file_pages:
            if page.path == "files/index.md":
                continue
            parts = Path(page.path).parts
            if len(parts) > 2:
                dir_name = parts[1]  # files/DIR/file.md -> DIR
            else:
                dir_name = "root"
            by_dir.setdefault(dir_name, []).append(page)

        for dir_name, dir_pages in sorted(by_dir.items()):
            lines.append(f"\n## {dir_name}\n")
            for page in sorted(dir_pages, key=lambda p: p.title):
                # Make relative link from files/index.md
                rel_path = page.path.replace("files/", "")
                lines.append(f"- [{page.title}]({rel_path})")

        return "\n".join(lines)

    async def _generate_dependencies(self, index_status: IndexStatus) -> WikiPage:
        """Generate dependencies documentation with grounded facts from manifest."""
        # Build grounded dependency context
        facts_sections = []

        # 1. External dependencies from manifest (GROUNDED FACTS)
        if self._manifest and self._manifest.dependencies:
            deps_list = []
            for name, version in sorted(self._manifest.dependencies.items()):
                version_str = f" ({version})" if version and version != "*" else ""
                deps_list.append(f"- {name}{version_str}")
            facts_sections.append(
                "EXTERNAL DEPENDENCIES (from package manifest):\n" + "\n".join(deps_list[:30])
            )

        # 2. Dev dependencies from manifest (GROUNDED FACTS)
        if self._manifest and self._manifest.dev_dependencies:
            dev_deps_list = []
            for name, version in sorted(self._manifest.dev_dependencies.items()):
                version_str = f" ({version})" if version and version != "*" else ""
                dev_deps_list.append(f"- {name}{version_str}")
            facts_sections.append(
                "DEV DEPENDENCIES (from package manifest):\n" + "\n".join(dev_deps_list[:20])
            )

        # 3. Get import chunks for internal dependency analysis
        search_results = await self.vector_store.search(
            "import require include from",
            limit=100,
        )

        import_chunks = [r for r in search_results if r.chunk.chunk_type.value == "import"]

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

        content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        # Generate auto-generated module dependency graph
        dep_graph = generate_dependency_graph(import_chunks, "local_deepwiki")
        if dep_graph:
            content += "\n\n## Module Dependency Graph\n\n"
            content += "The following diagram shows internal module dependencies:\n\n"
            content += dep_graph

        return WikiPage(
            path="dependencies.md",
            title="Dependencies",
            content=content,
            generated_at=time.time(),
        )

    async def _generate_changelog(self) -> WikiPage | None:
        """Generate changelog page from git history.

        Returns:
            WikiPage with changelog content, or None if not a git repo.
        """
        from local_deepwiki.generators.changelog import generate_changelog_content

        content = generate_changelog_content(self._repo_path)
        if not content:
            logger.debug("No changelog generated (not a git repo or no commits)")
            return None

        return WikiPage(
            path="changelog.md",
            title="Changelog",
            content=content,
            generated_at=time.time(),
        )

    async def _write_page(self, page: WikiPage) -> None:
        """Write a wiki page to disk asynchronously."""
        page_path = self.wiki_path / page.path
        content = page.content

        def _sync_write() -> None:
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(content)

        await asyncio.to_thread(_sync_write)


async def generate_wiki(
    repo_path: Path,
    wiki_path: Path,
    vector_store: VectorStore,
    index_status: IndexStatus,
    config: Config | None = None,
    llm_provider: str | None = None,
    progress_callback: ProgressCallback | None = None,
    full_rebuild: bool = False,
) -> WikiStructure:
    """Convenience function to generate wiki documentation.

    Args:
        repo_path: Path to the repository.
        wiki_path: Path for wiki output.
        vector_store: Indexed vector store.
        index_status: Index status.
        config: Optional configuration.
        llm_provider: Optional LLM provider override.
        progress_callback: Optional progress callback.
        full_rebuild: If True, regenerate all pages. Otherwise, only regenerate changed pages.

    Returns:
        WikiStructure with generated pages.
    """
    generator = WikiGenerator(
        wiki_path=wiki_path,
        vector_store=vector_store,
        config=config,
        llm_provider_name=llm_provider,
    )
    return await generator.generate(index_status, progress_callback, full_rebuild)
