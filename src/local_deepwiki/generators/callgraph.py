"""Call graph extraction and diagram generation."""

from pathlib import Path

from tree_sitter import Node

from local_deepwiki.core.parser import (
    CodeParser,
    find_nodes_by_type,
    get_node_text,
    get_node_name,
)
from local_deepwiki.core.chunker import (
    FUNCTION_NODE_TYPES,
    CLASS_NODE_TYPES,
)
from local_deepwiki.models import Language


# Node types that represent function calls per language
CALL_NODE_TYPES: dict[Language, set[str]] = {
    Language.PYTHON: {"call"},
    Language.JAVASCRIPT: {"call_expression"},
    Language.TYPESCRIPT: {"call_expression"},
    Language.GO: {"call_expression"},
    Language.RUST: {"call_expression"},
    Language.JAVA: {"method_invocation"},
    Language.C: {"call_expression"},
    Language.CPP: {"call_expression"},
    Language.SWIFT: {"call_expression"},
}


def extract_call_name(call_node: Node, source: bytes, language: Language) -> str | None:
    """Extract the function/method name from a call expression.

    Args:
        call_node: The call expression AST node.
        source: Source bytes.
        language: Programming language.

    Returns:
        The called function name or None if can't determine.
    """
    if language == Language.PYTHON:
        # Python: func() or obj.method() or module.func()
        func = call_node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                return get_node_text(func, source)
            elif func.type == "attribute":
                # obj.method() - get the method name
                attr = func.child_by_field_name("attribute")
                if attr:
                    return get_node_text(attr, source)

    elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        # JS/TS: func() or obj.method()
        func = call_node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                return get_node_text(func, source)
            elif func.type == "member_expression":
                prop = func.child_by_field_name("property")
                if prop:
                    return get_node_text(prop, source)

    elif language == Language.GO:
        # Go: func() or pkg.Func() or obj.Method()
        func = call_node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                return get_node_text(func, source)
            elif func.type == "selector_expression":
                field = func.child_by_field_name("field")
                if field:
                    return get_node_text(field, source)

    elif language == Language.RUST:
        # Rust: func() or Type::method() or self.method()
        func = call_node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                return get_node_text(func, source)
            elif func.type == "scoped_identifier":
                name = func.child_by_field_name("name")
                if name:
                    return get_node_text(name, source)
            elif func.type == "field_expression":
                field = func.child_by_field_name("field")
                if field:
                    return get_node_text(field, source)

    elif language == Language.JAVA:
        # Java: method() or obj.method()
        name = call_node.child_by_field_name("name")
        if name:
            return get_node_text(name, source)

    elif language in (Language.C, Language.CPP):
        # C/C++: func() or obj.method() or obj->method()
        func = call_node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                return get_node_text(func, source)
            elif func.type == "field_expression":
                field = func.child_by_field_name("field")
                if field:
                    return get_node_text(field, source)

    elif language == Language.SWIFT:
        # Swift: func() or obj.method()
        func = call_node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                return get_node_text(func, source)
            elif func.type in ("navigation_expression", "member_access"):
                for child in func.children:
                    if child.type == "navigation_suffix":
                        for c in child.children:
                            if c.type == "simple_identifier":
                                return get_node_text(c, source)

    return None


def extract_calls_from_function(
    func_node: Node,
    source: bytes,
    language: Language,
) -> list[str]:
    """Extract all function calls from a function body.

    Args:
        func_node: The function AST node.
        source: Source bytes.
        language: Programming language.

    Returns:
        List of called function names (deduplicated).
    """
    call_types = CALL_NODE_TYPES.get(language, set())
    if not call_types:
        return []

    call_nodes = find_nodes_by_type(func_node, call_types)
    calls = []

    for call_node in call_nodes:
        name = extract_call_name(call_node, source, language)
        if name and name not in calls:
            # Filter out common built-ins and noise
            if not _is_builtin_or_noise(name, language):
                calls.append(name)

    return calls


def _is_builtin_or_noise(name: str, language: Language) -> bool:
    """Check if a function name is a built-in or common noise.

    Args:
        name: Function name.
        language: Programming language.

    Returns:
        True if should be filtered out.
    """
    # Common built-ins/noise to filter across languages
    common_noise = {
        "print", "println", "printf", "len", "str", "int", "float", "bool",
        "list", "dict", "set", "tuple", "range", "enumerate", "zip", "map",
        "filter", "sorted", "reversed", "min", "max", "sum", "any", "all",
        "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
        "type", "id", "repr", "hash", "format", "open", "close",
        "append", "extend", "insert", "remove", "pop", "clear",
        "get", "keys", "values", "items", "update",
        "join", "split", "strip", "replace", "startswith", "endswith",
        "lower", "upper", "find", "index", "count",
        "log", "debug", "info", "warn", "warning", "error",
        "console", "assert", "require", "include",
    }

    if name.lower() in common_noise:
        return True

    # Language-specific noise
    if language == Language.PYTHON:
        python_noise = {"super", "next", "iter", "abs", "round", "ord", "chr", "hex", "bin", "oct"}
        if name in python_noise:
            return True

    elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        js_noise = {"setTimeout", "setInterval", "clearTimeout", "clearInterval", "fetch", "Promise"}
        if name in js_noise:
            return True

    return False


class CallGraphExtractor:
    """Extracts call graphs from source files."""

    def __init__(self):
        """Initialize the extractor."""
        self.parser = CodeParser()

    def extract_from_file(
        self,
        file_path: Path,
        repo_root: Path,
    ) -> dict[str, list[str]]:
        """Extract call graph from a source file.

        Args:
            file_path: Path to the source file.
            repo_root: Repository root path.

        Returns:
            Dictionary mapping function name to list of called functions.
        """
        result = self.parser.parse_file(file_path)
        if result is None:
            return {}

        root, language, source = result
        call_graph: dict[str, list[str]] = {}

        # Get function and class node types
        function_types = FUNCTION_NODE_TYPES.get(language, set())
        class_types = CLASS_NODE_TYPES.get(language, set())

        # Extract from top-level functions
        for func_node in find_nodes_by_type(root, function_types):
            # Skip if inside a class
            if self._is_inside_class(func_node, class_types):
                continue

            func_name = get_node_name(func_node, source, language)
            if func_name:
                calls = extract_calls_from_function(func_node, source, language)
                if calls:
                    call_graph[func_name] = calls

        # Extract from class methods
        for class_node in find_nodes_by_type(root, class_types):
            class_name = get_node_name(class_node, source, language)
            if not class_name:
                continue

            for method_node in find_nodes_by_type(class_node, function_types):
                method_name = get_node_name(method_node, source, language)
                if method_name:
                    full_name = f"{class_name}.{method_name}"
                    calls = extract_calls_from_function(method_node, source, language)
                    if calls:
                        call_graph[full_name] = calls

        return call_graph

    def _is_inside_class(self, node: Node, class_types: set[str]) -> bool:
        """Check if a node is inside a class definition."""
        parent = node.parent
        while parent:
            if parent.type in class_types:
                return True
            parent = parent.parent
        return False


def generate_call_graph_diagram(
    call_graph: dict[str, list[str]],
    title: str | None = None,
    max_nodes: int = 30,
) -> str | None:
    """Generate a Mermaid flowchart for a call graph.

    Args:
        call_graph: Mapping of caller to list of callees.
        title: Optional diagram title.
        max_nodes: Maximum number of nodes to include.

    Returns:
        Mermaid diagram string or None if empty.
    """
    if not call_graph:
        return None

    # Collect all unique nodes
    all_nodes: set[str] = set()
    for caller, callees in call_graph.items():
        all_nodes.add(caller)
        all_nodes.update(callees)

    # If too many nodes, filter to most connected
    if len(all_nodes) > max_nodes:
        # Count connections per node
        connection_count: dict[str, int] = {}
        for caller, callees in call_graph.items():
            connection_count[caller] = connection_count.get(caller, 0) + len(callees)
            for callee in callees:
                connection_count[callee] = connection_count.get(callee, 0) + 1

        # Keep top nodes by connection count
        sorted_nodes = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)
        all_nodes = {node for node, _ in sorted_nodes[:max_nodes]}

    # Build diagram
    lines = ["flowchart TD"]

    if title:
        # Mermaid doesn't have native title, use a styled node
        pass

    # Generate safe node IDs
    node_ids: dict[str, str] = {}
    for i, node in enumerate(sorted(all_nodes)):
        safe_id = f"N{i}"
        node_ids[node] = safe_id
        # Use display name (truncate if too long)
        display_name = node if len(node) <= 30 else node[:27] + "..."
        lines.append(f"    {safe_id}[{display_name}]")

    # Add edges
    for caller, callees in call_graph.items():
        if caller not in node_ids:
            continue
        caller_id = node_ids[caller]
        for callee in callees:
            if callee in node_ids:
                callee_id = node_ids[callee]
                lines.append(f"    {caller_id} --> {callee_id}")

    # Style function nodes differently from method nodes
    func_nodes = []
    method_nodes = []
    for node, node_id in node_ids.items():
        if "." in node:
            method_nodes.append(node_id)
        else:
            func_nodes.append(node_id)

    if func_nodes:
        lines.append(f"    classDef func fill:#e1f5fe")
        lines.append(f"    class {','.join(func_nodes)} func")

    if method_nodes:
        lines.append(f"    classDef method fill:#fff3e0")
        lines.append(f"    class {','.join(method_nodes)} method")

    return "\n".join(lines)


def get_file_call_graph(file_path: Path, repo_root: Path) -> str | None:
    """Get a call graph diagram for a single file.

    Args:
        file_path: Path to the source file.
        repo_root: Repository root path.

    Returns:
        Mermaid diagram string or None if no calls found.
    """
    extractor = CallGraphExtractor()
    call_graph = extractor.extract_from_file(file_path, repo_root)
    return generate_call_graph_diagram(call_graph)
