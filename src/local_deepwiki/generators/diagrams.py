"""Mermaid diagram generation for code visualization."""

from local_deepwiki.models import CodeChunk, IndexStatus


def generate_architecture_diagram(chunks: list[CodeChunk]) -> str:
    """Generate a Mermaid architecture diagram from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid diagram string.
    """
    # Group chunks by file/module
    modules: dict[str, list[CodeChunk]] = {}
    for chunk in chunks:
        module = chunk.file_path.split("/")[0] if "/" in chunk.file_path else "root"
        modules.setdefault(module, []).append(chunk)

    lines = ["graph TD"]

    # Add module nodes
    for module_name, module_chunks in modules.items():
        safe_name = module_name.replace("-", "_").replace(".", "_")
        class_count = sum(1 for c in module_chunks if c.chunk_type.value == "class")
        func_count = sum(1 for c in module_chunks if c.chunk_type.value == "function")

        label = f"{module_name}"
        if class_count or func_count:
            label += f"<br/>{class_count} classes, {func_count} functions"

        lines.append(f"    {safe_name}[{label}]")

    return "\n".join(lines)


def generate_class_diagram(chunks: list[CodeChunk]) -> str:
    """Generate a Mermaid class diagram from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid class diagram string.
    """
    lines = ["classDiagram"]

    # Find class and method chunks
    classes = [c for c in chunks if c.chunk_type.value == "class"]
    methods = [c for c in chunks if c.chunk_type.value == "method"]

    for class_chunk in classes:
        safe_name = class_chunk.name.replace("-", "_") if class_chunk.name else "Unknown"
        lines.append(f"    class {safe_name} {{")

        # Find methods for this class
        class_methods = [m for m in methods if m.parent_name == class_chunk.name]
        for method in class_methods[:10]:  # Limit to 10 methods
            method_name = method.name or "unknown"
            lines.append(f"        +{method_name}()")

        lines.append("    }")

    return "\n".join(lines)


def generate_dependency_diagram(index_status: IndexStatus) -> str:
    """Generate a Mermaid dependency diagram from index status.

    Args:
        index_status: Index status with file information.

    Returns:
        Mermaid diagram string.
    """
    # Group by language
    lines = ["pie title Languages in Repository"]

    for lang, count in index_status.languages.items():
        lines.append(f'    "{lang}" : {count}')

    return "\n".join(lines)


def generate_file_tree_diagram(index_status: IndexStatus, max_depth: int = 3) -> str:
    """Generate a text-based file tree.

    Args:
        index_status: Index status with file information.
        max_depth: Maximum directory depth to show.

    Returns:
        File tree string.
    """
    lines = ["```"]
    lines.append(f"{index_status.repo_path.split('/')[-1]}/")

    # Build tree structure
    tree: dict = {}
    for file_info in index_status.files:
        parts = file_info.path.split("/")
        current = tree
        for part in parts[:-1][:max_depth]:
            current = current.setdefault(part, {})
        if len(parts) <= max_depth:
            current[parts[-1]] = None

    def render_tree(node: dict, prefix: str = "") -> list[str]:
        result = []
        items = sorted(node.items())
        for i, (name, children) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            result.append(f"{prefix}{connector}{name}")
            if children is not None:
                extension = "    " if is_last else "│   "
                result.extend(render_tree(children, prefix + extension))
        return result

    lines.extend(render_tree(tree))
    lines.append("```")

    return "\n".join(lines)
