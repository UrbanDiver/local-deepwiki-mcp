"""Inheritance tree extraction and visualization."""

from dataclasses import dataclass, field
from pathlib import Path

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.diagrams import sanitize_mermaid_name
from local_deepwiki.models import ChunkType, IndexStatus


@dataclass
class ClassNode:
    """A class in the inheritance tree."""

    name: str
    file_path: str
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    is_abstract: bool = False
    docstring: str | None = None


async def collect_class_hierarchy(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> dict[str, ClassNode]:
    """Collect all classes and their inheritance relationships.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        Dictionary mapping class name to ClassNode.
    """
    classes: dict[str, ClassNode] = {}

    # Iterate through all indexed files
    for file_info in index_status.files:
        chunks = await vector_store.get_chunks_by_file(file_info.path)

        for chunk in chunks:
            if chunk.chunk_type != ChunkType.CLASS:
                continue

            class_name = chunk.name
            if not class_name:
                continue

            # Extract parent classes from metadata
            parent_classes = chunk.metadata.get("parent_classes", [])

            # Check if abstract
            is_abstract = (
                "ABC" in str(parent_classes)
                or "@abstractmethod" in chunk.content
                or "abstract" in chunk.content.lower()[:100]
            )

            # Create or update class node
            if class_name not in classes:
                classes[class_name] = ClassNode(
                    name=class_name,
                    file_path=file_info.path,
                    parents=parent_classes,
                    is_abstract=is_abstract,
                    docstring=chunk.docstring,
                )
            else:
                # Merge if same class appears in multiple files (shouldn't happen often)
                existing = classes[class_name]
                existing.parents = list(set(existing.parents + parent_classes))

    # Build children relationships (reverse of parents)
    for class_name, class_node in classes.items():
        for parent in class_node.parents:
            if parent in classes:
                if class_name not in classes[parent].children:
                    classes[parent].children.append(class_name)

    return classes


def find_root_classes(classes: dict[str, ClassNode]) -> list[str]:
    """Find classes that have no parents (root of inheritance trees).

    Args:
        classes: Dictionary of class nodes.

    Returns:
        List of root class names, sorted alphabetically.
    """
    roots = []
    for class_name, class_node in classes.items():
        # A class is a root if it has no parents in our codebase
        has_internal_parent = any(p in classes for p in class_node.parents)
        if not has_internal_parent and class_node.children:
            roots.append(class_name)
    return sorted(roots)


def generate_inheritance_diagram(
    classes: dict[str, ClassNode],
    max_classes: int = 50,
) -> str | None:
    """Generate a Mermaid class diagram showing inheritance relationships.

    Only shows classes with internal inheritance relationships (excludes
    classes that only inherit from external bases like BaseModel, Enum, ABC).

    Args:
        classes: Dictionary of class nodes.
        max_classes: Maximum number of classes to include.

    Returns:
        Mermaid diagram string or None if no inheritance found.
    """
    # Filter to classes that have INTERNAL inheritance relationships
    # (parent or child is also in our codebase)
    classes_with_internal_inheritance = {}
    for name, node in classes.items():
        has_internal_parent = any(p in classes for p in node.parents)
        has_children = bool(node.children)
        if has_internal_parent or has_children:
            classes_with_internal_inheritance[name] = node

    if not classes_with_internal_inheritance:
        return None

    # If too many, prioritize classes with most internal relationships
    if len(classes_with_internal_inheritance) > max_classes:
        scored = [
            (name, len([p for p in node.parents if p in classes]) + len(node.children))
            for name, node in classes_with_internal_inheritance.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        keep_names = {name for name, _ in scored[:max_classes]}
        classes_with_internal_inheritance = {
            name: node
            for name, node in classes_with_internal_inheritance.items()
            if name in keep_names
        }

    lines = ["```mermaid", "classDiagram"]

    # Add class definitions
    for class_name in sorted(classes_with_internal_inheritance.keys()):
        node = classes_with_internal_inheritance[class_name]
        safe_name = sanitize_mermaid_name(class_name)

        if node.is_abstract:
            lines.append(f"    class {safe_name} {{")
            lines.append("        <<abstract>>")
            lines.append("    }")
        else:
            lines.append(f"    class {safe_name}")

    # Add inheritance relationships (only internal)
    for class_name, node in sorted(classes_with_internal_inheritance.items()):
        safe_child = sanitize_mermaid_name(class_name)
        for parent in node.parents:
            # Only add if parent is in our codebase
            if parent in classes_with_internal_inheritance:
                safe_parent = sanitize_mermaid_name(parent)
                lines.append(f"    {safe_child} --|> {safe_parent}")

    lines.append("```")

    # Check if we actually have any relationships
    has_relationships = any(
        "-->" in line or "--|>" in line for line in lines
    )
    if not has_relationships:
        return None

    return "\n".join(lines)


def generate_inheritance_tree_text(
    classes: dict[str, ClassNode],
    root_class: str,
    indent: int = 0,
    visited: set[str] | None = None,
) -> list[str]:
    """Generate a text-based inheritance tree starting from a root class.

    Args:
        classes: Dictionary of class nodes.
        root_class: The root class to start from.
        indent: Current indentation level.
        visited: Set of visited classes to avoid cycles.

    Returns:
        List of formatted tree lines.
    """
    if visited is None:
        visited = set()

    if root_class in visited:
        return []

    visited.add(root_class)
    lines = []

    node = classes.get(root_class)
    if not node:
        return []

    prefix = "  " * indent
    marker = "- " if indent == 0 else "└─ " if indent > 0 else ""

    # Format: ClassName (file.py) - brief description
    file_name = Path(node.file_path).name
    desc = ""
    if node.docstring:
        first_line = node.docstring.split("\n")[0].strip()
        if len(first_line) > 60:
            first_line = first_line[:57] + "..."
        desc = f" - {first_line}"

    abstract_marker = " (abstract)" if node.is_abstract else ""
    lines.append(f"{prefix}{marker}**{root_class}**{abstract_marker} `{file_name}`{desc}")

    # Recursively add children
    for child in sorted(node.children):
        child_lines = generate_inheritance_tree_text(
            classes, child, indent + 1, visited
        )
        lines.extend(child_lines)

    return lines


async def generate_inheritance_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> str | None:
    """Generate the inheritance documentation page content.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        Markdown content for the inheritance page, or None if no inheritance found.
    """
    classes = await collect_class_hierarchy(index_status, vector_store)

    if not classes:
        return None

    # Filter to classes with INTERNAL inheritance relationships
    classes_with_inheritance = {}
    for name, node in classes.items():
        has_internal_parent = any(p in classes for p in node.parents)
        has_children = bool(node.children)
        if has_internal_parent or has_children:
            classes_with_inheritance[name] = node

    if not classes_with_inheritance:
        return None

    lines = [
        "# Class Inheritance",
        "",
        "This page shows the class inheritance hierarchies in the codebase.",
        "",
    ]

    # Generate diagram
    diagram = generate_inheritance_diagram(classes)
    if diagram:
        lines.append("## Inheritance Diagram")
        lines.append("")
        lines.append(diagram)
        lines.append("")

    # Find root classes and generate trees
    roots = find_root_classes(classes)

    if roots:
        lines.append("## Inheritance Trees")
        lines.append("")

        for root in roots:
            tree_lines = generate_inheritance_tree_text(classes, root)
            if tree_lines:
                lines.extend(tree_lines)
                lines.append("")

    # List all classes with their parents
    lines.append("## All Classes")
    lines.append("")
    lines.append("| Class | Inherits From | File |")
    lines.append("|-------|---------------|------|")

    for class_name in sorted(classes_with_inheritance.keys()):
        node = classes_with_inheritance[class_name]
        parents_str = ", ".join(f"`{p}`" for p in node.parents) if node.parents else "-"
        file_link = f"[{Path(node.file_path).name}](files/{node.file_path.replace('.py', '.md')})"
        lines.append(f"| `{class_name}` | {parents_str} | {file_link} |")

    lines.append("")

    return "\n".join(lines)
