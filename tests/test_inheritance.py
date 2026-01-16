"""Tests for inheritance tree generation."""

import pytest

from local_deepwiki.generators.inheritance import (
    ClassNode,
    find_root_classes,
    generate_inheritance_diagram,
    generate_inheritance_tree_text,
)


class TestClassNode:
    """Tests for ClassNode dataclass."""

    def test_creates_basic_node(self):
        """Test creating a basic class node."""
        node = ClassNode(name="MyClass", file_path="src/myclass.py")
        assert node.name == "MyClass"
        assert node.file_path == "src/myclass.py"
        assert node.parents == []
        assert node.children == []
        assert node.is_abstract is False

    def test_creates_node_with_inheritance(self):
        """Test creating a node with parent classes."""
        node = ClassNode(
            name="ChildClass",
            file_path="src/child.py",
            parents=["BaseClass", "Mixin"],
            is_abstract=True,
        )
        assert node.parents == ["BaseClass", "Mixin"]
        assert node.is_abstract is True


class TestFindRootClasses:
    """Tests for find_root_classes function."""

    def test_finds_root_with_children(self):
        """Test finding root classes that have children."""
        classes = {
            "Base": ClassNode("Base", "base.py", [], ["Child1", "Child2"]),
            "Child1": ClassNode("Child1", "child1.py", ["Base"], []),
            "Child2": ClassNode("Child2", "child2.py", ["Base"], []),
        }
        roots = find_root_classes(classes)
        assert roots == ["Base"]

    def test_excludes_root_without_children(self):
        """Test that classes with no parents but no children are excluded."""
        classes = {
            "Standalone": ClassNode("Standalone", "standalone.py", [], []),
            "Base": ClassNode("Base", "base.py", [], ["Child"]),
            "Child": ClassNode("Child", "child.py", ["Base"], []),
        }
        roots = find_root_classes(classes)
        assert "Standalone" not in roots
        assert "Base" in roots

    def test_returns_empty_for_no_hierarchies(self):
        """Test returns empty when no inheritance hierarchies exist."""
        classes = {
            "Class1": ClassNode("Class1", "c1.py", [], []),
            "Class2": ClassNode("Class2", "c2.py", [], []),
        }
        roots = find_root_classes(classes)
        assert roots == []

    def test_multiple_roots(self):
        """Test finding multiple root classes."""
        classes = {
            "BaseA": ClassNode("BaseA", "a.py", [], ["ChildA"]),
            "ChildA": ClassNode("ChildA", "ca.py", ["BaseA"], []),
            "BaseB": ClassNode("BaseB", "b.py", [], ["ChildB"]),
            "ChildB": ClassNode("ChildB", "cb.py", ["BaseB"], []),
        }
        roots = find_root_classes(classes)
        assert sorted(roots) == ["BaseA", "BaseB"]


class TestGenerateInheritanceDiagram:
    """Tests for generate_inheritance_diagram function."""

    def test_returns_none_for_empty(self):
        """Test returns None for empty classes."""
        assert generate_inheritance_diagram({}) is None

    def test_returns_none_for_no_inheritance(self):
        """Test returns None when no classes have inheritance."""
        classes = {
            "Class1": ClassNode("Class1", "c1.py", [], []),
            "Class2": ClassNode("Class2", "c2.py", [], []),
        }
        assert generate_inheritance_diagram(classes) is None

    def test_generates_diagram_with_inheritance(self):
        """Test generates diagram for classes with inheritance."""
        classes = {
            "Base": ClassNode("Base", "base.py", [], ["Child"]),
            "Child": ClassNode("Child", "child.py", ["Base"], []),
        }
        diagram = generate_inheritance_diagram(classes)
        assert diagram is not None
        assert "```mermaid" in diagram
        assert "classDiagram" in diagram
        assert "--|>" in diagram  # Inheritance arrow

    def test_marks_abstract_classes(self):
        """Test that abstract classes are marked."""
        classes = {
            "AbstractBase": ClassNode("AbstractBase", "base.py", [], ["Impl"], is_abstract=True),
            "Impl": ClassNode("Impl", "impl.py", ["AbstractBase"], []),
        }
        diagram = generate_inheritance_diagram(classes)
        assert "<<abstract>>" in diagram


class TestGenerateInheritanceTreeText:
    """Tests for generate_inheritance_tree_text function."""

    def test_generates_single_node(self):
        """Test generating tree for single node with no children."""
        classes = {
            "Root": ClassNode("Root", "root.py", [], []),
        }
        lines = generate_inheritance_tree_text(classes, "Root")
        assert len(lines) == 1
        assert "Root" in lines[0]

    def test_generates_tree_with_children(self):
        """Test generating tree with parent and children."""
        classes = {
            "Base": ClassNode("Base", "base.py", [], ["Child1", "Child2"]),
            "Child1": ClassNode("Child1", "c1.py", ["Base"], []),
            "Child2": ClassNode("Child2", "c2.py", ["Base"], []),
        }
        lines = generate_inheritance_tree_text(classes, "Base")
        assert len(lines) == 3
        assert "Base" in lines[0]
        assert any("Child1" in line for line in lines)
        assert any("Child2" in line for line in lines)

    def test_handles_deep_hierarchy(self):
        """Test generating tree with multiple levels."""
        classes = {
            "Root": ClassNode("Root", "root.py", [], ["Middle"]),
            "Middle": ClassNode("Middle", "mid.py", ["Root"], ["Leaf"]),
            "Leaf": ClassNode("Leaf", "leaf.py", ["Middle"], []),
        }
        lines = generate_inheritance_tree_text(classes, "Root")
        assert len(lines) == 3
        # Check proper nesting
        assert lines[0].startswith("- ")  # Root at top level
        assert "└─" in lines[1]  # Children indented

    def test_avoids_cycles(self):
        """Test that cycles are handled gracefully."""
        classes = {
            "A": ClassNode("A", "a.py", ["B"], ["B"]),
            "B": ClassNode("B", "b.py", ["A"], ["A"]),
        }
        lines = generate_inheritance_tree_text(classes, "A")
        # Should not infinite loop - just visit each once
        assert len(lines) <= 2

    def test_includes_file_name(self):
        """Test that file name is included in output."""
        classes = {
            "MyClass": ClassNode("MyClass", "src/mymodule/myclass.py", [], []),
        }
        lines = generate_inheritance_tree_text(classes, "MyClass")
        assert "myclass.py" in lines[0]

    def test_marks_abstract_classes(self):
        """Test that abstract classes are marked in text tree."""
        classes = {
            "AbstractBase": ClassNode("AbstractBase", "base.py", [], [], is_abstract=True),
        }
        lines = generate_inheritance_tree_text(classes, "AbstractBase")
        assert "(abstract)" in lines[0]
