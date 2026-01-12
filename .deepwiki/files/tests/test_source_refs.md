# File Overview

This file contains test cases for the `source_refs` module, which is responsible for generating and inserting source reference sections into wiki pages. The tests cover various scenarios including handling file pages, module pages, architecture pages, and line information.

# Classes

## TestAddSourceRefsSections

Tests for the `add_source_refs_sections` function. This class contains tests for adding source reference sections to different types of wiki pages.

Key methods:
- `test_adds_sections_to_file_pages`: Tests that sections are added to file documentation pages
- `test_skips_index_pages`: Tests that sections are not added to index pages
- `test_inserts_before_see_also`: Tests that sections are inserted before the "See Also" section
- `test_handles_missing_status`: Tests handling of pages with missing status information
- `test_adds_section_to_module_pages`: Tests that sections are added to module pages
- `test_adds_section_to_architecture_page`: Tests that sections are added to architecture pages

## TestBuildFileToWikiMap

Tests for the [`build_file_to_wiki_map`](../src/local_deepwiki/generators/see_also.md) function. This class tests mapping of source files to wiki page paths.

## TestRelativePath

Tests for the `_relative_path` function. This function calculates relative paths between wiki pages.

Key methods:
- `test_same_directory`: Tests relative path calculation in the same directory
- `test_parent_directory`: Tests relative path calculation to a parent directory
- `test_child_directory`: Tests relative path calculation to a child directory

## TestGenerateSourceRefsSection

Tests for the `generate_source_refs_section` function. This function generates source reference sections for wiki pages.

Key methods:
- `test_single_file_with_wiki_link`: Tests generating section for a single file with a wiki page
- `test_single_file_without_wiki_link`: Tests generating section for a single file without a wiki page
- `test_multiple_files_with_wiki_links`: Tests generating section for multiple files with wiki pages
- `test_multiple_files_mixed_links`: Tests generating section for multiple files with mixed wiki page links

## TestAddSourceRefsSectionsWithLineInfo

Tests for the `add_source_refs_sections` function with line information in status.

Key methods:
- `test_passes_line_info_to_section_generator`: Tests that line info from status is used in generated section

## TestGenerateSourceRefsSectionWithLineInfo

Tests for the `generate_source_refs_section` function with line information.

Key methods:
- `test_single_file_with_line_info`: Tests single file displays line numbers
- `test_multiple_files_with_line_info`: Tests multiple files display line numbers

## TestFormatFileEntry

Tests for the `_format_file_entry` function. This function formats individual file entries for source reference sections.

Key methods:
- `test_without_line_info`: Tests formatting without line information
- `test_with_line_info`: Tests formatting with line information showing start-end range

# Functions

## add_source_refs_sections

Adds source reference sections to wiki pages based on page status information.

Parameters:
- `pages`: List of WikiPage objects to process
- `page_statuses`: Dictionary mapping page paths to WikiPageStatus objects

Returns:
- List of updated WikiPage objects with source reference sections added

## build_file_to_wiki_map

Builds a mapping from source file paths to wiki page paths.

Parameters:
- `pages`: List of WikiPage objects to process

Returns:
- Dictionary mapping source file paths to wiki page paths

## generate_source_refs_section

Generates a source references section for a wiki page.

Parameters:
- `source_files`: List of source file paths
- `current_wiki_path`: Path of the current wiki page
- `file_to_wiki`: Dictionary mapping source file paths to wiki page paths
- `file_line_info`: Optional dictionary mapping file paths to line information

Returns:
- String containing the formatted source references section

## _format_file_entry

Formats a single file entry for a source references section.

Parameters:
- `file_path`: Path of the source file
- `wiki_path`: Path of the corresponding wiki page (optional)
- `current_wiki_path`: Path of the current wiki page
- `line_info`: Optional line information dictionary with "start_line" and "end_line" keys

Returns:
- String formatted file entry

## _relative_path

Calculates the relative path from one wiki page to another.

Parameters:
- `from_path`: Source wiki page path
- `to_path`: Target wiki page path

Returns:
- String representing the relative path

# Usage Examples

## Basic usage of `add_source_refs_sections`

```python
from local_deepwiki.models import WikiPage, WikiPageStatus

pages = [
    WikiPage(
        path="files/src/parser.md",
        title="parser",
        content="# Parser\n\nContent here.",
        generated_at=0,
    ),
]

page_statuses = {
    "files/src/parser.md": WikiPageStatus(
        path="files/src/parser.md",
        source_files=["src/parser.py"],
        source_hashes={"src/parser.py": "abc123"},
        content_hash="xyz",
        generated_at=0,
    ),
}

updated_pages = add_source_refs_sections(pages, page_statuses)
```

## Using `generate_source_refs_section`

```python
result = generate_source_refs_section(
    source_files=["src/parser.py", "src/models.py"],
    current_wiki_path="files/src/chunker.md",
    file_to_wiki={
        "src/parser.py": "files/src/parser.md",
        "src/models.py": "files/src/models.md",
    },
    file_line_info={
        "src/parser.py": {"start_line": 42, "end_line": 150},
    },
)
```

# Related Components

This file works with the following components:

- `WikiPage` and `WikiPageStatus` models from `local_deepwiki.models`
- `add_source_refs_sections` function from `local_deepwiki.generators.source_refs`
- [`build_file_to_wiki_map`](../src/local_deepwiki/generators/see_also.md) function from `local_deepwiki.generators.source_refs`
- `generate_source_refs_section` function from `local_deepwiki.generators.source_refs`
- `_format_file_entry` function from `local_deepwiki.generators.source_refs`
- `_relative_path` function from `local_deepwiki.generators.source_refs`

## API Reference

### class `TestBuildFileToWikiMap`

Tests for [build_file_to_wiki_map](../src/local_deepwiki/generators/see_also.md) function.

**Methods:**

#### `test_builds_correct_mapping`

```python
def test_builds_correct_mapping()
```

Test that file paths are correctly mapped to wiki paths.

#### `test_empty_pages`

```python
def test_empty_pages()
```

Test with empty pages list.


### class `TestRelativePath`

Tests for _relative_path function.

**Methods:**

#### `test_same_directory`

```python
def test_same_directory()
```

Test relative path in same directory.

#### `test_parent_directory`

```python
def test_parent_directory()
```

Test relative path to parent directory.

#### `test_sibling_directory`

```python
def test_sibling_directory()
```

Test relative path to sibling directory.

#### `test_root_to_nested`

```python
def test_root_to_nested()
```

Test relative path from root to nested.


### class `TestGenerateSourceRefsSection`

Tests for generate_source_refs_section function.

**Methods:**

#### `test_single_file_with_wiki_link`

```python
def test_single_file_with_wiki_link()
```

Test generating section for single file with wiki page.

#### `test_single_file_no_wiki_page`

```python
def test_single_file_no_wiki_page()
```

Test generating section for file without wiki page.

#### `test_multiple_files`

```python
def test_multiple_files()
```

Test generating section for multiple files.

#### `test_empty_source_files`

```python
def test_empty_source_files()
```

Test that empty source files returns None.

#### `test_max_items_limit`

```python
def test_max_items_limit()
```

Test that max_items limits the output.

#### `test_skips_self_reference`

```python
def test_skips_self_reference()
```

Test that current page is not linked to itself.


### class `TestAddSourceRefsSections`

Tests for add_source_refs_sections function.

**Methods:**

#### `test_adds_sections_to_file_pages`

```python
def test_adds_sections_to_file_pages()
```

Test that sections are added to file documentation pages.

#### `test_skips_index_pages`

```python
def test_skips_index_pages()
```

Test that index pages are not modified.

#### `test_inserts_before_see_also`

```python
def test_inserts_before_see_also()
```

Test that section is inserted before See Also.

#### `test_handles_missing_status`

```python
def test_handles_missing_status()
```

Test that pages without status are passed through.

#### `test_adds_section_to_module_pages`

```python
def test_adds_section_to_module_pages()
```

Test that sections are added to module pages.

#### `test_adds_section_to_architecture_page`

```python
def test_adds_section_to_architecture_page()
```

Test that sections are added to architecture page.


### class `TestFormatFileEntry`

Tests for _format_file_entry function.

**Methods:**

#### `test_without_line_info`

```python
def test_without_line_info()
```

Test formatting without line info.

#### `test_with_line_info`

```python
def test_with_line_info()
```

Test formatting with line info shows start-end range.

#### `test_with_line_info_and_wiki_link`

```python
def test_with_line_info_and_wiki_link()
```

Test formatting with line info and wiki link.

#### `test_skips_self_link_with_line_info`

```python
def test_skips_self_link_with_line_info()
```

Test that self-reference doesn't include link even with line info.


### class `TestGenerateSourceRefsSectionWithLineInfo`

Tests for generate_source_refs_section with line info.

**Methods:**

#### `test_single_file_with_line_info`

```python
def test_single_file_with_line_info()
```

Test single file displays line numbers.

#### `test_multiple_files_with_line_info`

```python
def test_multiple_files_with_line_info()
```

Test multiple files each display their line numbers.

#### `test_partial_line_info`

```python
def test_partial_line_info()
```

Test that files without line info fallback gracefully.


### class `TestAddSourceRefsSectionsWithLineInfo`

Tests for add_source_refs_sections with line info in status.

**Methods:**

#### `test_passes_line_info_to_section_generator`

```python
def test_passes_line_info_to_section_generator()
```

Test that line info from status is used in generated section.

#### `test_handles_empty_line_info`

```python
def test_handles_empty_line_info()
```

Test that empty line info works (fallback to no line numbers).



## Class Diagram

```mermaid
classDiagram
    class TestAddSourceRefsSections {
        +test_adds_sections_to_file_pages()
        +test_skips_index_pages()
        +test_inserts_before_see_also()
        +test_handles_missing_status()
        +test_adds_section_to_module_pages()
        +test_adds_section_to_architecture_page()
    }
    class TestAddSourceRefsSectionsWithLineInfo {
        +test_passes_line_info_to_section_generator()
        +test_handles_empty_line_info()
    }
    class TestBuildFileToWikiMap {
        +test_builds_correct_mapping()
        +test_empty_pages()
    }
    class TestFormatFileEntry {
        +test_without_line_info()
        +test_with_line_info()
        +test_with_line_info_and_wiki_link()
        +test_skips_self_link_with_line_info()
    }
    class TestGenerateSourceRefsSection {
        +test_single_file_with_wiki_link()
        +test_single_file_no_wiki_page()
        +test_multiple_files()
        +test_empty_source_files()
        +test_max_items_limit()
        +test_skips_self_reference()
    }
    class TestGenerateSourceRefsSectionWithLineInfo {
        +test_single_file_with_line_info()
        +test_multiple_files_with_line_info()
        +test_partial_line_info()
    }
    class TestRelativePath {
        +test_same_directory()
        +test_parent_directory()
        +test_sibling_directory()
        +test_root_to_nested()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[TestAddSourceRefsSections.t...]
    N1[TestAddSourceRefsSections.t...]
    N2[TestAddSourceRefsSections.t...]
    N3[TestAddSourceRefsSections.t...]
    N4[TestAddSourceRefsSections.t...]
    N5[TestAddSourceRefsSections.t...]
    N6[TestAddSourceRefsSectionsWi...]
    N7[TestAddSourceRefsSectionsWi...]
    N8[TestBuildFileToWikiMap.test...]
    N9[TestBuildFileToWikiMap.test...]
    N10[TestFormatFileEntry.test_wi...]
    N11[TestFormatFileEntry.test_wi...]
    N12[TestFormatFileEntry.test_wi...]
    N13[TestGenerateSourceRefsSecti...]
    N14[TestGenerateSourceRefsSecti...]
    N15[TestGenerateSourceRefsSecti...]
    N16[TestGenerateSourceRefsSecti...]
    N17[TestGenerateSourceRefsSecti...]
    N18[TestGenerateSourceRefsSecti...]
    N19[TestRelativePath.test_paren...]
    N20[TestRelativePath.test_root_...]
    N21[TestRelativePath.test_same_...]
    N22[TestRelativePath.test_sibli...]
    N23[WikiPage]
    N24[WikiPageStatus]
    N25[_format_file_entry]
    N26[_relative_path]
    N27[add_source_refs_sections]
    N28[build_file_to_wiki_map]
    N29[generate_source_refs_section]
    N8 --> N23
    N8 --> N28
    N9 --> N28
    N21 --> N26
    N19 --> N26
    N22 --> N26
    N20 --> N26
    N17 --> N29
    N16 --> N29
    N15 --> N29
    N13 --> N29
    N14 --> N29
    N18 --> N29
    N2 --> N23
    N2 --> N24
    N2 --> N27
    N5 --> N23
    N5 --> N24
    N5 --> N27
    N4 --> N23
    N4 --> N24
    N4 --> N27
    N3 --> N23
    N3 --> N27
    N1 --> N23
    N1 --> N24
    N1 --> N27
    N0 --> N23
    N0 --> N24
    N0 --> N27
    N12 --> N25
    N10 --> N25
    N11 --> N25
    N7 --> N23
    N7 --> N24
    N7 --> N27
    N6 --> N23
    N6 --> N24
    N6 --> N27
    classDef func fill:#e1f5fe
    class N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22 method
```

## Relevant Source Files

- `tests/test_source_refs.py:15-51`

## See Also

- [test_diagrams](test_diagrams.md) - shares 2 dependencies
