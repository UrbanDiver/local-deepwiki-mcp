# diagrams.py

## File Overview

This file provides functionality for generating various Mermaid diagrams from code chunks. It includes functions to create architecture diagrams, class diagrams, dependency diagrams, and file tree diagrams, enabling visual representation of code structure and relationships.

## Dependencies

- `local_deepwiki.models.CodeChunk`
- `local_deepwiki.models.IndexStatus`

## Functions

### generate_architecture_diagram

```python
def generate_architecture_diagram(chunks: list[CodeChunk]) -> str:
    """Generate a Mermaid architecture diagram from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid diagram string.
    """
```

Generates a Mermaid architecture diagram that visualizes code chunks organized by modules/files. The diagram shows relationships between different code modules in a hierarchical structure.

**Parameters:**
- `chunks` (list[CodeChunk]): List of code chunks to visualize

**Returns:**
- `str`: Mermaid diagram string representing the architecture

**Usage Example:**
```python
chunks = [chunk1, chunk2, chunk3]  # List of CodeChunk objects
diagram = generate_architecture_diagram(chunks)
print(diagram)
```

### generate_class_diagram

```python
def generate_class_diagram(chunks: list[CodeChunk]) -> str:
    """Generate a Mermaid class diagram from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid diagram string.
    """
```

Generates a Mermaid class diagram that visualizes classes and their relationships from code chunks. This function analyzes the code structure to identify class definitions and their connections.

**Parameters:**
- `chunks` (list[CodeChunk]): List of code chunks to visualize

**Returns:**
- `str`: Mermaid diagram string representing the class structure

### generate_dependency_diagram

```python
def generate_dependency_diagram(chunks: list[CodeChunk]) -> str:
    """Generate a Mermaid dependency diagram from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid diagram string.
    """
```

Generates a Mermaid dependency diagram that shows relationships and dependencies between different code elements. This function identifies import statements and other dependency relationships in the code.

**Parameters:**
- `chunks` (list[CodeChunk]): List of code chunks to visualize

**Returns:**
- `str`: Mermaid diagram string representing the dependencies

### generate_file_tree_diagram

```python
def generate_file_tree_diagram(chunks: list[CodeChunk]) -> str:
    """Generate a Mermaid file tree diagram from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid diagram string.
    """
```

Generates a Mermaid file tree diagram that visualizes the hierarchical structure of files and directories from code chunks. This function organizes chunks by their file paths to create a tree representation.

**Parameters:**
- `chunks` (list[CodeChunk]): List of code chunks to visualize

**Returns:**
- `str`: Mermaid diagram string representing the file tree structure

### render_tree

```python
def render_tree(chunks: list[CodeChunk]) -> str:
    """Render a tree structure from code chunks.

    Args:
        chunks: List of code chunks to visualize.

    Returns:
        Mermaid diagram string.
    """
```

Renders a tree structure visualization from code chunks, typically used for hierarchical file organization or code structure representation.

**Parameters:**
- `chunks` (list[CodeChunk]): List of code chunks to visualize

**Returns:**
- `str`: Mermaid diagram string representing the tree structure

## Usage Examples

### Basic Usage

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram, generate_class_diagram

# Assuming you have a list of CodeChunk objects
chunks = [...]  # Your list of code chunks

# Generate architecture diagram
architecture_diagram = generate_architecture_diagram(chunks)
print(architecture_diagram)

# Generate class diagram
class_diagram = generate_class_diagram(chunks)
print(class_diagram)
```

### Complete Diagram Generation

```python
from local_deepwiki.generators.diagrams import (
    generate_architecture_diagram,
    generate_class_diagram,
    generate_dependency_diagram,
    generate_file_tree_diagram
)

# Generate all types of diagrams
diagrams = {
    'architecture': generate_architecture_diagram(chunks),
    'class': generate_class_diagram(chunks),
    'dependency': generate_dependency_diagram(chunks),
    'file_tree': generate_file_tree_diagram(chunks)
}

for diagram_type, diagram in diagrams.items():
    print(f"=== {diagram_type.upper()} DIAGRAM ===")
    print(diagram)
    print()
```