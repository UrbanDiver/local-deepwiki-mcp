"""Wiki documentation generator using LLM providers."""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.callgraph import get_file_call_graph
from local_deepwiki.generators.crosslinks import EntityRegistry, add_cross_links
from local_deepwiki.generators.search import write_search_index
from local_deepwiki.generators.see_also import RelationshipAnalyzer, add_see_also_sections
from local_deepwiki.models import (
    IndexStatus,
    WikiGenerationStatus,
    WikiPage,
    WikiPageStatus,
    WikiStructure,
)
from local_deepwiki.providers.llm import get_llm_provider


SYSTEM_PROMPT = """You are a technical documentation expert. Generate clear, concise documentation for code.
- Use markdown formatting
- Include code examples where helpful
- Focus on explaining what the code does and how to use it
- Be accurate and avoid speculation
- Keep explanations practical and actionable
- When mentioning class or function names in prose explanations, write them as plain text (e.g., "The WikiGenerator class") rather than inline code, so they can be cross-linked
- Only use backticks for code snippets, variable names in context, or when showing exact syntax"""


def generate_class_diagram(chunks: list) -> str | None:
    """Generate a Mermaid class diagram from code chunks.

    Args:
        chunks: List of CodeChunk objects.

    Returns:
        Mermaid class diagram markdown string, or None if no classes found.
    """
    from local_deepwiki.models import ChunkType

    # Collect classes, their methods, and inheritance info
    classes: dict[str, list[str]] = {}
    class_contents: dict[str, str] = {}  # Store content for method extraction
    inheritance: dict[str, list[str]] = {}  # child -> [parents]
    standalone_functions: list[str] = []

    for chunk in chunks:
        # Handle both CodeChunk objects and SearchResult objects (which have .chunk)
        if hasattr(chunk, 'chunk'):
            chunk = chunk.chunk
        if chunk.chunk_type == ChunkType.CLASS:
            class_name = chunk.name or "Unknown"
            if class_name not in classes:
                classes[class_name] = []
                class_contents[class_name] = chunk.content
            # Extract parent classes from metadata
            parent_classes = chunk.metadata.get("parent_classes", [])
            if parent_classes:
                inheritance[class_name] = parent_classes
        elif chunk.chunk_type == ChunkType.METHOD:
            parent = chunk.parent_name or "Unknown"
            method_name = chunk.name or "unknown"
            if parent not in classes:
                classes[parent] = []
            # Avoid duplicates
            if method_name not in classes[parent]:
                classes[parent].append(method_name)
        elif chunk.chunk_type == ChunkType.FUNCTION:
            func_name = chunk.name or "unknown"
            if func_name not in standalone_functions:
                standalone_functions.append(func_name)

    # For classes without METHOD chunks, extract methods from content
    # Pattern matches: def method_name( or async def method_name(
    method_pattern = re.compile(r'(?:async\s+)?def\s+(\w+)\s*\(')
    for class_name, methods in classes.items():
        if not methods and class_name in class_contents:
            content = class_contents[class_name]
            # Skip the first match if it's the class definition line
            found_methods = method_pattern.findall(content)
            for method in found_methods:
                if method not in methods:
                    methods.append(method)

    # Filter to only classes with methods (empty classes cause Mermaid syntax errors)
    classes_with_methods = {k: v for k, v in classes.items() if v}

    # If no classes with methods, nothing to diagram
    if not classes_with_methods:
        return None

    # Helper to sanitize names for Mermaid
    def sanitize(name: str) -> str:
        return name.replace("<", "_").replace(">", "_").replace(" ", "_")

    # Build Mermaid diagram
    lines = ["```mermaid", "classDiagram"]

    for class_name, methods in sorted(classes_with_methods.items()):
        safe_name = sanitize(class_name)
        lines.append(f"    class {safe_name} {{")
        for method in methods:
            # Mark private methods with - prefix, others with +
            prefix = "-" if method.startswith("_") else "+"
            safe_method = sanitize(method)
            lines.append(f"        {prefix}{safe_method}()")
        lines.append("    }")

    # Add inheritance relationships
    for child, parents in sorted(inheritance.items()):
        if child in classes_with_methods:
            safe_child = sanitize(child)
            for parent in parents:
                safe_parent = sanitize(parent)
                # Use --|> for inheritance (child inherits from parent)
                lines.append(f"    {safe_child} --|> {safe_parent}")

    lines.append("```")

    return "\n".join(lines)


def generate_dependency_graph(chunks: list, project_name: str = "project") -> str | None:
    """Generate a Mermaid flowchart showing module dependencies.

    Args:
        chunks: List of CodeChunk objects (should include IMPORT chunks).
        project_name: Name of the project for filtering internal imports.

    Returns:
        Mermaid flowchart markdown string, or None if no dependencies found.
    """
    from local_deepwiki.models import ChunkType

    # Collect dependencies: file -> set of imports
    dependencies: dict[str, set[str]] = {}

    for chunk in chunks:
        if hasattr(chunk, 'chunk'):
            chunk = chunk.chunk
        if chunk.chunk_type != ChunkType.IMPORT:
            continue

        file_path = chunk.file_path
        # Get module name from file path (e.g., src/local_deepwiki/core/indexer.py -> core.indexer)
        module = _path_to_module(file_path)
        if not module:
            continue

        if module not in dependencies:
            dependencies[module] = set()

        # Parse imports from content
        for line in chunk.content.split('\n'):
            line = line.strip()
            if not line:
                continue

            imported = _parse_import_line(line, project_name)
            if imported:
                dependencies[module].add(imported)

    if not dependencies:
        return None

    # Filter to only internal dependencies (within the project)
    internal_modules = set(dependencies.keys())
    internal_deps: dict[str, set[str]] = {}

    for module, imports in dependencies.items():
        internal_imports = {imp for imp in imports if imp in internal_modules}
        if internal_imports:
            internal_deps[module] = internal_imports

    if not internal_deps:
        return None

    # Build Mermaid flowchart
    lines = ["```mermaid", "flowchart TD"]

    # Create node definitions with short IDs
    node_ids: dict[str, str] = {}
    for i, module in enumerate(sorted(internal_modules)):
        node_id = f"M{i}"
        node_ids[module] = node_id
        # Use last part of module name for display
        display_name = module.split('.')[-1]
        lines.append(f"    {node_id}[{display_name}]")

    # Add edges
    for module, imports in sorted(internal_deps.items()):
        from_id = node_ids.get(module)
        if not from_id:
            continue
        for imp in sorted(imports):
            to_id = node_ids.get(imp)
            if to_id and from_id != to_id:
                lines.append(f"    {from_id} --> {to_id}")

    lines.append("```")

    return "\n".join(lines)


def _path_to_module(file_path: str) -> str | None:
    """Convert file path to module name.

    Args:
        file_path: Path like 'src/local_deepwiki/core/indexer.py'

    Returns:
        Module name like 'core.indexer', or None if not applicable.
    """
    from pathlib import Path

    p = Path(file_path)
    if p.suffix != '.py':
        return None
    if p.name.startswith('__'):
        return None

    # Remove src/local_deepwiki prefix and .py suffix
    parts = list(p.parts)

    # Find the main package directory
    try:
        # Look for common patterns
        if 'src' in parts:
            idx = parts.index('src')
            parts = parts[idx + 1:]
        elif 'local_deepwiki' in parts:
            idx = parts.index('local_deepwiki')
            parts = parts[idx:]
    except (ValueError, IndexError):
        pass

    # Remove .py extension from last part
    if parts and parts[-1].endswith('.py'):
        parts[-1] = parts[-1][:-3]

    # Skip __init__ and similar
    if parts and parts[-1].startswith('__'):
        return None

    return '.'.join(parts) if parts else None


def _parse_import_line(line: str, project_name: str) -> str | None:
    """Parse a Python import line to extract the imported module.

    Args:
        line: Import statement line.
        project_name: Project name for filtering.

    Returns:
        Full imported module name (e.g., 'local_deepwiki.core.chunker'), or None if not internal.
    """
    # Handle: from local_deepwiki.core.chunker import CodeChunker
    if line.startswith('from '):
        parts = line.split()
        if len(parts) >= 2:
            module = parts[1]
            # Check if it's an internal import
            if 'local_deepwiki' in module:
                # Keep full module path for matching
                if module.startswith('local_deepwiki.'):
                    return module
                elif '.local_deepwiki.' in module:
                    # Extract from nested path
                    idx = module.find('local_deepwiki.')
                    return module[idx:]
    # Handle: import local_deepwiki.core.chunker
    elif line.startswith('import '):
        parts = line.split()
        if len(parts) >= 2:
            module = parts[1].split(',')[0]  # Handle multiple imports
            if module.startswith('local_deepwiki.'):
                return module
    return None


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

    def _load_wiki_status(self) -> WikiGenerationStatus | None:
        """Load previous wiki generation status.

        Returns:
            WikiGenerationStatus or None if not found.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        if not status_path.exists():
            return None

        try:
            with open(status_path) as f:
                data = json.load(f)
            return WikiGenerationStatus.model_validate(data)
        except Exception:
            return None

    def _save_wiki_status(self, status: WikiGenerationStatus) -> None:
        """Save wiki generation status.

        Args:
            status: The WikiGenerationStatus to save.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        with open(status_path, "w") as f:
            json.dump(status.model_dump(), f, indent=2)

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

    def _load_existing_page(self, page_path: str) -> WikiPage | None:
        """Load an existing wiki page from disk.

        Args:
            page_path: Relative path to the page.

        Returns:
            WikiPage if found, None otherwise.
        """
        full_path = self.wiki_path / page_path
        if not full_path.exists():
            return None

        try:
            content = full_path.read_text()
            # Get title from previous status or derive from path
            prev_page = self._previous_status.pages.get(page_path) if self._previous_status else None
            title = Path(page_path).stem.replace("_", " ").title()
            generated_at = prev_page.generated_at if prev_page else time.time()

            return WikiPage(
                path=page_path,
                title=title,
                content=content,
                generated_at=generated_at,
            )
        except Exception:
            return None

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
        source_hashes = {
            f: self._file_hashes.get(f, "")
            for f in source_files
        }

        self._page_statuses[page.path] = WikiPageStatus(
            path=page.path,
            source_files=source_files,
            source_hashes=source_hashes,
            content_hash=self._compute_content_hash(page.content),
            generated_at=page.generated_at,
        )

    async def generate(
        self,
        index_status: IndexStatus,
        progress_callback: Any = None,
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
        pages: list[WikiPage] = []
        total_steps = 8  # overview, architecture, modules, files, dependencies, cross-links, see-also, search
        pages_generated = 0
        pages_skipped = 0

        # Build file hash map for incremental generation
        self._file_hashes = {f.path: f.hash for f in index_status.files}
        all_source_files = list(self._file_hashes.keys())

        # Load previous wiki status for incremental updates
        if not full_rebuild:
            self._previous_status = self._load_wiki_status()

        # Generate index page (overview) - depends on all files
        if progress_callback:
            progress_callback("Generating overview", 0, total_steps)

        overview_path = "index.md"
        if full_rebuild or self._needs_regeneration(overview_path, all_source_files):
            overview_page = await self._generate_overview(index_status)
            pages_generated += 1
        else:
            overview_page = self._load_existing_page(overview_path)
            if overview_page is None:
                overview_page = await self._generate_overview(index_status)
                pages_generated += 1
            else:
                pages_skipped += 1

        pages.append(overview_page)
        self._record_page_status(overview_page, all_source_files)
        self._write_page(overview_page)

        # Generate architecture page - depends on all files
        if progress_callback:
            progress_callback("Generating architecture docs", 1, total_steps)

        architecture_path = "architecture.md"
        if full_rebuild or self._needs_regeneration(architecture_path, all_source_files):
            architecture_page = await self._generate_architecture(index_status)
            pages_generated += 1
        else:
            architecture_page = self._load_existing_page(architecture_path)
            if architecture_page is None:
                architecture_page = await self._generate_architecture(index_status)
                pages_generated += 1
            else:
                pages_skipped += 1

        pages.append(architecture_page)
        self._record_page_status(architecture_page, all_source_files)
        self._write_page(architecture_page)

        # Collect import chunks for relationship analysis (needed for See Also)
        import_results = await self.vector_store.search(
            "import require include",
            limit=200,
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
            self._write_page(page)

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
            self._write_page(page)

        # Generate dependencies page - depends on all files
        if progress_callback:
            progress_callback("Generating dependencies", 4, total_steps)

        deps_path = "dependencies.md"
        if full_rebuild or self._needs_regeneration(deps_path, all_source_files):
            deps_page = await self._generate_dependencies(index_status)
            pages_generated += 1
        else:
            deps_page = self._load_existing_page(deps_path)
            if deps_page is None:
                deps_page = await self._generate_dependencies(index_status)
                pages_generated += 1
            else:
                pages_skipped += 1

        pages.append(deps_page)
        self._record_page_status(deps_page, all_source_files)
        self._write_page(deps_page)

        # Apply cross-links to all pages
        if progress_callback:
            progress_callback("Adding cross-links", 5, total_steps)

        pages = add_cross_links(pages, self.entity_registry)

        # Add See Also sections
        if progress_callback:
            progress_callback("Adding See Also sections", 6, total_steps)

        pages = add_see_also_sections(pages, self.relationship_analyzer)

        # Re-write pages with cross-links and See Also sections
        for page in pages:
            self._write_page(page)

        # Generate search index
        if progress_callback:
            progress_callback("Generating search index", 7, total_steps)

        write_search_index(self.wiki_path, pages)

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
        self._save_wiki_status(wiki_status)

        if progress_callback:
            progress_callback(
                f"Wiki generation complete ({pages_generated} generated, {pages_skipped} unchanged)",
                total_steps,
                total_steps,
            )

        return WikiStructure(root=str(self.wiki_path), pages=pages)

    async def _generate_overview(self, index_status: IndexStatus) -> WikiPage:
        """Generate the main overview/index page."""
        # Gather context from vector store
        stats = self.vector_store.get_stats()

        prompt = f"""Generate a README-style overview for this codebase:

Repository: {Path(index_status.repo_path).name}
Total Files: {index_status.total_files}
Languages: {', '.join(f'{lang} ({count} files)' for lang, count in index_status.languages.items())}
Total Code Chunks: {index_status.total_chunks}

Generate a clear overview that includes:
1. Project title and brief description (infer from the code structure)
2. Key features/capabilities
3. Technology stack
4. Directory structure overview
5. Quick start guide

Format as markdown with proper headings."""

        content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        return WikiPage(
            path="index.md",
            title="Overview",
            content=content,
            generated_at=time.time(),
        )

    async def _generate_architecture(self, index_status: IndexStatus) -> WikiPage:
        """Generate architecture documentation with diagrams."""
        # Get module-level chunks for architecture overview
        search_results = await self.vector_store.search(
            "architecture structure main module",
            limit=20,
        )

        context = "\n\n".join([
            f"File: {r.chunk.file_path}\n{r.chunk.content[:500]}"
            for r in search_results
        ])

        prompt = f"""Based on this codebase context, generate architecture documentation:

{context}

Generate documentation that includes:
1. System architecture overview - describe how the system works at a high level
2. Key components and their responsibilities - explain what each major class does and how they interact. When describing classes like WikiGenerator, VectorStore, CodeChunker, etc., write their names as plain text in sentences (not in backticks) so they can be cross-linked.
3. Data flow between components - explain how data moves through the system, mentioning specific classes involved
4. A Mermaid diagram showing the architecture (use ```mermaid code blocks)
5. Design patterns used - describe patterns and which classes implement them

IMPORTANT: Write class and component names as plain text in prose (e.g., "The WikiGenerator class uses VectorStore to retrieve code context") rather than using backticks, so they can be automatically linked to their documentation pages.

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
                existing_page = self._load_existing_page(page_path)
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
            relevant_chunks = [
                r for r in search_results
                if r.chunk.file_path.startswith(dir_name)
            ]

            if not relevant_chunks:
                continue

            context = "\n\n".join([
                f"File: {r.chunk.file_path}\nType: {r.chunk.chunk_type.value}\nName: {r.chunk.name}\n{r.chunk.content[:400]}"
                for r in relevant_chunks[:10]
            ])

            prompt = f"""Generate documentation for the '{dir_name}' module:

Files in module: {', '.join(files[:10])}{'...' if len(files) > 10 else ''}

Code context:
{context}

Generate documentation that includes:
1. Module purpose and responsibilities - explain what this module does
2. Key classes and functions - describe each major class (e.g., WikiGenerator, VectorStore, CodeChunker) and what it does. Write class names as plain text in sentences.
3. How components interact - explain how classes in this module work together and with other modules
4. Usage examples (use code blocks for actual code)
5. Dependencies - what other modules this depends on

IMPORTANT: When mentioning class names in prose explanations, write them as plain text (e.g., "The CodeParser class handles parsing") rather than using backticks, so they can be cross-linked to their documentation.

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
        progress_callback: Any = None,
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
            f for f in index_status.files
            if not f.path.endswith("__init__.py")
            and f.chunk_count >= 2  # Has meaningful content
        ]

        # Limit to avoid too many LLM calls
        max_files = 20
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
                existing_page = self._load_existing_page(wiki_path)
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
                limit=50,
            )

            # Filter to chunks from this specific file
            file_chunks = [
                r for r in search_results
                if r.chunk.file_path == file_info.path
            ]

            if not file_chunks:
                # Fallback: search by filename
                search_results = await self.vector_store.search(
                    file_path.stem,
                    limit=30,
                )
                file_chunks = [
                    r for r in search_results
                    if r.chunk.file_path == file_info.path
                ]

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

            prompt = f"""Generate documentation for the file '{file_info.path}':

Language: {file_info.language}
Total code chunks: {file_info.chunk_count}

Code contents:
{context}

Generate comprehensive documentation that includes:
1. **File Overview**: Purpose and responsibility of this file. Explain how it relates to other components in the codebase.
2. **Classes**: Document each class with its purpose, key methods, and usage. Describe relationships with other classes.
3. **Functions**: Document each function with parameters, return values, and purpose.
4. **Usage Examples**: Show how to use the main components (use code blocks for examples).
5. **Related Components**: Mention other classes or modules this file works with, written as plain text in sentences (e.g., "This class works with VectorStore to store embeddings").

IMPORTANT: When mentioning class names like VectorStore, WikiGenerator, CodeChunker, etc. in explanatory prose, write them as plain text without backticks so they can be automatically cross-linked. Only use backticks for actual code snippets.

Format as markdown with clear sections. Be specific about the actual code.
Do NOT include mermaid class diagrams - they will be auto-generated."""

            content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

            # Strip any LLM-generated class diagram sections (we add our own)
            # Remove "## Class Diagram" section and any mermaid classDiagram blocks
            content = re.sub(
                r'\n*##\s*Class\s*Diagram\s*\n+```mermaid\s*\n+classDiagram.*?```',
                '',
                content,
                flags=re.DOTALL | re.IGNORECASE
            )

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
        """Generate dependencies documentation."""
        # Get import chunks - use higher limit for complete dependency graph
        search_results = await self.vector_store.search(
            "import require include dependencies",
            limit=100,
        )

        import_chunks = [r for r in search_results if r.chunk.chunk_type.value == "import"]

        context = "\n\n".join([
            f"File: {r.chunk.file_path}\n{r.chunk.content}"
            for r in import_chunks[:20]
        ])

        prompt = f"""Based on these import statements, generate a dependencies overview:

{context}

Generate documentation that includes:
1. External dependencies (libraries, packages) - list third-party libraries and their purposes
2. Internal module dependencies - explain how internal modules depend on each other. Describe which classes (like WikiGenerator, VectorStore, CodeChunker, RepositoryIndexer) use which other classes.
3. Dependency patterns - describe notable patterns like dependency injection or the provider pattern, mentioning specific classes involved

IMPORTANT: When mentioning class names in explanations, write them as plain text in sentences (e.g., "WikiGenerator depends on VectorStore for code retrieval") rather than using backticks, so they can be cross-linked.

Do NOT include a Mermaid diagram - one will be auto-generated.

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

    def _write_page(self, page: WikiPage) -> None:
        """Write a wiki page to disk."""
        page_path = self.wiki_path / page.path
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(page.content)


async def generate_wiki(
    repo_path: Path,
    wiki_path: Path,
    vector_store: VectorStore,
    index_status: IndexStatus,
    config: Config | None = None,
    llm_provider: str | None = None,
    progress_callback: Any = None,
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
