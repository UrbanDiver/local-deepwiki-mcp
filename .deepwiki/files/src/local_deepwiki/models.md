# Local DeepWiki Models Documentation

## File Overview

This file defines the data models and structures used throughout the Local DeepWiki application. It provides Pydantic-based models for representing wiki pages, file information, indexing status, and search results. These models serve as the core data structures for data validation, serialization, and API responses.

## Classes

### `WikiPage`
Represents a generated wiki page with its metadata and content.

**Fields:**
- `path` (str): Relative path in wiki directory
- `title` (str): Page title
- `content` (str): Markdown content
- `generated_at` (float): Generation timestamp

**Usage:**
```python
page = WikiPage(
    path="docs/installation.md",
    title="Installation Guide",
    content="# Installation\n\nStep 1: Install dependencies...",
    generated_at=1699123456.789
)
```

## Dependencies

This file imports:
- `Enum` from `enum` - for defining enumerated types
- `Path` from `pathlib` - for path manipulation
- `Any` from `typing` - for type hints
- `BaseModel` and `Field` from `pydantic` - for data validation and serialization

## Additional Models (Not Implemented in Code)

The file declares several model classes in its imports but only implements `WikiPage`. The following classes are referenced but not defined in the provided code:

- `Language`: Enum for programming languages
- `ChunkType`: Enum for chunk types
- `CodeChunk`: Model for code chunks
- `FileInfo`: Model for file information
- `IndexStatus`: Model for indexing status
- `WikiStructure`: Model for wiki structure
- `SearchResult`: Model for search results

## Usage Examples

### Creating a WikiPage Instance
```python
from src.local_deepwiki.models import WikiPage

# Create a new wiki page
page = WikiPage(
    path="getting-started.md",
    title="Getting Started",
    content="# Welcome to Local DeepWiki\n\nThis is the start...",
    generated_at=1699123456.789
)

# Access fields
print(page.title)  # Output: "Getting Started"
print(page.path)   # Output: "getting-started.md"
```

### Data Validation
```python
# Pydantic automatically validates data types
try:
    page = WikiPage(
        path="example.md",
        title="Example",
        content="Markdown content",
        generated_at="not_a_timestamp"  # This will raise a validation error
    )
except Exception as e:
    print(f"Validation error: {e}")
```