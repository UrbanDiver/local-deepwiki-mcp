# Search Index Generator

## File Overview

This file provides functionality for generating search indexes from wiki pages. It extracts relevant content from wiki pages including headings, code terms, and snippets to create a searchable index that can be used for fast lookup and filtering of wiki content.

## Dependencies

- `json` - For serializing the search index to JSON format
- `re` - For regular expression operations when extracting content
- `pathlib.Path` - For handling file system paths
- `local_deepwiki.models.WikiPage` - Model representing wiki pages

## Functions

### `extract_headings(content: str) -> list[str]`

Extracts all headings from the given content.

**Parameters:**
- `content` (str): The wiki page content to extract headings from

**Returns:**
- `list[str]`: List of extracted headings

### `extract_code_terms(content: str) -> list[str]`

Extracts code terms (likely code snippets or identifiers) from the given content.

**Parameters:**
- `content` (str): The wiki page content to extract code terms from

**Returns:**
- `list[str]`: List of extracted code terms

### `extract_snippet(content: str) -> str`

Extracts a snippet from the given content, likely the first paragraph or a summary.

**Parameters:**
- `content` (str): The wiki page content to extract snippet from

**Returns:**
- `str`: Extracted snippet text

### `generate_search_entry(page: WikiPage) -> dict`

Generate a search index entry for a wiki page.

**Parameters:**
- `page` (WikiPage): The wiki page to generate entry for

**Returns:**
- `dict`: Dictionary with searchable fields including path, title, headings, terms, and snippet

### `generate_search_index(pages: list[WikiPage]) -> list[dict]`

Generate a search index from wiki pages.

**Parameters:**
- `pages` (list[WikiPage]): List of wiki pages to index

**Returns:**
- `list[dict]`: List of search entries for all pages

### `write_search_index(wiki_path: Path, pages: list[WikiPage]) -> Path`

Generate and write search index to disk.

**Parameters:**
- `wiki_path` (Path): Path to wiki directory where index should be written
- `pages` (list[WikiPage]): List of wiki pages to index

**Returns:**
- `Path`: Path to the generated search.json file

## Usage Examples

```python
from pathlib import Path
from local_deepwiki.models import WikiPage
from local_deepwiki.generators.search import write_search_index

# Example usage
wiki_path = Path("/path/to/wiki")
pages = [
    WikiPage(
        path="page1.md",
        title="Page One",
        content="# Introduction\nThis is the content of page one."
    ),
    WikiPage(
        path="page2.md",
        title="Page Two",
        content="# Guide\nThis is the content of page two."
    )
]

# Generate and write search index
index_path = write_search_index(wiki_path, pages)
print(f"Search index written to: {index_path}")
```

## Output Format

The generated search index is a JSON file containing an array of entries, each with the following structure:

```json
[
  {
    "path": "page1.md",
    "title": "Page One",
    "headings": ["Introduction"],
    "terms": ["code", "example"],
    "snippet": "This is the content of page one."
  }
]
```

## See Also

- [test_search](../../../tests/test_search.md) - uses this
- [wiki](wiki.md) - uses this
- [models](../models.md) - dependency
- [crosslinks](crosslinks.md) - shares 3 dependencies
- [see_also](see_also.md) - shares 3 dependencies
