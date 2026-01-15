# test_crosslinks.py

## File Overview

This file contains comprehensive unit tests for the cross-linking functionality in the local_deepwiki system. It tests the ability to automatically create links between wiki pages by detecting entity references in markdown content and converting them to proper cross-references.

## Classes

### TestCrossLinker

The [main](../src/local_deepwiki/web/app.md) test class that validates the [CrossLinker](../src/local_deepwiki/generators/crosslinks.md) functionality for creating automatic cross-links between wiki pages.

**Key Test Methods:**

- `test_adds_links_to_prose` - Verifies that entity names in prose text are converted to markdown links
- `test_does_not_link_in_code_blocks` - Ensures entity names inside code blocks remain unchanged
- `test_does_not_self_link` - Prevents entities from being linked on their own page
- `test_relative_paths` - Tests proper relative path calculation between wiki pages
- `test_links_backticked_entities` - Verifies that backticked entity names get linked
- `test_does_not_link_non_entity_inline_code` - Ensures non-entity inline code is preserved
- `test_links_qualified_names` - Tests linking of qualified names like `module.ClassName`
- `test_links_simple_qualified_names` - Tests linking of simple qualified names
- `test_preserves_existing_links` - Ensures existing markdown links are not modified
- `test_links_bold_text` - Verifies that bold entity names get linked
- `test_links_spaced_aliases` - Tests linking of spaced aliases like "Vector Store"
- `test_links_bold_spaced_aliases` - Tests linking of bold spaced aliases

### TestAddCrossLinks

Tests the high-level [`add_cross_links`](../src/local_deepwiki/generators/crosslinks.md) function that processes multiple wiki pages.

**Key Test Methods:**

- `test_processes_all_pages` - Verifies that all provided pages are processed for cross-linking

## Test Structure

Each test follows a consistent pattern:

1. Creates an [EntityRegistry](../src/local_deepwiki/generators/crosslinks.md) and registers test entities
2. Instantiates a [CrossLinker](../src/local_deepwiki/generators/crosslinks.md) with the registry
3. Creates a WikiPage with test content
4. Calls the linking functionality
5. Asserts the expected output

## Usage Examples

### Basic Cross-Linking Test Setup

```python
# Create entity registry
registry = EntityRegistry()
registry.register_entity(
    name="VectorStore",
    entity_type=ChunkType.CLASS,
    wiki_path="files/vectorstore.md",
    file_path="vectorstore.py",
)

# Create cross-linker
linker = CrossLinker(registry)

# Create test page
page = WikiPage(
    path="files/indexer.md",
    title="Indexer",
    content="The indexer uses VectorStore to store embeddings.",
    generated_at=0,
)

# Test linking
result = linker.add_links(page)
```

### Testing Multiple Pages

```python
registry = EntityRegistry()
# Register multiple entities...

pages = [
    WikiPage(...),
    WikiPage(...),
]

# Process all pages
result_pages = add_cross_links(pages, registry)
```

## Related Components

This test file works with several components from the local_deepwiki system:

- **[CrossLinker](../src/local_deepwiki/generators/crosslinks.md)** - The [main](../src/local_deepwiki/web/app.md) class for adding cross-links to wiki pages
- **[EntityRegistry](../src/local_deepwiki/generators/crosslinks.md)** - Manages registered entities that can be linked
- **WikiPage** - Represents a wiki page with content and metadata
- **ChunkType** - Enumeration for different types of code entities
- **CodeChunk** - Represents code elements that can be linked
- **Language** - Enumeration for programming languages

The tests also use the [`camel_to_spaced`](../src/local_deepwiki/generators/crosslinks.md) utility function for converting CamelCase names to spaced aliases.

## Test Coverage

The tests comprehensively cover:

- Basic linking functionality in prose text
- Preservation of code blocks and existing links
- Self-linking prevention
- Various text formatting scenarios (bold, backticks, qualified names)
- Relative path calculation between pages
- Batch processing of multiple pages

## API Reference

### class `TestCamelToSpaced`

Tests for [camel_to_spaced](../src/local_deepwiki/generators/crosslinks.md) function.

**Methods:**

#### `test_simple_camel_case`

```python
def test_simple_camel_case()
```

Test simple CamelCase conversion.

#### `test_multi_word`

```python
def test_multi_word()
```

Test multi-word CamelCase.

#### `test_acronyms`

```python
def test_acronyms()
```

Test CamelCase with acronyms.

#### `test_returns_none_for_invalid`

```python
def test_returns_none_for_invalid()
```

Test that None is returned for non-CamelCase names.

#### `test_already_single_word`

```python
def test_already_single_word()
```

Test single capitalized word returns None.


### class `TestEntityRegistry`

Tests for [EntityRegistry](../src/local_deepwiki/generators/crosslinks.md) class.

**Methods:**

#### `test_register_entity`

```python
def test_register_entity()
```

Test registering an entity.

#### `test_skips_short_names`

```python
def test_skips_short_names()
```

Test that short names are not registered.

#### `test_skips_private_names`

```python
def test_skips_private_names()
```

Test that private names are not registered.

#### `test_skips_excluded_names`

```python
def test_skips_excluded_names()
```

Test that excluded common names are not registered.

#### `test_register_from_chunks`

```python
def test_register_from_chunks()
```

Test registering entities from code chunks.

#### `test_get_page_entities`

```python
def test_get_page_entities()
```

Test getting entities defined in a page.

#### `test_registers_camelcase_aliases`

```python
def test_registers_camelcase_aliases()
```

Test that CamelCase names get spaced aliases registered.

#### `test_alias_lookup`

```python
def test_alias_lookup()
```

Test looking up entities by alias.


### class `TestCrossLinker`

Tests for [CrossLinker](../src/local_deepwiki/generators/crosslinks.md) class.

**Methods:**

#### `test_adds_links_to_prose`

```python
def test_adds_links_to_prose()
```

Test that links are added to prose text.

#### `test_does_not_link_in_code_blocks`

```python
def test_does_not_link_in_code_blocks()
```

Test that links are not added inside code blocks.

#### `test_does_not_self_link`

```python
def test_does_not_self_link()
```

Test that entities are not linked on their own page.

#### `test_relative_paths`

```python
def test_relative_paths()
```

Test relative path calculation between pages.

#### `test_links_backticked_entities`

```python
def test_links_backticked_entities()
```

Test that backticked entity names get linked.

#### `test_does_not_link_non_entity_inline_code`

```python
def test_does_not_link_non_entity_inline_code()
```

Test that non-entity inline code is preserved unchanged.

#### `test_links_qualified_names`

```python
def test_links_qualified_names()
```

Test that qualified names like module.ClassName get linked.

#### `test_links_simple_qualified_names`

```python
def test_links_simple_qualified_names()
```

Test that simple qualified names like module.Class get linked.

#### `test_preserves_existing_links`

```python
def test_preserves_existing_links()
```

Test that existing markdown links are preserved.

#### `test_links_bold_text`

```python
def test_links_bold_text()
```

Test that bold entity names get linked.

#### `test_links_spaced_aliases`

```python
def test_links_spaced_aliases()
```

Test that spaced aliases like 'Vector Store' get linked.

#### `test_links_bold_spaced_aliases`

```python
def test_links_bold_spaced_aliases()
```

Test that bold spaced aliases get linked.


### class `TestAddCrossLinks`

Tests for [add_cross_links](../src/local_deepwiki/generators/crosslinks.md) function.

**Methods:**

#### `test_processes_all_pages`

```python
def test_processes_all_pages()
```

Test that all pages are processed.



## Class Diagram

```mermaid
classDiagram
    class TestAddCrossLinks {
        +test_processes_all_pages()
    }
    class TestCamelToSpaced {
        +test_simple_camel_case()
        +test_multi_word()
        +test_acronyms()
        +test_returns_none_for_invalid()
        +test_already_single_word()
    }
    class TestCrossLinker {
        +test_adds_links_to_prose()
        +test_does_not_link_in_code_blocks()
        +test_does_not_self_link()
        +test_relative_paths()
        +test_links_backticked_entities()
        +test_does_not_link_non_entity_inline_code()
        +test_links_qualified_names()
        +test_links_simple_qualified_names()
        +test_preserves_existing_links()
        +test_links_bold_text()
        +test_links_spaced_aliases()
        +test_links_bold_spaced_aliases()
    }
    class TestEntityRegistry {
        +test_register_entity()
        +test_skips_short_names()
        +test_skips_private_names()
        +test_skips_excluded_names()
        +test_register_from_chunks()
        +test_get_page_entities()
        +test_registers_camelcase_aliases()
        +test_alias_lookup()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CrossLinker]
    N1[EntityRegistry]
    N2[TestAddCrossLinks.test_proc...]
    N3[TestCamelToSpaced.test_mult...]
    N4[TestCamelToSpaced.test_simp...]
    N5[TestCrossLinker.test_adds_l...]
    N6[TestCrossLinker.test_does_n...]
    N7[TestCrossLinker.test_does_n...]
    N8[TestCrossLinker.test_does_n...]
    N9[TestCrossLinker.test_links_...]
    N10[TestCrossLinker.test_links_...]
    N11[TestCrossLinker.test_links_...]
    N12[TestCrossLinker.test_links_...]
    N13[TestCrossLinker.test_links_...]
    N14[TestCrossLinker.test_links_...]
    N15[TestCrossLinker.test_preser...]
    N16[TestCrossLinker.test_relati...]
    N17[TestEntityRegistry.test_ali...]
    N18[TestEntityRegistry.test_get...]
    N19[TestEntityRegistry.test_reg...]
    N20[TestEntityRegistry.test_reg...]
    N21[TestEntityRegistry.test_reg...]
    N22[TestEntityRegistry.test_ski...]
    N23[TestEntityRegistry.test_ski...]
    N24[TestEntityRegistry.test_ski...]
    N25[WikiPage]
    N26[add_links]
    N27[camel_to_spaced]
    N28[get_entity]
    N29[register_entity]
    N4 --> N27
    N3 --> N27
    N19 --> N1
    N19 --> N29
    N19 --> N28
    N24 --> N1
    N24 --> N29
    N24 --> N28
    N23 --> N1
    N23 --> N29
    N23 --> N28
    N22 --> N1
    N22 --> N29
    N22 --> N28
    N20 --> N1
    N20 --> N28
    N18 --> N1
    N18 --> N29
    N21 --> N1
    N21 --> N29
    N17 --> N1
    N17 --> N29
    N5 --> N1
    N5 --> N29
    N5 --> N0
    N5 --> N25
    N5 --> N26
    N6 --> N1
    N6 --> N29
    N6 --> N0
    N6 --> N25
    N6 --> N26
    N8 --> N1
    N8 --> N29
    N8 --> N0
    N8 --> N25
    N8 --> N26
    N16 --> N1
    N16 --> N29
    N16 --> N0
    N16 --> N25
    N16 --> N26
    N9 --> N1
    N9 --> N29
    N9 --> N0
    N9 --> N25
    N9 --> N26
    N7 --> N1
    N7 --> N29
    N7 --> N0
    N7 --> N25
    N7 --> N26
    N12 --> N1
    N12 --> N29
    N12 --> N0
    N12 --> N25
    N12 --> N26
    N13 --> N1
    N13 --> N29
    N13 --> N0
    N13 --> N25
    N13 --> N26
    N15 --> N1
    N15 --> N29
    N15 --> N0
    N15 --> N25
    N15 --> N26
    N11 --> N1
    N11 --> N29
    N11 --> N0
    N11 --> N25
    N11 --> N26
    N14 --> N1
    N14 --> N29
    N14 --> N0
    N14 --> N25
    N14 --> N26
    N10 --> N1
    N10 --> N29
    N10 --> N0
    N10 --> N25
    N10 --> N26
    N2 --> N1
    N2 --> N29
    N2 --> N25
    classDef func fill:#e1f5fe
    class N0,N1,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24 method
```

## Relevant Source Files

- [`tests/test_crosslinks.py:12-42`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_crosslinks.py#L12-L42)

## See Also

- [crosslinks](../src/local_deepwiki/generators/crosslinks.md) - dependency
