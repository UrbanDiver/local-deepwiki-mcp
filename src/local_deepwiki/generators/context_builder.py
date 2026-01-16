"""Build rich context for LLM documentation generation.

This module extracts and assembles contextual information from the codebase
to help the LLM generate more accurate and comprehensive documentation.
Context includes:
- Import statements showing dependencies
- Caller information from other files
- Related files based on imports/dependencies
- Type definitions used by the code
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.callgraph import CallGraphExtractor, build_reverse_call_graph
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk

logger = get_logger(__name__)


@dataclass
class FileContext:
    """Rich context for a source file."""

    file_path: str
    imports: list[str] = field(default_factory=list)
    imported_modules: list[str] = field(default_factory=list)
    callers: dict[str, list[str]] = field(default_factory=dict)  # entity -> [caller files]
    related_files: list[str] = field(default_factory=list)
    type_definitions: list[str] = field(default_factory=list)  # Type hints used


def extract_imports_from_chunks(chunks: list[CodeChunk]) -> tuple[list[str], list[str]]:
    """Extract import statements and module names from code chunks.

    Args:
        chunks: List of code chunks for a file.

    Returns:
        Tuple of (import_statements, module_names).
    """
    imports: list[str] = []
    modules: list[str] = []

    for chunk in chunks:
        if chunk.chunk_type == ChunkType.IMPORT:
            # Split import block into individual lines
            for line in chunk.content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                imports.append(line)

                # Extract module name
                module = _parse_import_module(line)
                if module and module not in modules:
                    modules.append(module)

    return imports, modules


def _parse_import_module(import_line: str) -> str | None:
    """Parse an import line to extract the module name.

    Args:
        import_line: An import statement like "from foo import bar" or "import baz".

    Returns:
        The top-level module name, or None if parsing fails.
    """
    # Handle "from X import Y"
    from_match = re.match(r"from\s+([\w.]+)\s+import", import_line)
    if from_match:
        module = from_match.group(1)
        # Return top-level module
        return module.split(".")[0]

    # Handle "import X"
    import_match = re.match(r"import\s+([\w.]+)", import_line)
    if import_match:
        module = import_match.group(1)
        return module.split(".")[0]

    return None


async def get_callers_from_other_files(
    file_path: str,
    entity_names: list[str],
    repo_path: Path,
    vector_store: VectorStore,
    max_files: int = 10,
) -> dict[str, list[str]]:
    """Find which other files call entities defined in this file.

    Args:
        file_path: Path to the source file.
        entity_names: Names of functions/classes defined in the file.
        repo_path: Repository root path.
        vector_store: Vector store for searching code.
        max_files: Maximum number of caller files to return per entity.

    Returns:
        Mapping of entity name to list of calling file paths.
    """
    callers: dict[str, list[str]] = {}

    for entity_name in entity_names:
        if len(entity_name) < 4:  # Skip short names (likely false positives)
            continue

        # Search for uses of this entity
        try:
            results = await vector_store.search(
                f"{entity_name}(",  # Function call pattern
                limit=20,
            )

            caller_files: set[str] = set()
            for result in results:
                chunk = result.chunk
                # Skip the file that defines the entity
                if chunk.file_path == file_path:
                    continue
                # Skip if entity name not actually in the content
                if entity_name not in chunk.content:
                    continue
                caller_files.add(chunk.file_path)

                if len(caller_files) >= max_files:
                    break

            if caller_files:
                callers[entity_name] = sorted(caller_files)[:max_files]

        except Exception as e:
            logger.debug(f"Error searching for callers of {entity_name}: {e}")

    return callers


async def find_related_files(
    file_path: str,
    imported_modules: list[str],
    vector_store: VectorStore,
    max_files: int = 5,
) -> list[str]:
    """Find files that are closely related to this one.

    Related files are those that:
    - Are imported by this file (same package)
    - Import this file

    Args:
        file_path: Path to the source file.
        imported_modules: Modules imported by this file.
        vector_store: Vector store for searching.
        max_files: Maximum number of related files to return.

    Returns:
        List of related file paths.
    """
    related: set[str] = set()

    # Find files that this file imports (within same project)
    for module in imported_modules:
        try:
            results = await vector_store.search(
                f"def {module}" if not module[0].isupper() else f"class {module}",
                limit=5,
            )
            for result in results:
                if result.chunk.file_path != file_path:
                    related.add(result.chunk.file_path)
        except Exception:
            pass

    return sorted(related)[:max_files]


async def get_type_definitions_used(
    chunks: list[CodeChunk],
    vector_store: VectorStore,
    max_types: int = 10,
) -> list[str]:
    """Extract type definitions used in the file that are defined elsewhere.

    Args:
        chunks: Code chunks for the file.
        vector_store: Vector store for searching.
        max_types: Maximum number of type definitions to return.

    Returns:
        List of type definition snippets.
    """
    type_defs: list[str] = []
    type_names: set[str] = set()

    # Find type annotations in chunks
    type_pattern = re.compile(r":\s*([A-Z][a-zA-Z0-9_]+)")
    return_pattern = re.compile(r"->\s*([A-Z][a-zA-Z0-9_]+)")

    for chunk in chunks:
        # Find type annotations
        for match in type_pattern.finditer(chunk.content):
            type_name = match.group(1)
            if type_name not in type_names and len(type_name) > 3:
                type_names.add(type_name)
        # Find return type annotations
        for match in return_pattern.finditer(chunk.content):
            type_name = match.group(1)
            if type_name not in type_names and len(type_name) > 3:
                type_names.add(type_name)

    # Look up definitions of these types
    for type_name in list(type_names)[:max_types]:
        try:
            results = await vector_store.search(
                f"class {type_name}",
                limit=3,
            )
            for result in results:
                if result.chunk.chunk_type == ChunkType.CLASS:
                    # Get just the class definition line
                    first_line = result.chunk.content.split("\n")[0]
                    if type_name in first_line:
                        type_defs.append(f"{type_name}: {first_line}")
                        break
        except Exception:
            pass

    return type_defs


async def build_file_context(
    file_path: str,
    chunks: list[CodeChunk],
    repo_path: Path,
    vector_store: VectorStore,
) -> FileContext:
    """Build comprehensive context for a source file.

    Args:
        file_path: Path to the source file.
        chunks: Code chunks for the file.
        repo_path: Repository root path.
        vector_store: Vector store for searching.

    Returns:
        FileContext with all extracted information.
    """
    # Extract imports
    imports, imported_modules = extract_imports_from_chunks(chunks)

    # Get entity names for caller lookup
    entity_names = [
        chunk.name for chunk in chunks
        if chunk.name and chunk.chunk_type in (ChunkType.CLASS, ChunkType.FUNCTION)
    ]

    # Get callers from other files
    callers = await get_callers_from_other_files(
        file_path=file_path,
        entity_names=entity_names,
        repo_path=repo_path,
        vector_store=vector_store,
    )

    # Find related files
    related_files = await find_related_files(
        file_path=file_path,
        imported_modules=imported_modules,
        vector_store=vector_store,
    )

    # Get type definitions used
    type_definitions = await get_type_definitions_used(chunks, vector_store)

    return FileContext(
        file_path=file_path,
        imports=imports,
        imported_modules=imported_modules,
        callers=callers,
        related_files=related_files,
        type_definitions=type_definitions,
    )


def format_context_for_llm(context: FileContext, max_imports: int = 15) -> str:
    """Format file context as text for the LLM prompt.

    Args:
        context: The file context to format.
        max_imports: Maximum number of imports to include.

    Returns:
        Formatted context string.
    """
    parts: list[str] = []

    # Imports section
    if context.imports:
        parts.append("## Dependencies (Imports)")
        parts.append("This file imports from:")
        for imp in context.imports[:max_imports]:
            parts.append(f"  {imp}")
        if len(context.imports) > max_imports:
            parts.append(f"  ... and {len(context.imports) - max_imports} more")
        parts.append("")

    # Callers section (who uses this file)
    if context.callers:
        parts.append("## External Usage")
        parts.append("Functions/classes in this file are called from:")
        for entity, caller_files in list(context.callers.items())[:10]:
            files_str = ", ".join(Path(f).stem for f in caller_files[:3])
            if len(caller_files) > 3:
                files_str += f" +{len(caller_files) - 3} more"
            parts.append(f"  - `{entity}`: used by {files_str}")
        parts.append("")

    # Related files section
    if context.related_files:
        parts.append("## Related Files")
        parts.append("Closely related files in this project:")
        for f in context.related_files[:5]:
            parts.append(f"  - {f}")
        parts.append("")

    # Type definitions section
    if context.type_definitions:
        parts.append("## Type Definitions Used")
        parts.append("Key types referenced in this file:")
        for type_def in context.type_definitions[:8]:
            parts.append(f"  - {type_def}")
        parts.append("")

    return "\n".join(parts) if parts else ""
