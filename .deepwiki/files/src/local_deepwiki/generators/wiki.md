# Wiki Generator Documentation

## File Overview

This file defines the `WikiGenerator` class and the `generate_wiki` function, which are responsible for generating wiki documentation from a codebase. It uses a vector store for code indexing and integrates with various code analysis tools to produce structured documentation including module overviews, architecture diagrams, and cross-referenced pages.

## Classes

### WikiGenerator

The WikiGenerator class is responsible for generating wiki documentation from a codebase using a vector store and configuration.

#### Constructor

```python
def __init__(
    self,
    wiki_path: Path,
    vector_store: VectorStore,
    config: Config | None = None,
    llm_provider_name: str | None = None,
)
```

Initialize the wiki generator.

**Parameters:**
- `wiki_path`: Path to wiki output directory.
- `vector_store`: Vector store with indexed code.
- `config`: Optional configuration.
- `llm_provider_name`: Override LLM provider ("ollama", "anthropic", "openai").

## Functions

### generate_wiki

```python
async def generate_wiki(
    repo_path: Path,
    wiki_path: Path,
    vector_store: VectorStore,
    index_status: IndexStatus,
    config: Config | None = None,
    llm_provider: str | None = None,
    progress_callback: Any = None,
    full_rebuild: bool = False,
) -> WikiStructure:
```

Convenience function to generate wiki documentation.

**Parameters:**
- `repo_path`: Path to the repository.
- `wiki_path`: Path for wiki output.
- `vector_store`: Indexed vector store.
- `index_status`: Index status.
- `config`: Optional configuration.
- `llm_provider`: Optional LLM provider name.
- [`progress_callback`](../server.md): Optional callback for progress updates.
- `full_rebuild`: Whether to perform a full rebuild.

**Returns:**
- `WikiStructure`: The generated wiki structure.

## Usage Examples

### Using WikiGenerator

```python
from pathlib import Path
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.config import Config
from local_deepwiki.generators.wiki import WikiGenerator

# Initialize components
wiki_path = Path("output/wiki")
vector_store = VectorStore()
config = Config()

# Create generator
generator = WikiGenerator(
    wiki_path=wiki_path,
    vector_store=vector_store,
    config=config
)

# Generate wiki (example usage)
# generator.generate()
```

### Using generate_wiki

```python
from pathlib import Path
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.config import Config
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.core.index_status import IndexStatus

# Setup paths and components
repo_path = Path("path/to/repo")
wiki_path = Path("output/wiki")
vector_store = VectorStore()
index_status = IndexStatus()

# Generate wiki
# wiki_structure = await generate_wiki(
#     repo_path=repo_path,
#     wiki_path=wiki_path,
#     vector_store=vector_store,
#     index_status=index_status,
#     config=Config(),
#     llm_provider="openai"
# )
```

## Related Components

This file works with the following components:

- [`VectorStore`](../core/vectorstore.md): Used for code indexing and retrieval.
- [`Config`](../config.md): Configuration settings for the wiki generation.
- `IndexStatus`: Tracks the status of code indexing.
- [`EntityRegistry`](crosslinks.md) and [`add_cross_links`](crosslinks.md): For managing and adding cross-references.
- [`get_file_api_docs`](api_docs.md), `get_file_call_graph`: For generating API documentation and call graphs.
- [`generate_class_diagram`](diagrams.md), [`generate_dependency_graph`](diagrams.md), [`generate_language_pie_chart`](diagrams.md), [`generate_module_overview`](diagrams.md): For generating various diagrams and overviews.
- `WikiStructure`: The structure of the generated wiki.

## API Reference

### class `WikiGenerator`

Generate wiki documentation from indexed code.

**Methods:**

#### `__init__`

```python
def __init__(wiki_path: Path, vector_store: VectorStore, config: Config | None = None, llm_provider_name: str | None = None)
```

Initialize the wiki generator.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | Path to wiki output directory. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Vector store with indexed code. |
| `config` | `Config | None` | `None` | Optional configuration. |
| `llm_provider_name` | `str | None` | `None` | Override LLM provider ("ollama", "anthropic", "openai"). |

#### `generate`

```python
async def generate(index_status: IndexStatus, progress_callback: Any = None, full_rebuild: bool = False) -> WikiStructure
```

Generate wiki documentation for the indexed repository.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | `IndexStatus` | - | The index status with file information. |
| [`progress_callback`](../server.md) | `Any` | `None` | Optional progress callback. |
| `full_rebuild` | `bool` | `False` | If True, regenerate all pages. Otherwise, only regenerate changed pages. |


---

### Functions

#### `generate_wiki`

```python
async def generate_wiki(repo_path: Path, wiki_path: Path, vector_store: VectorStore, index_status: IndexStatus, config: Config | None = None, llm_provider: str | None = None, progress_callback: Any = None, full_rebuild: bool = False) -> WikiStructure
```

Convenience function to generate wiki documentation.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path` | - | Path to the repository. |
| `wiki_path` | `Path` | - | Path for wiki output. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Indexed vector store. |
| `index_status` | `IndexStatus` | - | Index status. |
| `config` | `Config | None` | `None` | Optional configuration. |
| `llm_provider` | `str | None` | `None` | Optional LLM provider override. |
| [`progress_callback`](../server.md) | `Any` | `None` | Optional progress callback. |
| `full_rebuild` | `bool` | `False` | If True, regenerate all pages. Otherwise, only regenerate changed pages. |

**Returns:** `WikiStructure`



## Class Diagram

```mermaid
classDiagram
    class WikiGenerator {
        -__init__()
        -_get_main_definition_lines()
        -_load_wiki_status()
        -_save_wiki_status()
        -_compute_content_hash()
        -_needs_regeneration()
        -_load_existing_page()
        -_record_page_status()
        +generate()
        -_generate_overview()
        -_generate_architecture()
        -_generate_module_docs()
        -_generate_modules_index()
        -_generate_file_docs()
        -_generate_files_index()
        -_generate_dependencies()
        -_write_page()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[WikiGenerator.__init__]
    N2[WikiGenerator._compute_cont...]
    N3[WikiGenerator._generate_arc...]
    N4[WikiGenerator._generate_dep...]
    N5[WikiGenerator._generate_fil...]
    N6[WikiGenerator._generate_mod...]
    N7[WikiGenerator._generate_ove...]
    N8[WikiGenerator._get_main_def...]
    N9[WikiGenerator._load_existin...]
    N10[WikiGenerator._load_wiki_st...]
    N11[WikiGenerator._record_page_...]
    N12[WikiGenerator._save_wiki_st...]
    N13[WikiGenerator.generate]
    N14[WikiPage]
    N15[_load_existing_page]
    N16[_needs_regeneration]
    N17[_record_page_status]
    N18[add]
    N19[encode]
    N20[exists]
    N21[generate]
    N22[generate_wiki]
    N23[get_directory_tree]
    N24[hexdigest]
    N25[model_dump]
    N26[search]
    N27[setdefault]
    N28[sha256]
    N29[time]
    N22 --> N21
    N10 --> N20
    N12 --> N25
    N2 --> N24
    N2 --> N28
    N2 --> N19
    N9 --> N20
    N9 --> N0
    N9 --> N29
    N9 --> N14
    N13 --> N0
    N13 --> N16
    N13 --> N15
    N13 --> N17
    N13 --> N26
    N13 --> N29
    N13 --> N24
    N13 --> N28
    N13 --> N19
    N13 --> N25
    N7 --> N0
    N7 --> N26
    N7 --> N18
    N7 --> N23
    N7 --> N21
    N7 --> N14
    N7 --> N29
    N3 --> N26
    N3 --> N18
    N3 --> N23
    N3 --> N21
    N3 --> N14
    N3 --> N29
    N6 --> N0
    N6 --> N27
    N6 --> N16
    N6 --> N15
    N6 --> N17
    N6 --> N26
    N6 --> N21
    N6 --> N14
    N6 --> N29
    N5 --> N0
    N5 --> N16
    N5 --> N15
    N5 --> N17
    N5 --> N26
    N5 --> N21
    N5 --> N20
    N5 --> N14
    N5 --> N29
    N4 --> N26
    N4 --> N21
    N4 --> N14
    N4 --> N29
    classDef func fill:#e1f5fe
    class N0,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13 method
```

## Relevant Source Files

- `src/local_deepwiki/generators/wiki.py:59-1131`

## See Also

- [test_incremental_wiki](../../../tests/test_incremental_wiki.md) - uses this
- [server](../server.md) - uses this
- [see_also](see_also.md) - dependency
- [vectorstore](../core/vectorstore.md) - dependency
- [crosslinks](crosslinks.md) - dependency
