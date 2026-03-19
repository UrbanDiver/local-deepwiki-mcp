"""Tests for node utility functions, extraction helpers, and edge cases."""

from __future__ import annotations

import pytest

from local_deepwiki.core.parser import (
    LANGUAGE_MODULES,
    CodeParser,
    _collect_preceding_comments,
    _get_block_comment,
    _get_javadoc_or_doxygen,
    _get_jsdoc_or_line_comments,
    _get_python_docstring,
    _get_swift_docstring,
    find_nodes_by_type,
    get_node_name,
    get_node_text,
)
from local_deepwiki.models import Language


class TestNodeHelpers:
    """Test node helper functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_get_node_text(self):
        """Test extracting text from nodes."""
        code = b"def foo(): pass"
        root = self.parser.parse_source(code, Language.PYTHON)

        # Get the function definition node
        func_node = root.children[0]
        text = get_node_text(func_node, code)
        assert text == "def foo(): pass"

    def test_get_node_name_python_function(self):
        """Test getting name from Python function."""
        code = b"def my_function(): pass"
        root = self.parser.parse_source(code, Language.PYTHON)
        func_node = root.children[0]

        name = get_node_name(func_node, code, Language.PYTHON)
        assert name == "my_function"

    def test_get_node_name_python_class(self):
        """Test getting name from Python class."""
        code = b"class MyClass: pass"
        root = self.parser.parse_source(code, Language.PYTHON)
        class_node = root.children[0]

        name = get_node_name(class_node, code, Language.PYTHON)
        assert name == "MyClass"


class TestNodeNameEdgeCases:
    """Test edge cases for get_node_name function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_get_node_name_returns_none_for_anonymous(self):
        """Test get_node_name returns None for anonymous functions."""
        # Python lambda has no name - tree-sitter may find multiple lambda nodes
        # due to nested structure (lambda keyword and lambda expression)
        code = b"x = lambda y: y + 1"
        root = self.parser.parse_source(code, Language.PYTHON)

        # Find the lambda node - may find multiple due to tree-sitter structure
        lambda_nodes = find_nodes_by_type(root, {"lambda"})
        assert len(lambda_nodes) >= 1

        # The first lambda node (outermost) should have no name
        name = get_node_name(lambda_nodes[0], code, Language.PYTHON)
        assert name is None

    def test_get_node_name_javascript_arrow_function(self):
        """Test get_node_name with JavaScript arrow function."""
        code = b"const greet = (name) => `Hello, ${name}`;"
        root = self.parser.parse_source(code, Language.JAVASCRIPT)

        # Arrow functions don't have names directly
        arrow_nodes = find_nodes_by_type(root, {"arrow_function"})
        assert len(arrow_nodes) == 1

        name = get_node_name(arrow_nodes[0], code, Language.JAVASCRIPT)
        # Arrow functions typically don't have a direct name child
        assert name is None

    def test_get_node_name_field_access_fallback(self):
        """Test get_node_name uses field access when no direct identifier child."""
        # JavaScript arrow function assigned to a const has name via field_name
        code = b"const greet = (x) => x"
        root = self.parser.parse_source(code, Language.JAVASCRIPT)

        # Find variable_declarator which has a "name" field
        declarator_nodes = find_nodes_by_type(root, {"variable_declarator"})
        assert len(declarator_nodes) == 1

        # The variable_declarator should have name = "greet"
        name = get_node_name(declarator_nodes[0], code, Language.JAVASCRIPT)
        # Should find "greet" via the identifier child
        assert name == "greet"

    def test_get_node_name_via_field_name(self):
        """Test get_node_name uses child_by_field_name for languages like Go.

        Go method declarations have 'field_identifier' children (not 'identifier'),
        but they have a 'name' field that can be accessed via child_by_field_name.
        """
        code = b"""
type Person struct {}

func (p Person) Greet() string {
    return "Hello"
}
"""
        root = self.parser.parse_source(code, Language.GO)

        # Find method_declaration - Go receiver methods
        method_nodes = find_nodes_by_type(root, {"method_declaration"})
        assert len(method_nodes) == 1

        method_node = method_nodes[0]
        # Verify the method has no direct 'identifier' child (it has 'field_identifier')
        has_identifier_child = any(c.type == "identifier" for c in method_node.children)
        # Go uses field_identifier, not identifier
        assert not has_identifier_child

        # But get_node_name should still find the name via field access
        name = get_node_name(method_node, code, Language.GO)
        assert name == "Greet"


class TestFindNodesByType:
    """Test find_nodes_by_type function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_find_multiple_node_types(self):
        """Test finding multiple node types at once."""
        code = b"""
def func1(): pass
class MyClass:
    def method1(self): pass
def func2(): pass
"""
        root = self.parser.parse_source(code, Language.PYTHON)

        # Find both functions and classes
        nodes = find_nodes_by_type(root, {"function_definition", "class_definition"})

        # Should find 3 function_definitions and 1 class_definition
        # Actually: func1, method1, func2 (3 functions) + MyClass (1 class) = 4 total
        assert len(nodes) >= 3  # At least the standalone functions

    def test_find_no_matching_nodes(self):
        """Test finding nodes when none exist."""
        code = b"x = 1"
        root = self.parser.parse_source(code, Language.PYTHON)

        nodes = find_nodes_by_type(root, {"function_definition"})
        assert nodes == []


class TestCollectPrecedingComments:
    """Test _collect_preceding_comments function edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_no_preceding_comments(self):
        """Test function with no preceding comments."""
        code = b"func noComments() {}"
        root = self.parser.parse_source(code, Language.GO)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        # Call the function directly
        comments = _collect_preceding_comments(func_nodes[0], code, {"comment"}, "//")
        assert comments == []

    def test_preceding_comment_wrong_prefix(self):
        """Test that non-matching prefix comments are not collected."""
        # Go code with /* */ block comment instead of //
        code = b"""/* Block comment */
func example() {}"""
        root = self.parser.parse_source(code, Language.GO)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        # Looking for // comments should not find /* */
        comments = _collect_preceding_comments(func_nodes[0], code, {"comment"}, "//")
        # Block comment doesn't match // prefix
        assert len(comments) == 0

    def test_preceding_comments_no_prefix_filter(self):
        """Test collecting comments without prefix filter."""
        code = b"""// Comment 1
// Comment 2
func example() {}"""
        root = self.parser.parse_source(code, Language.GO)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        # No prefix filter
        comments = _collect_preceding_comments(func_nodes[0], code, {"comment"}, None)
        assert len(comments) == 2


class TestDocstringExtractorHelpers:
    """Direct tests for docstring extractor helper functions to cover edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_python_docstring_no_body(self):
        """Test _get_python_docstring with function that has no body field."""
        # Parse a simple expression - not a function
        code = b"x = 1"
        root = self.parser.parse_source(code, Language.PYTHON)
        # The root node itself has no 'body' field in the function sense
        result = _get_python_docstring(root, code)
        assert result is None

    def test_python_docstring_expression_not_statement(self):
        """Test Python function where first body element is not expression_statement."""
        # A function with assignment as first statement, not docstring
        code = b"""def func():
    x = 1
    return x"""
        root = self.parser.parse_source(code, Language.PYTHON)
        func_node = root.children[0]
        result = _get_python_docstring(func_node, code)
        assert result is None

    def test_python_class_no_docstring(self):
        """Test Python class with no docstring."""
        code = b"""class Empty:
    pass"""
        root = self.parser.parse_source(code, Language.PYTHON)
        class_node = root.children[0]
        result = _get_python_docstring(class_node, code)
        assert result is None

    def test_jsdoc_no_comments_returns_none(self):
        """Test _get_jsdoc_or_line_comments returns None when no comments exist."""
        code = b"function noDoc() {}"
        root = self.parser.parse_source(code, Language.JAVASCRIPT)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        result = _get_jsdoc_or_line_comments(func_nodes[0], code)
        assert result is None

    def test_jsdoc_regular_comment_not_jsdoc(self):
        """Test that regular /* */ comment is not extracted as JSDoc."""
        code = b"""/* Regular comment, not JSDoc */
function hello() {}"""
        root = self.parser.parse_source(code, Language.JAVASCRIPT)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        result = _get_jsdoc_or_line_comments(func_nodes[0], code)
        # Regular /* */ should not be extracted - only /** */ is JSDoc
        # However, the code checks for "/**" prefix, so this should be None
        assert result is None

    def test_javadoc_no_comments(self):
        """Test _get_javadoc_or_doxygen returns None when no comments exist."""
        code = b"""class Test {
    void noDoc() {}
}"""
        root = self.parser.parse_source(code, Language.JAVA)
        func_nodes = find_nodes_by_type(root, {"method_declaration"})
        assert len(func_nodes) == 1

        result = _get_javadoc_or_doxygen(func_nodes[0], code)
        assert result is None

    def test_javadoc_regular_block_comment(self):
        """Test that regular /* */ is not extracted as Javadoc."""
        code = b"""class Test {
    /* Regular block comment */
    void hello() {}
}"""
        root = self.parser.parse_source(code, Language.JAVA)
        func_nodes = find_nodes_by_type(root, {"method_declaration"})
        assert len(func_nodes) == 1

        result = _get_javadoc_or_doxygen(func_nodes[0], code)
        assert result is None

    def test_swift_docstring_no_comments(self):
        """Test _get_swift_docstring returns None when no comments exist."""
        code = b"func noDoc() {}"
        root = self.parser.parse_source(code, Language.SWIFT)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        result = _get_swift_docstring(func_nodes[0], code)
        assert result is None

    def test_block_comment_no_prev_sibling(self):
        """Test _get_block_comment returns None when no prev_sibling."""
        code = b"<?php\nfunction first() {}\n?>"
        root = self.parser.parse_source(code, Language.PHP)
        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) == 1

        result = _get_block_comment(func_nodes[0], code, "comment")
        assert result is None

    def test_block_comment_wrong_type(self):
        """Test _get_block_comment returns None when prev_sibling is wrong type."""
        # PHP with a line comment instead of block
        code = b"""<?php
// Line comment
function hello() {}
?>"""
        root = self.parser.parse_source(code, Language.PHP)
        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) == 1

        # The prev_sibling might be the comment, but it's not a block
        result = _get_block_comment(func_nodes[0], code, "doc_comment")
        assert result is None

    def test_block_comment_non_jsdoc_style(self):
        """Test _get_block_comment returns None for /* */ style (not /** */)."""
        code = b"""<?php
/* Regular block comment */
function hello() {}
?>"""
        root = self.parser.parse_source(code, Language.PHP)
        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) == 1

        result = _get_block_comment(func_nodes[0], code, "comment")
        # The function checks for "/**" prefix, so /* */ should return None
        assert result is None
