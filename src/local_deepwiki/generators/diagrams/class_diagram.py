"""Class diagram generation using Mermaid."""

from __future__ import annotations

import re
from pathlib import Path

from local_deepwiki.models import ChunkType, CodeChunk

from ._utils import ClassInfo, _unwrap_chunk, sanitize_mermaid_name


def _collect_class_from_chunk(
    chunk: CodeChunk,
    classes: dict[str, ClassInfo],
    methods_by_class: dict[str, list[tuple[str, str | None]]],
    show_attributes: bool,
) -> None:
    """Extract class info from a CLASS chunk and add to dictionaries."""
    class_name = chunk.name or "Unknown"
    if class_name in classes:
        return

    attributes = _extract_class_attributes(
        chunk.content, chunk.language.value if hasattr(chunk, "language") else "python"
    )

    is_abstract = (
        "ABC" in str(chunk.metadata.get("parent_classes", []))
        or "abstract" in chunk.content.lower()
    )
    is_dataclass = "@dataclass" in chunk.content or "BaseModel" in str(
        chunk.metadata.get("parent_classes", [])
    )

    classes[class_name] = ClassInfo(
        name=class_name,
        methods=[],
        attributes=attributes if show_attributes else [],
        parents=chunk.metadata.get("parent_classes", []),
        is_abstract=is_abstract,
        is_dataclass=is_dataclass,
        docstring=chunk.docstring,
    )
    methods_by_class[class_name] = []


def _collect_method_from_chunk(
    chunk: CodeChunk,
    methods_by_class: dict[str, list[tuple[str, str | None]]],
    show_types: bool,
) -> None:
    """Extract method info from a METHOD chunk and add to dictionary."""
    parent = chunk.parent_name or "Unknown"
    method_name = chunk.name or "unknown"

    signature = _extract_method_signature(chunk.content) if show_types else None

    if parent not in methods_by_class:
        methods_by_class[parent] = []

    existing = [m[0] for m in methods_by_class[parent]]
    if method_name not in existing:
        methods_by_class[parent].append((method_name, signature))


def _extract_methods_from_class_content(
    chunks: list,
    classes: dict[str, ClassInfo],
    methods_by_class: dict[str, list[tuple[str, str | None]]],
    show_types: bool,
) -> None:
    """Extract methods from class content for classes without METHOD chunks."""
    method_pattern = re.compile(
        r"(?:async\s+)?def\s+(\w+)\s*\([^)]*\)(?:\s*->\s*([^:]+))?:"
    )

    for class_name in classes:
        if methods_by_class.get(class_name):
            continue

        for chunk in chunks:
            chunk = _unwrap_chunk(chunk)
            if chunk.chunk_type == ChunkType.CLASS and chunk.name == class_name:
                for match in method_pattern.finditer(chunk.content):
                    method_name = match.group(1)
                    return_type = match.group(2)
                    if method_name not in [
                        m[0] for m in methods_by_class.get(class_name, [])
                    ]:
                        if class_name not in methods_by_class:
                            methods_by_class[class_name] = []
                        sig = (
                            f"() -> {return_type.strip()}"
                            if return_type and show_types
                            else "()"
                        )
                        methods_by_class[class_name].append((method_name, sig))


def _build_class_lines(
    class_name: str,
    class_info: ClassInfo,
    methods_by_class: dict[str, list[tuple[str, str | None]]],
    max_methods: int,
    show_types: bool,
) -> list[str]:
    """Build Mermaid diagram lines for a single class."""
    lines: list[str] = []
    safe_name = sanitize_mermaid_name(class_name)

    lines.append(f"    class {safe_name} {{")
    if class_info.is_dataclass:
        lines.append("        <<dataclass>>")
    elif class_info.is_abstract:
        lines.append("        <<abstract>>")

    for attr in class_info.attributes[:10]:
        lines.append(f"        {attr}")

    method_list = methods_by_class.get(class_name, [])
    for method_name, signature in method_list[:max_methods]:
        prefix = "-" if method_name.startswith("_") else "+"
        safe_method = sanitize_mermaid_name(method_name)
        if signature and show_types:
            lines.append(f"        {prefix}{safe_method}{signature}")
        else:
            lines.append(f"        {prefix}{safe_method}()")

    lines.append("    }")
    return lines


def _build_inheritance_lines(classes: dict[str, ClassInfo]) -> list[str]:
    """Build Mermaid inheritance relationship lines."""
    lines: list[str] = []
    for class_name, class_info in sorted(classes.items()):
        safe_child = sanitize_mermaid_name(class_name)
        for parent in class_info.parents:
            safe_parent = sanitize_mermaid_name(parent)
            lines.append(f"    {safe_child} --|> {safe_parent}")
    return lines


def _package_from_file_path(file_path: str) -> str:
    """Extract the package name from a file path.

    For 'src/local_deepwiki/core/indexer.py' returns 'core'.
    For 'src/local_deepwiki/models.py' returns 'top-level'.
    For 'tests/test_parser.py' returns 'tests'.

    Args:
        file_path: Source file path.

    Returns:
        Package name string.
    """
    parts = Path(file_path).parts
    if "src" in parts:
        idx = parts.index("src")
        # Skip src/ and the package dir (e.g. local_deepwiki/)
        remaining = parts[idx + 2 :]
        if len(remaining) > 1:
            return remaining[0]
        return "top-level"
    if "tests" in parts:
        return "tests"
    return "top-level"


def generate_class_diagram(
    chunks: list,
    *,
    show_attributes: bool = True,
    show_types: bool = True,
    max_methods: int = 15,
    max_classes_per_diagram: int = 30,
) -> str | None:
    """Generate enhanced Mermaid class diagrams from code chunks.

    When more than max_classes_per_diagram classes exist, generates separate
    diagrams per package to keep each diagram renderable.

    Features:
    - Shows class attributes/properties (not just methods)
    - Shows type annotations for parameters and return types
    - Distinguishes abstract classes, dataclasses, protocols
    - Shows inheritance relationships

    Args:
        chunks: List of CodeChunk or SearchResult objects.
        show_attributes: Whether to show class attributes.
        show_types: Whether to show type annotations.
        max_methods: Maximum methods to show per class.
        max_classes_per_diagram: Split into per-package diagrams above this threshold.

    Returns:
        Mermaid class diagram markdown string, or None if no classes found.
    """
    classes: dict[str, ClassInfo] = {}
    methods_by_class: dict[str, list[tuple[str, str | None]]] = {}
    class_to_package: dict[str, str] = {}

    # Collect class and method info from chunks
    for chunk in chunks:
        chunk = _unwrap_chunk(chunk)
        if chunk.chunk_type == ChunkType.CLASS:
            class_name = chunk.name or "Unknown"
            if class_name not in classes:
                class_to_package[class_name] = _package_from_file_path(chunk.file_path)
            _collect_class_from_chunk(chunk, classes, methods_by_class, show_attributes)
        elif chunk.chunk_type == ChunkType.METHOD:
            _collect_method_from_chunk(chunk, methods_by_class, show_types)

    # Extract methods from class content for classes without METHOD chunks
    _extract_methods_from_class_content(chunks, classes, methods_by_class, show_types)

    # Assign methods to classes
    for class_name, method_list in methods_by_class.items():
        if class_name in classes:
            classes[class_name].methods = [m[0] for m in method_list[:max_methods]]

    # Filter to classes with content
    classes_with_content = {
        k: v for k, v in classes.items() if v.methods or v.attributes
    }
    if not classes_with_content:
        return None

    # If small enough, build a single diagram
    if len(classes_with_content) <= max_classes_per_diagram:
        lines = ["```mermaid", "classDiagram"]
        for class_name, class_info in sorted(classes_with_content.items()):
            lines.extend(
                _build_class_lines(
                    class_name, class_info, methods_by_class, max_methods, show_types
                )
            )
        lines.extend(_build_inheritance_lines(classes_with_content))
        lines.append("```")
        return "\n".join(lines)

    # Split into per-package diagrams
    packages: dict[str, dict[str, ClassInfo]] = {}
    for class_name, class_info in classes_with_content.items():
        pkg = class_to_package.get(class_name, "top-level")
        if pkg not in packages:
            packages[pkg] = {}
        packages[pkg][class_name] = class_info

    sections: list[str] = []
    for pkg_name in sorted(packages):
        pkg_classes = packages[pkg_name]
        lines = [f"### {pkg_name}", "", "```mermaid", "classDiagram"]
        for class_name, class_info in sorted(pkg_classes.items()):
            lines.extend(
                _build_class_lines(
                    class_name, class_info, methods_by_class, max_methods, show_types
                )
            )
        lines.extend(_build_inheritance_lines(pkg_classes))
        lines.append("```")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def _extract_class_attributes(content: str, language: str = "python") -> list[str]:
    """Extract class attributes from content.

    Args:
        content: Class source code.
        language: Programming language.

    Returns:
        List of attribute strings like "+name: str" or "-_count: int".
    """
    attributes = []

    if language in ("python", "py"):
        # Match class-level type annotations: name: Type or self.name: Type
        # Also match __init__ assignments
        attr_pattern = re.compile(
            r"^\s{4}(\w+)\s*:\s*([^=\n]+?)(?:\s*=|$)", re.MULTILINE
        )
        init_pattern = re.compile(r"self\.(\w+)\s*(?::\s*([^\s=]+))?\s*=")

        for match in attr_pattern.finditer(content):
            name, type_hint = match.groups()
            if name not in ("self", "cls") and not name.startswith("__"):
                prefix = "-" if name.startswith("_") else "+"
                type_str = type_hint.strip() if type_hint else ""
                if type_str:
                    attributes.append(f"{prefix}{name}: {type_str}")
                else:
                    attributes.append(f"{prefix}{name}")

        for match in init_pattern.finditer(content):
            name, type_hint = match.groups()
            if name not in [a.split(":")[0].strip("+-") for a in attributes]:
                if not name.startswith("__"):
                    prefix = "-" if name.startswith("_") else "+"
                    if type_hint:
                        attributes.append(f"{prefix}{name}: {type_hint}")
                    else:
                        attributes.append(f"{prefix}{name}")

    return attributes[:10]  # Limit to 10 attributes


def _extract_method_signature(content: str) -> str | None:
    """Extract method signature with types from content.

    Args:
        content: Method source code.

    Returns:
        Signature string like "(x: int, y: str) -> bool" or None.
    """
    # Match def method(params) -> return_type:
    sig_pattern = re.compile(r"def\s+\w+\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?:")
    match = sig_pattern.search(content)
    if not match:
        return None

    params_str = match.group(1)
    return_type = match.group(2)

    # Simplify params (remove defaults, keep just name: type)
    params = []
    for param in params_str.split(","):
        param = param.strip()
        if not param or param == "self" or param == "cls":
            continue
        # Extract name and type
        if ":" in param:
            name_type = param.split("=")[0].strip()  # Remove default
            params.append(name_type)
        else:
            name = param.split("=")[0].strip()
            if name:
                params.append(name)

    sig = f"({', '.join(params[:4])})"  # Limit to 4 params for readability
    if len(params) > 4:
        sig = f"({', '.join(params[:3])}, ...)"

    if return_type:
        sig += f" {return_type.strip()}"

    return sig
