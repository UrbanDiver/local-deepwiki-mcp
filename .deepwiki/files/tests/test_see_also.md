# File: test_see_also.py

## File Overview

This test file contains unit tests for the `see_also` module, which is responsible for generating "See Also" sections in documentation pages. These sections list related files that either import or are imported by a given file, helping users navigate related code.

The tests validate the core functionality of:
- Analyzing file relationships (imports and importers)
- Mapping file paths to wiki page paths
- Generating See Also section content
- Adding See Also sections to wiki pages

This file works closely with the [`RelationshipAnalyzer`](../src/local_deepwiki/generators/see_also.md), [`FileRelationships`](../src/local_deepwiki/generators/see_also.md), and [`WikiPage`](../src/local_deepwiki/models.md) classes, as well as the [`CodeChunk`](../src/local_deepwiki/models.md) model to understand code structure and relationships.

## Classes

### TestRelationshipAnalyzer

Tests the [RelationshipAnalyzer](../src/local_deepwiki/generators/see_also.md) class, which analyzes code chunks to determine file import relationships.

**Key Methods:**
- `test_analyze_python_imports`: Tests analysis of Python import statements
- `test_get_relationships_imports`: Tests finding files that a given file imports
- `test_get_relationships_imported_by`: Tests finding files that import a given file
- `test_ignores_non_import_chunks`: Tests that non-import chunks are ignored
- `test_shared_dependencies`: Tests handling of shared dependencies

### TestBuildFileToWikiMap

Tests the [`build_file_to_wiki_map`](../src/local_deepwiki/generators/see_also.md) function which maps file paths to their corresponding wiki page paths.

**Key Methods:**
- `test_builds_correct_mapping`: Tests correct mapping of file paths to wiki paths

### TestGenerateSeeAlsoSection

Tests the [`generate_see_also_section`](../src/local_deepwiki/generators/see_also.md) function which creates the content for See Also sections.

**Key Methods:**
- `test_generates_section_with_importers`: Tests generating See Also section with files that import the current file

### TestRelativePath

Tests the `_relative_path` helper function which computes relative paths between wiki pages.

**Key Methods:**
- `test_same_directory`: Tests relative path in same directory
- `test_parent_directory`: Tests relative path to parent directory
- `test_sibling_directory`: Tests relative path to sibling directory

### TestAddSeeAlsoSections

Tests the [`add_see_also_sections`](../src/local_deepwiki/generators/see_also.md) function which adds See Also sections to wiki pages.

**Key Methods:**
- `test_adds_sections_to_file_pages`: Tests that See Also sections are added to file documentation pages

## Functions

### generate_see_also_section

Generates a "See Also" section for a file based on its import relationships.

**Parameters:**
- `relationships` ([FileRelationships](../src/local_deepwiki/generators/see_also.md)): The import relationships for the file
- `file_to_wiki` (dict): Mapping of file paths to wiki page paths
- `current_file` (str): The file path for which to generate the section

**Returns:**
- `str`: The formatted See Also section content

### add_see_also_sections

Adds See Also sections to wiki pages.

**Parameters:**
- `analyzer` ([RelationshipAnalyzer](../src/local_deepwiki/generators/see_also.md)): The analyzer to use for finding relationships
- `wiki_pages` (list): List of [WikiPage](../src/local_deepwiki/models.md) objects to process
- `chunker` ([CodeChunker](../src/local_deepwiki/core/chunker.md)): The code chunker to use for analyzing code

**Returns:**
- `list`: List of updated [WikiPage](../src/local_deepwiki/models.md) objects with See Also sections added

### build_file_to_wiki_map

Builds a mapping from file paths to wiki page paths.

**Parameters:**
- `wiki_pages` (list): List of [WikiPage](../src/local_deepwiki/models.md) objects

**Returns:**
- `dict`: Dictionary mapping file paths to wiki page paths

### _relative_path

Computes the relative path from one wiki page to another.

**Parameters:**
- `from_path` (str): Source wiki page path
- `to_path` (str): Target wiki page path

**Returns:**
- `str`: Relative path from source to target

## Usage Examples

### Analyzing File Relationships

```python
analyzer = RelationshipAnalyzer()
chunks = [
    CodeChunk(
        id="1",
        file_path="src/module/file1.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.IMPORT,
        content="from module.file2 import func",
        start_line=1,
        end_line=1,
    )
]
relationships = analyzer.analyze_python_imports(chunks)
```

### Generating See Also Section

```python
relationships = FileRelationships(
    file_path="src/module/file1.py",
    imported_by={"src/module/file2.py"}
)
file_to_wiki = {
    "src/module/file1.py": "files/src/module/file1.md",
    "src/module/file2.py": "files/src/module/file2.md"
}
section = generate_see_also_section(relationships, file_to_wiki, "src/module/file1.py")
```

### Adding See Also Sections to Pages

```python
analyzer = RelationshipAnalyzer()
wiki_pages = [
    WikiPage(
        path="files/src/module/file1.md",
        title="File1",
        content="# File1",
        generated_at=0
    )
]
updated_pages = add_see_also_sections(analyzer, wiki_pages, code_chunker)
```

## API Reference

### class `TestRelationshipAnalyzer`

Tests for [RelationshipAnalyzer](../src/local_deepwiki/generators/see_also.md) class.

**Methods:**

#### `test_analyze_python_imports`

```python
def test_analyze_python_imports()
```

Test analyzing Python import statements.

#### `test_get_relationships_imports`

```python
def test_get_relationships_imports()
```

Test getting import relationships for a file.

#### `test_get_relationships_imported_by`

```python
def test_get_relationships_imported_by()
```

Test finding files that import a given file.

#### `test_ignores_non_import_chunks`

```python
def test_ignores_non_import_chunks()
```

Test that non-import chunks are ignored.

#### `test_shared_dependencies`

```python
def test_shared_dependencies()
```

Test finding files with shared dependencies.


### class `TestBuildFileToWikiMap`

Tests for [build_file_to_wiki_map](../src/local_deepwiki/generators/see_also.md) function.

**Methods:**

#### `test_builds_correct_mapping`

```python
def test_builds_correct_mapping()
```

Test that file paths are correctly mapped to wiki paths.


### class `TestGenerateSeeAlsoSection`

Tests for [generate_see_also_section](../src/local_deepwiki/generators/see_also.md) function.

**Methods:**

#### `test_generates_section_with_importers`

```python
def test_generates_section_with_importers()
```

Test generating See Also with files that import this file.

#### `test_generates_section_with_dependencies`

```python
def test_generates_section_with_dependencies()
```

Test generating See Also with dependency files.

#### `test_returns_none_for_no_relationships`

```python
def test_returns_none_for_no_relationships()
```

Test that None is returned when no related pages exist.

#### `test_avoids_self_reference`

```python
def test_avoids_self_reference()
```

Test that See Also doesn't include the current page.


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


### class `TestAddSeeAlsoSections`

Tests for [add_see_also_sections](../src/local_deepwiki/generators/see_also.md) function.

**Methods:**

#### `test_adds_sections_to_file_pages`

```python
def test_adds_sections_to_file_pages()
```

Test that See Also sections are added to file documentation pages.

#### `test_skips_non_file_pages`

```python
def test_skips_non_file_pages()
```

Test that non-file pages are not modified.

#### `test_skips_files_index`

```python
def test_skips_files_index()
```

Test that files/index.md is not modified.



## Class Diagram

```mermaid
classDiagram
    class TestAddSeeAlsoSections {
        +test_adds_sections_to_file_pages()
        +test_skips_non_file_pages()
        +test_skips_files_index()
    }
    class TestBuildFileToWikiMap {
        +test_builds_correct_mapping()
    }
    class TestGenerateSeeAlsoSection {
        +test_generates_section_with_importers()
        +test_generates_section_with_dependencies()
        +test_returns_none_for_no_relationships()
        +test_avoids_self_reference()
    }
    class TestRelationshipAnalyzer {
        +test_analyze_python_imports()
        +test_get_relationships_imports()
        +test_get_relationships_imported_by()
        +test_ignores_non_import_chunks()
        +test_shared_dependencies()
    }
    class TestRelativePath {
        +test_same_directory()
        +test_parent_directory()
        +test_sibling_directory()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CodeChunk]
    N1[FileRelationships]
    N2[RelationshipAnalyzer]
    N3[TestAddSeeAlsoSections.test...]
    N4[TestAddSeeAlsoSections.test...]
    N5[TestAddSeeAlsoSections.test...]
    N6[TestBuildFileToWikiMap.test...]
    N7[TestGenerateSeeAlsoSection....]
    N8[TestGenerateSeeAlsoSection....]
    N9[TestGenerateSeeAlsoSection....]
    N10[TestGenerateSeeAlsoSection....]
    N11[TestRelationshipAnalyzer.te...]
    N12[TestRelationshipAnalyzer.te...]
    N13[TestRelationshipAnalyzer.te...]
    N14[TestRelationshipAnalyzer.te...]
    N15[TestRelationshipAnalyzer.te...]
    N16[TestRelativePath.test_paren...]
    N17[TestRelativePath.test_same_...]
    N18[TestRelativePath.test_sibli...]
    N19[WikiPage]
    N20[_relative_path]
    N21[add_see_also_sections]
    N22[analyze_chunks]
    N23[build_file_to_wiki_map]
    N24[generate_see_also_section]
    N25[get_all_known_files]
    N26[get_relationships]
    N11 --> N2
    N11 --> N0
    N11 --> N22
    N11 --> N25
    N13 --> N2
    N13 --> N0
    N13 --> N22
    N13 --> N26
    N12 --> N2
    N12 --> N0
    N12 --> N22
    N12 --> N26
    N14 --> N2
    N14 --> N0
    N14 --> N22
    N14 --> N25
    N15 --> N2
    N15 --> N0
    N15 --> N22
    N15 --> N26
    N6 --> N19
    N6 --> N23
    N9 --> N1
    N9 --> N24
    N8 --> N1
    N8 --> N24
    N10 --> N1
    N10 --> N24
    N7 --> N1
    N7 --> N24
    N17 --> N20
    N16 --> N20
    N18 --> N20
    N3 --> N2
    N3 --> N0
    N3 --> N22
    N3 --> N19
    N3 --> N21
    N5 --> N2
    N5 --> N19
    N5 --> N21
    N4 --> N2
    N4 --> N19
    N4 --> N21
    classDef func fill:#e1f5fe
    class N0,N1,N2,N19,N20,N21,N22,N23,N24,N25,N26 func
    classDef method fill:#fff3e0
    class N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18 method
```

## See Also

- [models](../src/local_deepwiki/models.md) - dependency
- [see_also](../src/local_deepwiki/generators/see_also.md) - dependency
- [test_chunker](test_chunker.md) - shares 2 dependencies
- [test_api_docs](test_api_docs.md) - shares 2 dependencies
