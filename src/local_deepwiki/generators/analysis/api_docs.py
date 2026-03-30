"""API documentation generation with type signatures and docstrings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TypedDict

from tree_sitter import Node

from local_deepwiki.core.chunker import CLASS_NODE_TYPES, FUNCTION_NODE_TYPES
from local_deepwiki.core.parser import (
    CodeParser,
    find_nodes_by_type,
    get_node_name,
    get_node_text,
)
from local_deepwiki.models import Language


class ArgInfo(TypedDict):
    """Type for argument info in parsed docstrings."""

    type: str | None
    description: str


class ParsedDocstring(TypedDict):
    """Type for parsed docstring result."""

    description: str
    args: dict[str, ArgInfo]
    returns: str | None
    raises: list[str]


@dataclass(slots=True)
class Parameter:
    """Represents a function parameter."""

    name: str
    type_hint: str | None = None
    default_value: str | None = None
    description: str | None = None


@dataclass(slots=True)
class FunctionSignature:
    """Represents a function/method signature."""

    name: str
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    docstring: str | None = None
    description: str | None = None
    is_method: bool = False
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ClassSignature:
    """Represents a class signature."""

    name: str
    bases: list[str] = field(default_factory=list)
    docstring: str | None = None
    description: str | None = None
    methods: list[FunctionSignature] = field(default_factory=list)
    class_variables: list[tuple[str, str | None, str | None]] = field(
        default_factory=list
    )


_SELF_CLS = frozenset({"self", "cls"})


def _parse_identifier_param(child: Node, source: bytes) -> Parameter | None:
    """Handle a plain ``identifier`` parameter node."""
    name = get_node_text(child, source)
    if name not in _SELF_CLS:
        return Parameter(name=name)
    return None


def _parse_typed_param(child: Node, source: bytes) -> Parameter | None:
    """Handle a ``typed_parameter`` node (name: type)."""
    name_node = None
    type_node = None
    for c in child.children:
        if c.type == "identifier":
            name_node = c
        elif c.type == "type":
            type_node = c
    if name_node:
        name = get_node_text(name_node, source)
        if name not in _SELF_CLS:
            type_hint = get_node_text(type_node, source) if type_node else None
            return Parameter(name=name, type_hint=type_hint)
    return None


def _parse_default_param(child: Node, source: bytes) -> Parameter | None:
    """Handle a ``default_parameter`` node (name=default)."""
    name_node = child.child_by_field_name("name")
    value_node = child.child_by_field_name("value")
    if name_node:
        name = get_node_text(name_node, source)
        if name not in _SELF_CLS:
            default = get_node_text(value_node, source) if value_node else None
            return Parameter(name=name, default_value=default)
    return None


def _parse_typed_default_param(child: Node, source: bytes) -> Parameter | None:
    """Handle a ``typed_default_parameter`` node (name: type = default)."""
    name_node = child.child_by_field_name("name")
    type_node = child.child_by_field_name("type")
    value_node = child.child_by_field_name("value")
    if name_node:
        name = get_node_text(name_node, source)
        if name not in _SELF_CLS:
            type_hint = get_node_text(type_node, source) if type_node else None
            default = get_node_text(value_node, source) if value_node else None
            return Parameter(name=name, type_hint=type_hint, default_value=default)
    return None


def _parse_splat_param(child: Node, source: bytes) -> Parameter | None:
    """Handle ``list_splat_pattern`` (*args) and ``dictionary_splat_pattern`` (**kwargs)."""
    prefix = "*" if child.type == "list_splat_pattern" else "**"
    for c in child.children:
        if c.type == "identifier":
            return Parameter(name=f"{prefix}{get_node_text(c, source)}")
    return None


_PARAM_NODE_HANDLERS: dict[str, Callable[[Node, bytes], Parameter | None]] = {
    "identifier": _parse_identifier_param,
    "typed_parameter": _parse_typed_param,
    "default_parameter": _parse_default_param,
    "typed_default_parameter": _parse_typed_default_param,
    "list_splat_pattern": _parse_splat_param,
    "dictionary_splat_pattern": _parse_splat_param,
}


def _parse_param_node(child: Node, source: bytes) -> Parameter | None:
    """Extract a single Parameter from an AST parameter node.

    Args:
        child: A child node of the parameters list.
        source: Source code bytes.

    Returns:
        A Parameter or None if the node should be skipped.
    """
    handler = _PARAM_NODE_HANDLERS.get(child.type)
    if handler is not None:
        return handler(child, source)
    return None


def extract_python_parameters(func_node: Node, source: bytes) -> list[Parameter]:
    """Extract parameters from a Python function definition.

    Args:
        func_node: The function_definition AST node.
        source: Source code bytes.

    Returns:
        List of Parameter objects.
    """
    parameters: list[Parameter] = []
    params_node = func_node.child_by_field_name("parameters")
    if not params_node:
        return parameters

    for child in params_node.children:
        param = _parse_param_node(child, source)
        if param is not None:
            parameters.append(param)

    return parameters


def extract_python_return_type(func_node: Node, source: bytes) -> str | None:
    """Extract return type annotation from a Python function.

    Args:
        func_node: The function_definition AST node.
        source: Source code bytes.

    Returns:
        Return type string or None.
    """
    return_type_node = func_node.child_by_field_name("return_type")
    if return_type_node:
        return get_node_text(return_type_node, source)
    return None


def extract_python_decorators(func_node: Node, source: bytes) -> list[str]:
    """Extract decorators from a Python function.

    Args:
        func_node: The function_definition AST node.
        source: Source code bytes.

    Returns:
        List of decorator strings.
    """
    decorators: list[str] = []
    # Look at siblings before the function
    if func_node.parent:
        prev_sibling = func_node.prev_sibling
        while prev_sibling:
            if prev_sibling.type == "decorator":
                dec_text = get_node_text(prev_sibling, source)
                decorators.insert(0, dec_text)
            elif prev_sibling.type not in ("comment", "decorator"):
                break
            prev_sibling = prev_sibling.prev_sibling
    return decorators


def extract_python_docstring(node: Node, source: bytes) -> str | None:
    """Extract docstring from a Python function or class.

    Args:
        node: The function_definition or class_definition AST node.
        source: Source code bytes.

    Returns:
        Docstring content or None.
    """
    # Find the body/block node
    body_node = node.child_by_field_name("body")
    if not body_node:
        return None

    # First statement in body might be a docstring
    for child in body_node.children:
        if child.type == "expression_statement":
            for c in child.children:
                if c.type == "string":
                    docstring = get_node_text(c, source)
                    # Remove quotes
                    if docstring.startswith('"""') or docstring.startswith("'''"):
                        docstring = docstring[3:-3]
                    elif docstring.startswith('"') or docstring.startswith("'"):
                        docstring = docstring[1:-1]
                    return docstring.strip()
        elif child.type not in ("comment", "pass_statement"):
            # First non-comment statement is not a docstring
            break

    return None


def _parse_google_docstring_section(
    stripped: str,
    current_section: str,
    current_param: str | None,
    args_dict: dict[str, ArgInfo],
    returns_str: str | None,
    description_lines: list[str],
) -> tuple[str | None, str | None]:
    """Process one line for the Google docstring parser.

    Args:
        stripped: The stripped line content.
        current_section: Current section name.
        current_param: Name of the current parameter being parsed, or None.
        args_dict: Mutable args dict to update in-place.
        returns_str: Current returns string (may be None).
        description_lines: Mutable description lines list to update.

    Returns:
        Tuple of (updated current_param, updated returns_str).
    """
    if current_section == "description":
        description_lines.append(stripped)
    elif current_section == "args":
        param_match = re.match(r"(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.+)?", stripped)
        if param_match:
            param_name = param_match.group(1)
            param_type = param_match.group(2)
            param_desc = param_match.group(3) or ""
            args_dict[param_name] = ArgInfo(
                type=param_type,
                description=param_desc.strip(),
            )
            current_param = param_name
        elif current_param and stripped:
            args_dict[current_param]["description"] += " " + stripped
    elif current_section == "returns":
        if returns_str is None:
            returns_str = stripped
        elif stripped:
            returns_str += " " + stripped
    return current_param, returns_str


def parse_google_docstring(docstring: str) -> ParsedDocstring:
    """Parse a Google-style docstring.

    Args:
        docstring: The docstring content.

    Returns:
        Dictionary with 'description', 'args', 'returns', 'raises' keys.
    """
    args_dict: dict[str, ArgInfo] = {}
    returns_str: str | None = None
    raises_list: list[str] = []

    if not docstring:
        return {
            "description": "",
            "args": args_dict,
            "returns": None,
            "raises": raises_list,
        }

    lines = docstring.split("\n")
    current_section = "description"
    current_param: str | None = None
    description_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Check for section headers
        if stripped in ("Args:", "Arguments:", "Parameters:"):
            current_section = "args"
            current_param = None
            continue
        elif stripped in ("Returns:", "Return:"):
            current_section = "returns"
            current_param = None
            continue
        elif stripped in ("Raises:", "Raise:"):
            current_section = "raises"
            current_param = None
            continue
        elif stripped in ("Example:", "Examples:", "Note:", "Notes:", "Yields:"):
            current_section = "other"
            current_param = None
            continue

        current_param, returns_str = _parse_google_docstring_section(
            stripped,
            current_section,
            current_param,
            args_dict,
            returns_str,
            description_lines,
        )

    description = " ".join(description_lines).strip()
    # Take just first paragraph for description
    if "\n\n" in description:
        description = description.split("\n\n")[0]

    return {
        "description": description,
        "args": args_dict,
        "returns": returns_str,
        "raises": raises_list,
    }


@dataclass(slots=True)
class NumpyParserState:
    """Mutable state for the NumPy docstring line-by-line parser.

    Groups the accumulators that :func:`_parse_numpy_docstring_section`
    reads and updates on each line.
    """

    current_section: str
    current_param: str | None
    args_dict: dict[str, ArgInfo]
    returns_str: str | None
    description_lines: list[str]


def _parse_numpy_docstring_section(
    line: str,
    stripped: str,
    state: NumpyParserState,
) -> None:
    """Process one line for the NumPy docstring parser.

    Args:
        line: The raw (non-stripped) line.
        stripped: The stripped line content.
        state: Mutable parser state accumulating args, returns, and description.
    """
    if state.current_section == "description":
        state.description_lines.append(stripped)
    elif state.current_section == "args":
        param_match = re.match(r"(\w+)\s*:\s*(.+)?", stripped)
        if param_match and not line.startswith("    "):
            param_name = param_match.group(1)
            param_type = param_match.group(2)
            state.args_dict[param_name] = ArgInfo(
                type=param_type.strip() if param_type else None,
                description="",
            )
            state.current_param = param_name
        elif state.current_param and stripped:
            state.args_dict[state.current_param]["description"] += " " + stripped
    elif state.current_section == "returns":
        if state.returns_str is None:
            state.returns_str = stripped
        elif stripped:
            state.returns_str += " " + stripped


def parse_numpy_docstring(docstring: str) -> ParsedDocstring:
    """Parse a NumPy-style docstring.

    Args:
        docstring: The docstring content.

    Returns:
        Dictionary with 'description', 'args', 'returns', 'raises' keys.
    """
    args_dict: dict[str, ArgInfo] = {}
    returns_str: str | None = None
    raises_list: list[str] = []

    if not docstring:
        return {
            "description": "",
            "args": args_dict,
            "returns": None,
            "raises": raises_list,
        }

    lines = docstring.split("\n")
    state = NumpyParserState(
        current_section="description",
        current_param=None,
        args_dict=args_dict,
        returns_str=returns_str,
        description_lines=[],
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check for section headers (followed by dashes)
        if i + 1 < len(lines) and lines[i + 1].strip().startswith("---"):
            if stripped.lower() in ("parameters", "args", "arguments"):
                state.current_section = "args"
            elif stripped.lower() in ("returns", "return"):
                state.current_section = "returns"
            elif stripped.lower() in ("raises", "raise"):
                state.current_section = "raises"
            else:
                state.current_section = "other"
            i += 2
            continue

        _parse_numpy_docstring_section(line, stripped, state)

        i += 1

    returns_str = state.returns_str
    description = " ".join(state.description_lines).strip()
    if "\n\n" in description:
        description = description.split("\n\n")[0]

    return {
        "description": description,
        "args": args_dict,
        "returns": returns_str,
        "raises": raises_list,
    }


def parse_docstring(docstring: str) -> ParsedDocstring:
    """Parse a docstring, auto-detecting format.

    Args:
        docstring: The docstring content.

    Returns:
        Parsed docstring dictionary.
    """
    if not docstring:
        return {"description": "", "args": {}, "returns": None, "raises": []}

    # Detect format by looking for section markers
    if re.search(r"^(Args|Arguments|Parameters):\s*$", docstring, re.MULTILINE):
        return parse_google_docstring(docstring)
    elif re.search(r"^(Parameters|Args)\s*\n\s*-+", docstring, re.MULTILINE):
        return parse_numpy_docstring(docstring)
    else:
        # Default to Google-style parsing (handles simple docstrings too)
        return parse_google_docstring(docstring)


def extract_function_signature(
    func_node: Node,
    source: bytes,
    language: Language,
    class_name: str | None = None,
) -> FunctionSignature | None:
    """Extract signature from a function node.

    Args:
        func_node: The function AST node.
        source: Source code bytes.
        language: Programming language.
        class_name: Parent class name if this is a method.

    Returns:
        FunctionSignature or None if extraction fails.
    """
    name = get_node_name(func_node, source, language)
    if not name:
        return None

    sig = FunctionSignature(name=name, is_method=class_name is not None)

    if language == Language.PYTHON:
        sig.parameters = extract_python_parameters(func_node, source)
        sig.return_type = extract_python_return_type(func_node, source)
        sig.decorators = extract_python_decorators(func_node, source)
        # Check for async keyword as first child
        sig.is_async = any(c.type == "async" for c in func_node.children)

        docstring = extract_python_docstring(func_node, source)
        if docstring:
            sig.docstring = docstring
            parsed = parse_docstring(docstring)
            sig.description = parsed["description"]

            # Merge docstring param descriptions
            for param in sig.parameters:
                if param.name.lstrip("*") in parsed["args"]:
                    arg_info = parsed["args"][param.name.lstrip("*")]
                    param.description = arg_info.get("description")
                    if not param.type_hint and arg_info.get("type"):
                        param.type_hint = arg_info["type"]

    return sig


def extract_class_signature(
    class_node: Node,
    source: bytes,
    language: Language,
) -> ClassSignature | None:
    """Extract signature from a class node.

    Args:
        class_node: The class AST node.
        source: Source code bytes.
        language: Programming language.

    Returns:
        ClassSignature or None if extraction fails.
    """
    name = get_node_name(class_node, source, language)
    if not name:
        return None

    sig = ClassSignature(name=name)

    if language == Language.PYTHON:
        # Extract base classes
        for child in class_node.children:
            if child.type == "argument_list":
                for c in child.children:
                    if c.type == "identifier":
                        sig.bases.append(get_node_text(c, source))
                    elif c.type == "attribute":
                        sig.bases.append(get_node_text(c, source))

        # Extract docstring
        docstring = extract_python_docstring(class_node, source)
        if docstring:
            sig.docstring = docstring
            parsed = parse_docstring(docstring)
            sig.description = parsed["description"]

        # Extract methods
        function_types = FUNCTION_NODE_TYPES.get(language, set())
        for method_node in find_nodes_by_type(class_node, function_types):
            method_sig = extract_function_signature(method_node, source, language, name)
            if method_sig:
                sig.methods.append(method_sig)

    return sig


class APIDocExtractor:
    """Extracts API documentation from source files."""

    def __init__(self) -> None:
        """Initialize the extractor."""
        self.parser = CodeParser()

    def extract_from_file(
        self, file_path: Path
    ) -> tuple[list[FunctionSignature], list[ClassSignature]]:
        """Extract API documentation from a source file.

        Args:
            file_path: Path to the source file.

        Returns:
            Tuple of (functions, classes) signatures.
        """
        result = self.parser.parse_file(file_path)
        if result is None:
            return [], []

        root, language, source = result
        functions: list[FunctionSignature] = []
        classes: list[ClassSignature] = []

        function_types = FUNCTION_NODE_TYPES.get(language, set())
        class_types = CLASS_NODE_TYPES.get(language, set())

        # Extract top-level functions
        for func_node in find_nodes_by_type(root, function_types):
            # Skip if inside a class
            if self._is_inside_class(func_node, class_types):
                continue

            sig = extract_function_signature(func_node, source, language)
            if sig:
                functions.append(sig)

        # Extract classes
        for class_node in find_nodes_by_type(root, class_types):
            class_sig = extract_class_signature(class_node, source, language)
            if class_sig:
                classes.append(class_sig)

        return functions, classes

    @staticmethod
    def _is_inside_class(node: Node, class_types: set[str]) -> bool:
        """Check if a node is inside a class definition."""
        parent = node.parent
        while parent:
            if parent.type in class_types:
                return True
            parent = parent.parent
        return False


def format_parameter(param: Parameter) -> str:
    """Format a parameter for display.

    Args:
        param: The parameter to format.

    Returns:
        Formatted parameter string.
    """
    parts = [param.name]
    if param.type_hint:
        parts.append(f": {param.type_hint}")
    if param.default_value is not None:
        parts.append(f" = {param.default_value}")
    return "".join(parts)


def format_function_signature_line(sig: FunctionSignature) -> str:
    """Format a function signature as a single line.

    Args:
        sig: The function signature.

    Returns:
        Formatted signature string.
    """
    prefix = "async " if sig.is_async else ""
    params = ", ".join(format_parameter(p) for p in sig.parameters)
    return_part = f" -> {sig.return_type}" if sig.return_type else ""
    return f"{prefix}def {sig.name}({params}){return_part}"


def _append_params_table(lines: list[str], params: list[Parameter]) -> None:
    """Append a markdown parameter table to *lines* for the given *params*."""
    lines.append("\n| Parameter | Type | Default | Description |")
    lines.append("|-----------|------|---------|-------------|")
    for param in params:
        type_str = f"`{param.type_hint}`" if param.type_hint else "-"
        default_str = f"`{param.default_value}`" if param.default_value else "-"
        desc_str = param.description or "-"
        lines.append(f"| `{param.name}` | {type_str} | {default_str} | {desc_str} |")
    lines.append("")


def _format_class_docs(
    cls: ClassSignature,
    lines: list[str],
    include_private: bool,
) -> None:
    """Render one class signature block into *lines*.

    Args:
        cls: The class signature to render.
        lines: Mutable list of markdown lines to append to.
        include_private: Whether to include private methods.
    """
    lines.append(f"### class `{cls.name}`")

    if cls.bases:
        lines.append(f"\n**Inherits from:** {', '.join(f'`{b}`' for b in cls.bases)}")

    if cls.description:
        lines.append(f"\n{cls.description}")

    methods = cls.methods
    if not include_private:
        methods = [
            m
            for m in methods
            if not m.name.startswith("_")
            or m.name in ("__init__", "__call__", "__enter__", "__exit__")
        ]

    if methods:
        lines.append("\n**Methods:**\n")
        for method in methods:
            sig_line = format_function_signature_line(method)
            lines.append(f"#### `{method.name}`\n")
            lines.append(f"```python\n{sig_line}\n```\n")
            if method.description:
                lines.append(f"{method.description}\n")
            if method.parameters:
                _append_params_table(lines, method.parameters)

    lines.append("")


def _format_function_docs(func: FunctionSignature, lines: list[str]) -> None:
    """Render one top-level function signature block into *lines*.

    Args:
        func: The function signature to render.
        lines: Mutable list of markdown lines to append to.
    """
    sig_line = format_function_signature_line(func)
    lines.append(f"#### `{func.name}`\n")

    if func.decorators:
        for dec in func.decorators:
            lines.append(f"`{dec}`\n")

    lines.append(f"```python\n{sig_line}\n```\n")

    if func.description:
        lines.append(f"{func.description}\n")

    if func.parameters:
        _append_params_table(lines, func.parameters)

    if func.return_type:
        lines.append(f"**Returns:** `{func.return_type}`\n")

    lines.append("")


def generate_api_reference_markdown(
    functions: list[FunctionSignature],
    classes: list[ClassSignature],
    include_private: bool = False,
) -> str:
    """Generate markdown API reference documentation.

    Args:
        functions: List of function signatures.
        classes: List of class signatures.
        include_private: Whether to include private (underscore) items.

    Returns:
        Markdown string.
    """
    lines: list[str] = []

    # Filter private items unless requested
    if not include_private:
        functions = [f for f in functions if not f.name.startswith("_")]
        classes = [c for c in classes if not c.name.startswith("_")]

    for cls in classes:
        _format_class_docs(cls, lines, include_private)

    if functions:
        if classes:
            lines.append("---\n")
        lines.append("### Functions\n")
        for func in functions:
            _format_function_docs(func, lines)

    return "\n".join(lines)


def get_file_api_docs(file_path: Path) -> str | None:
    """Get API documentation for a single file.

    Args:
        file_path: Path to the source file.

    Returns:
        Markdown API documentation or None if no APIs found.
    """
    extractor = APIDocExtractor()
    functions, classes = extractor.extract_from_file(file_path)

    if not functions and not classes:
        return None

    return generate_api_reference_markdown(functions, classes)
