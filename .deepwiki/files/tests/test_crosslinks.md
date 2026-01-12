# File Overview

This file contains unit tests for the cross-linking functionality in the local_deepwiki documentation generator. It tests how entities are linked across wiki pages, including handling of code blocks, qualified names, and existing links.

# Classes

## TestCrossLinker

The TestCrossLinker class contains unit tests for the [CrossLinker](../src/local_deepwiki/generators/crosslinks.md) class functionality. It tests various scenarios for adding cross-links to wiki pages, including:

- Basic linking in prose text
- Handling of code blocks (no linking)
- Self-linking prevention
- Relative path calculation
- Linking of backticked entities
- Handling of non-entity inline code
- Qualified name linking (module.ClassName)
- Simple qualified name linking (module.Class)
- Preservation of existing links
- Bold text linking
- Spaced aliases linking
- Bold spaced aliases linking

### Methods

- `test_adds_links_to_prose`: Tests that links are added to prose text
- `test_does_not_link_in_code_blocks`: Tests that links are not added inside code blocks
- `test_does_not_self_link`: Tests that entities are not linked on their own page
- `test_relative_paths`: Tests relative path calculation between pages
- `test_links_backticked_entities`: Tests that backticked entity names get linked
- `test_does_not_link_non_entity_inline_code`: Tests that non-entity inline code is preserved unchanged
- `test_links_qualified_names`: Tests that qualified names like module.ClassName get linked
- `test_links_simple_qualified_names`: Tests that simple qualified names like module.Class get linked
- `test_preserves_existing_links`: Tests that existing markdown links are preserved
- `test_links_bold_text`: Tests that bold entity names get linked
- `test_links_spaced_aliases`: Tests that spaced aliases like '[Vector Store](../src/local_deepwiki/core/vectorstore.md)' get linked
- `test_links_bold_spaced_aliases`: Tests that bold spaced aliases get linked

## TestAddCrossLinks

The TestAddCrossLinks class contains tests for the [add_cross_links](../src/local_deepwiki/generators/crosslinks.md) function, which processes multiple wiki pages for cross-linking.

### Methods

- `test_processes_all_pages`: Tests that all pages are processed

# Functions

## add_cross_links

The [add_cross_links](../src/local_deepwiki/generators/crosslinks.md) function processes a list of WikiPage objects using a [CrossLinker](../src/local_deepwiki/generators/crosslinks.md) and [EntityRegistry](../src/local_deepwiki/generators/crosslinks.md) to add cross-links between entities.

### Parameters

- `pages` (list[WikiPage]): List of WikiPage objects to process
- `registry` ([EntityRegistry](../src/local_deepwiki/generators/crosslinks.md)): Entity registry containing entity information
- `linker` ([CrossLinker](../src/local_deepwiki/generators/crosslinks.md)): [CrossLinker](../src/local_deepwiki/generators/crosslinks.md) instance to use for linking

### Return Value

None (modifies pages in-place)

# Usage Examples

## Using CrossLinker

```python
from local_deepwiki.generators.crosslinks import CrossLinker, EntityRegistry
from local_deepwiki.models import ChunkType, WikiPage

registry = EntityRegistry()
registry.register_entity(
    name="VectorStore",
    entity_type=ChunkType.CLASS,
    wiki_path="files/vectorstore.md",
    file_path="vectorstore.py",
)

linker = CrossLinker(registry)
page = WikiPage(
    path="files/indexer.md",
    title="Indexer",
    content="The indexer uses VectorStore to store embeddings.",
    generated_at=0,
)

result = linker.add_links(page)
```

## Using add_cross_links function

```python
from local_deepwiki.generators.crosslinks import add_cross_links, EntityRegistry
from local_deepwiki.models import ChunkType, WikiPage

registry = EntityRegistry()
registry.register_entity(
    name="ClassA",
    entity_type=ChunkType.CLASS,
    wiki_path="files/a.md",
    file_path="a.py",
)

pages = [
    WikiPage(
        path="files/a.md",
        title="Class A",
        content="Description of Class A.",
        generated_at=0,
    ),
    WikiPage(
        path="files/b.md",
        title="Class B",
        content="Description of Class B.",
        generated_at=0,
    ),
]

add_cross_links(pages, registry)
```

# Related Components

This file works with the following components:

- [`CrossLinker`](../src/local_deepwiki/generators/crosslinks.md): Main class for adding cross-links to wiki pages
- [`EntityRegistry`](../src/local_deepwiki/generators/crosslinks.md): Registry for managing entity information
- `WikiPage`: Model representing a wiki page with content to be processed
- `ChunkType`: Enum defining types of code chunks (CLASS, FUNCTION, etc.)
- [`camel_to_spaced`](../src/local_deepwiki/generators/crosslinks.md): Helper function for converting camelCase to spaced names

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

Test that spaced aliases like '[Vector Store](../src/local_deepwiki/core/vectorstore.md)' get linked.

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

- `tests/test_crosslinks.py:12-42`

## See Also

- [crosslinks](../src/local_deepwiki/generators/crosslinks.md) - dependency
- [wiki](../src/local_deepwiki/generators/wiki.md) - shares 2 dependencies
