"""Extraction helpers for AST-based code chunking.

Contains constants for node type identification and standalone functions
for extracting type metadata, decorators, parameters, and exceptions
from tree-sitter AST nodes.
"""

from __future__ import annotations

from typing import Any

from tree_sitter import Node

from local_deepwiki.core.parser import find_nodes_by_type, get_node_text
from local_deepwiki.models import Language


# Node types that represent extractable code units per language
FUNCTION_NODE_TYPES: dict[Language, set[str]] = {
    Language.PYTHON: {"function_definition", "async_function_definition"},
    Language.JAVASCRIPT: {
        "function_declaration",
        "arrow_function",
        "function_expression",
        "method_definition",
    },
    Language.TYPESCRIPT: {
        "function_declaration",
        "arrow_function",
        "function_expression",
        "method_definition",
    },
    Language.GO: {"function_declaration", "method_declaration"},
    Language.RUST: {"function_item"},
    Language.JAVA: {"method_declaration", "constructor_declaration"},
    Language.C: {"function_definition"},
    Language.CPP: {"function_definition"},
    Language.SWIFT: {"function_declaration", "init_declaration"},
    Language.RUBY: {"method", "singleton_method"},
    Language.PHP: {"function_definition", "method_declaration"},
    Language.KOTLIN: {"function_declaration"},
    Language.CSHARP: {"method_declaration", "constructor_declaration"},
}

CLASS_NODE_TYPES: dict[Language, set[str]] = {
    Language.PYTHON: {"class_definition"},
    Language.JAVASCRIPT: {"class_declaration"},
    Language.TYPESCRIPT: {
        "class_declaration",
        "interface_declaration",
        "type_alias_declaration",
    },
    Language.GO: {"type_declaration"},
    Language.RUST: {"struct_item", "impl_item", "trait_item", "enum_item"},
    Language.JAVA: {"class_declaration", "interface_declaration", "enum_declaration"},
    Language.C: {"struct_specifier"},
    Language.CPP: {"class_specifier", "struct_specifier"},
    Language.SWIFT: {
        "class_declaration",
        "struct_declaration",
        "protocol_declaration",
        "enum_declaration",
        "extension_declaration",
    },
    Language.RUBY: {"class", "module"},
    Language.PHP: {"class_declaration", "interface_declaration", "trait_declaration"},
    Language.KOTLIN: {"class_declaration", "object_declaration"},
    Language.CSHARP: {
        "class_declaration",
        "struct_declaration",
        "interface_declaration",
        "enum_declaration",
    },
}

IMPORT_NODE_TYPES: dict[Language, set[str]] = {
    Language.PYTHON: {"import_statement", "import_from_statement"},
    Language.JAVASCRIPT: {"import_statement", "import_declaration"},
    Language.TYPESCRIPT: {"import_statement", "import_declaration"},
    Language.GO: {"import_declaration"},
    Language.RUST: {"use_declaration"},
    Language.JAVA: {"import_declaration"},
    Language.C: {"preproc_include"},
    Language.CPP: {"preproc_include"},
    Language.SWIFT: {"import_declaration"},
    Language.RUBY: {"call"},  # require/require_relative are method calls in Ruby AST
    Language.PHP: {"namespace_use_declaration"},  # use statements in PHP
    Language.KOTLIN: {"import_header"},
    Language.CSHARP: {"using_directive"},
}


def _get_python_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a Python class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type == "identifier":
                    parents.append(get_node_text(arg, source))
    return parents


def _get_ts_js_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a TypeScript/JavaScript class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "class_heritage":
            for clause in child.children:
                if clause.type in ("extends_clause", "implements_clause"):
                    for item in clause.children:
                        if item.type in ("identifier", "type_identifier"):
                            parents.append(get_node_text(item, source))
    return parents


def _get_java_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a Java class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "superclass":
            for item in child.children:
                if item.type == "type_identifier":
                    parents.append(get_node_text(item, source))
        elif child.type == "super_interfaces":
            for item in find_nodes_by_type(child, {"type_identifier"}):
                parents.append(get_node_text(item, source))
    return parents


def _get_swift_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a Swift class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "type_inheritance_clause":
            for item in child.children:
                if item.type in ("user_type", "type_identifier"):
                    text = get_node_text(item, source)
                    if text and text not in (":", ","):
                        parents.append(text)
    return parents


def _get_cpp_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a C++ class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "base_class_clause":
            for item in find_nodes_by_type(child, {"type_identifier"}):
                parents.append(get_node_text(item, source))
    return parents


def _get_ruby_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a Ruby class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "superclass":
            for sc in child.children:
                if sc.type in ("constant", "scope_resolution"):
                    parents.append(get_node_text(sc, source))
    return parents


def _get_php_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a PHP class definition."""
    parents = []
    for child in class_node.children:
        if child.type in ("base_clause", "class_interface_clause"):
            for item in find_nodes_by_type(child, {"name", "qualified_name"}):
                parents.append(get_node_text(item, source))
    return parents


def _get_kotlin_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a Kotlin class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "delegation_specifiers":
            for spec in child.children:
                if spec.type == "delegation_specifier":
                    for item in find_nodes_by_type(
                        spec, {"user_type", "simple_identifier"}
                    ):
                        text = get_node_text(item, source)
                        if text and text not in (":", ","):
                            parents.append(text)
                            break
    return parents


def _get_csharp_parents(class_node: Node, source: bytes) -> list[str]:
    """Extract parent class names from a C# class definition."""
    parents = []
    for child in class_node.children:
        if child.type == "base_list":
            for item in find_nodes_by_type(
                child, {"identifier", "generic_name", "qualified_name"}
            ):
                text = get_node_text(item, source)
                if text:
                    parents.append(text)
    return parents


def get_parent_classes(
    class_node: Node, source: bytes, language: Language
) -> list[str]:
    """Extract parent class names from a class definition.

    Args:
        class_node: The class AST node.
        source: Source bytes.
        language: Programming language.

    Returns:
        List of parent class names.
    """
    match language:
        case Language.PYTHON:
            return _get_python_parents(class_node, source)
        case Language.TYPESCRIPT | Language.JAVASCRIPT:
            return _get_ts_js_parents(class_node, source)
        case Language.JAVA:
            return _get_java_parents(class_node, source)
        case Language.SWIFT:
            return _get_swift_parents(class_node, source)
        case Language.CPP:
            return _get_cpp_parents(class_node, source)
        case Language.RUBY:
            return _get_ruby_parents(class_node, source)
        case Language.PHP:
            return _get_php_parents(class_node, source)
        case Language.KOTLIN:
            return _get_kotlin_parents(class_node, source)
        case Language.CSHARP:
            return _get_csharp_parents(class_node, source)
    return []


def _get_splat_prefix(node_type: str) -> str:
    """Return the prefix string for a splat parameter node type."""
    return "*" if node_type == "list_splat_pattern" else "**"


def _extract_typed_parameter(
    child: Node, source: bytes
) -> tuple[str, str | None] | None:
    """Extract name and type hint from a typed_parameter node.

    Returns:
        A (name, type_hint) tuple, or None if the parameter should be skipped.
    """
    name_node = None
    type_node = None
    splat_pattern = None

    for c in child.children:
        if c.type == "identifier":
            name_node = c
        elif c.type == "type":
            type_node = c
        elif c.type in ("list_splat_pattern", "dictionary_splat_pattern"):
            splat_pattern = c
            for sc in c.children:
                if sc.type == "identifier":
                    name_node = sc
                    break

    if not name_node:
        return None
    name = get_node_text(name_node, source)
    if name in ("self", "cls"):
        return None
    type_hint = get_node_text(type_node, source) if type_node else None
    if splat_pattern:
        name = f"{_get_splat_prefix(splat_pattern.type)}{name}"
    return name, type_hint


def _extract_splat_parameter(
    child: Node, source: bytes
) -> tuple[str, str | None] | None:
    """Extract name and type hint from a list_splat_pattern or dictionary_splat_pattern node.

    Returns:
        A (name, type_hint) tuple, or None if nothing could be extracted.
    """
    prefix = _get_splat_prefix(child.type)
    for c in child.children:
        if c.type == "identifier":
            return f"{prefix}{get_node_text(c, source)}", None
        if c.type == "typed_parameter":
            inner_name = None
            inner_type = None
            for tc in c.children:
                if tc.type == "identifier":
                    inner_name = tc
                elif tc.type == "type":
                    inner_type = tc
            if inner_name:
                name = get_node_text(inner_name, source)
                type_hint = get_node_text(inner_type, source) if inner_type else None
                return f"{prefix}{name}", type_hint
            break
    return None


def extract_python_parameter_types(
    func_node: Node, source: bytes
) -> dict[str, str | None]:
    """Extract parameter types from a Python function.

    Args:
        func_node: The function_definition AST node.
        source: Source code bytes.

    Returns:
        Dictionary mapping parameter names to their type hints.
    """
    param_types: dict[str, str | None] = {}
    params_node = func_node.child_by_field_name("parameters")
    if not params_node:
        return param_types

    for child in params_node.children:
        if child.type == "identifier":
            name = get_node_text(child, source)
            if name not in ("self", "cls"):
                param_types[name] = None

        elif child.type == "typed_parameter":
            result = _extract_typed_parameter(child, source)
            if result is not None:
                param_types[result[0]] = result[1]

        elif child.type == "default_parameter":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = get_node_text(name_node, source)
                if name not in ("self", "cls"):
                    param_types[name] = None

        elif child.type == "typed_default_parameter":
            name_node = child.child_by_field_name("name")
            type_node = child.child_by_field_name("type")
            if name_node:
                name = get_node_text(name_node, source)
                if name not in ("self", "cls"):
                    param_types[name] = (
                        get_node_text(type_node, source) if type_node else None
                    )

        elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
            result = _extract_splat_parameter(child, source)
            if result is not None:
                param_types[result[0]] = result[1]

    return param_types


def extract_python_parameter_defaults(func_node: Node, source: bytes) -> dict[str, str]:
    """Extract parameter default values from a Python function.

    Args:
        func_node: The function_definition AST node.
        source: Source code bytes.

    Returns:
        Dictionary mapping parameter names to their default values.
    """
    defaults: dict[str, str] = {}
    params_node = func_node.child_by_field_name("parameters")
    if not params_node:
        return defaults

    for child in params_node.children:
        if child.type == "default_parameter":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node and value_node:
                name = get_node_text(name_node, source)
                if name not in ("self", "cls"):
                    defaults[name] = get_node_text(value_node, source)

        elif child.type == "typed_default_parameter":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node and value_node:
                name = get_node_text(name_node, source)
                if name not in ("self", "cls"):
                    defaults[name] = get_node_text(value_node, source)

    return defaults


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


def is_async_function(func_node: Node) -> bool:
    """Check if a function is async.

    Args:
        func_node: The function AST node.

    Returns:
        True if the function is async.
    """
    return func_node.type == "async_function_definition" or any(
        c.type == "async" for c in func_node.children
    )


def _extract_raise_target(raise_node: Node, source: bytes) -> str | None:
    """Extract the exception name from a raise_statement node.

    Handles both direct raises (``raise ValueError``) and call raises
    (``raise ValueError("msg")``), as well as attribute forms
    (``raise errors.CustomError``).

    Args:
        raise_node: A raise_statement AST node.
        source: Source code bytes.

    Returns:
        Exception name string, or None if it could not be extracted.
    """
    for child in raise_node.children:
        if child.type == "identifier":
            exc_name = get_node_text(child, source)
            return exc_name if exc_name and exc_name != "raise" else None
        if child.type == "call":
            for call_child in child.children:
                if call_child.type in ("identifier", "attribute"):
                    exc_name = get_node_text(call_child, source)
                    return exc_name if exc_name else None
            break
    return None


def _find_raises_in_block(node: Node, source: bytes, exceptions: set[str]) -> None:
    """Recursively collect raised exception names, skipping nested function defs."""
    if node.type == "raise_statement":
        name = _extract_raise_target(node, source)
        if name:
            exceptions.add(name)
    for child in node.children:
        if child.type not in ("function_definition", "async_function_definition"):
            _find_raises_in_block(child, source, exceptions)


def extract_python_raised_exceptions(func_node: Node, source: bytes) -> list[str]:
    """Extract exception types raised by a Python function.

    Finds all `raise` statements within the function and extracts the exception
    type being raised.

    Args:
        func_node: The function_definition AST node.
        source: Source code bytes.

    Returns:
        List of unique exception type names raised by the function.
    """
    exceptions: set[str] = set()
    for child in func_node.children:
        if child.type == "block":
            _find_raises_in_block(child, source, exceptions)
    return sorted(exceptions)


def extract_function_type_metadata(
    func_node: Node, source: bytes, language: Language
) -> dict[str, Any]:
    """Extract type annotation metadata from a function node.

    Args:
        func_node: The function AST node.
        source: Source code bytes.
        language: Programming language.

    Returns:
        Metadata dictionary with type information.
    """
    metadata: dict[str, Any] = {}

    if language == Language.PYTHON:
        # Extract parameter types
        param_types = extract_python_parameter_types(func_node, source)
        # Only include parameters that have type hints
        typed_params = {k: v for k, v in param_types.items() if v is not None}
        if typed_params:
            metadata["parameter_types"] = typed_params

        # Extract parameter defaults
        param_defaults = extract_python_parameter_defaults(func_node, source)
        if param_defaults:
            metadata["parameter_defaults"] = param_defaults

        # Extract return type
        return_type = extract_python_return_type(func_node, source)
        if return_type:
            metadata["return_type"] = return_type

        # Extract decorators
        decorators = extract_python_decorators(func_node, source)
        if decorators:
            metadata["decorators"] = decorators

        # Check if async
        if is_async_function(func_node):
            metadata["is_async"] = True

        # Extract raised exceptions
        raised_exceptions = extract_python_raised_exceptions(func_node, source)
        if raised_exceptions:
            metadata["raises"] = raised_exceptions

    return metadata
