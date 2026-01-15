# WikiGenerator Module

## File Overview

The `wiki.py` module contains the core WikiGenerator class responsible for generating comprehensive documentation wikis from codebases. It orchestrates the creation of various documentation pages including module documentation, architecture overviews, dependency analysis, and cross-referenced API documentation.

## Classes

### WikiGenerator

The WikiGenerator class is the [main](../export/pdf.md) component for generating wiki documentation from indexed code. It manages the entire documentation generation process, including status tracking, content caching, and coordinated generation of multiple documentation types.

#### Constructor

```python
def __init__(
    self,
    wiki_path: Path,
    vector_store: VectorStore,
    config: Config | None = None,
    llm_provider_name: str | None = None,
):
```

**Parameters:**
- `wiki_path`: Path to wiki output directory
- `vector_store`: Vector store with indexed code
- `config`: Optional configuration object
- `llm_provider_name`: Override LLM provider ("ollama", "anthropic", "openai")

#### Key Methods

**Content Management:**
- `_compute_content_hash`: Computes hash for content change detection
- `_needs_regeneration`: Determines if a page needs to be regenerated
- `_load_existing_page`: Loads existing wiki page content
- `_record_page_status`: Records generation status for a page

**Status Tracking:**
- `_load_wiki_status`: Loads wiki generation status from disk
- `_save_wiki_status`: Saves wiki generation status to disk
- `_read_status`: Reads status from file
- `_write_status`: Writes status to file

**Generation Methods:**
- `generate`: Main entry point for wiki generation
- `_generate_overview`: Generates project overview documentation
- `_generate_architecture`: Generates architecture documentation
- `_generate_module_docs`: Generates module-specific documentation
- `_generate_single_file_doc`: Generates documentation for a single file
- `_generate_file_docs`: Generates documentation for multiple files
- `_generate_modules_index`: Generates index of all modules
- `_generate_files_index`: Generates index of all files
- `_generate_dependencies`: Generates dependency analysis
- `_generate_changelog`: Generates changelog documentation

**Utility Methods:**
- `is_test_file`: Determines if a file is a test file
- `generate_with_semaphore`: Manages concurrent generation with semaphore
- `_write_page`: Writes generated content to wiki page
- `_sync_write`: Synchronous write operation
- `_get_main_definition_lines`: Extracts [main](../export/pdf.md) definition lines from code

## Functions

### generate_wiki

```python
def generate_wiki(
    source_dir: Path,
    wiki_path: Path,
    config: Config | None = None,
    llm_provider_name: str | None = None,
) -> None:
```

Main function for generating a complete wiki from a source directory.

**Parameters:**
- `source_dir`: Source code directory to document
- `wiki_path`: Output directory for wiki files
- `config`: Optional configuration object
- `llm_provider_name`: Override for LLM provider selection

## Usage Examples

### Basic Wiki Generation

```python
from pathlib import Path
from local_deepwiki.generators.wiki import generate_wiki

# Generate wiki for a project
source_dir = Path("./my_project")
wiki_output = Path("./docs/wiki")
generate_wiki(source_dir, wiki_output)
```

### Using WikiGenerator Directly

```python
from pathlib import Path
from local_deepwiki.generators.wiki import WikiGenerator
from local_deepwiki.core.vectorstore import VectorStore

# Initialize components
wiki_path = Path("./docs")
vector_store = VectorStore()  # Assume properly initialized
generator = WikiGenerator(wiki_path, vector_store)

# Generate wiki
asyncio.run(generator.generate())
```

### Custom LLM Provider

```python
# Use specific LLM provider
generate_wiki(
    source_dir=Path("./src"),
    wiki_path=Path("./wiki"),
    llm_provider_name="anthropic"
)
```

## Related Components

The WikiGenerator class integrates with several other components from the codebase:

- **[VectorStore](../core/vectorstore.md)**: Provides indexed code content for documentation generation
- **[Config](../config.md)**: Supplies configuration settings for generation behavior
- **[EntityRegistry](crosslinks.md)**: Manages cross-linking between documentation entities
- **API Documentation Generator**: Generates API documentation via [`get_file_api_docs`](api_docs.md)
- **Call Graph Generator**: Creates call graphs via [`get_file_call_graph`](callgraph.md)
- **Test Examples Generator**: Extracts test examples via [`get_file_examples`](test_examples.md)
- **Diagram Generator**: Creates class diagrams via [`generate_class_diagram`](diagrams.md)
- **Cross-linking System**: Adds cross-references via [`add_cross_links`](crosslinks.md)

The module uses asynchronous operations for efficient concurrent generation and includes comprehensive status tracking to avoid unnecessary regeneration of unchanged content.

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
async def generate(index_status: IndexStatus, progress_callback: ProgressCallback | None = None, full_rebuild: bool = False) -> WikiStructure
```

Generate wiki documentation for the indexed repository.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | [`IndexStatus`](../models.md) | - | The index status with file information. |
| [`progress_callback`](../watcher.md) | `ProgressCallback | None` | `None` | Optional progress callback. |
| `full_rebuild` | `bool` | `False` | If True, regenerate all pages. Otherwise, only regenerate changed pages. |

#### `is_test_file`

```python
def is_test_file(path: str) -> bool
```

Check if a file is a test file.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | - | - |

#### `generate_with_semaphore`

```python
async def generate_with_semaphore(file_info: FileInfo) -> tuple[WikiPage | None, bool]
```


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_info` | [`FileInfo`](../models.md) | - | - |


---

### Functions

#### `generate_wiki`

```python
async def generate_wiki(repo_path: Path, wiki_path: Path, vector_store: VectorStore, index_status: IndexStatus, config: Config | None = None, llm_provider: str | None = None, progress_callback: ProgressCallback | None = None, full_rebuild: bool = False) -> WikiStructure
```

Convenience function to generate wiki documentation.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path` | - | Path to the repository. |
| `wiki_path` | `Path` | - | Path for wiki output. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Indexed vector store. |
| `index_status` | [`IndexStatus`](../models.md) | - | Index status. |
| `config` | `Config | None` | `None` | Optional configuration. |
| `llm_provider` | `str | None` | `None` | Optional LLM provider override. |
| [`progress_callback`](../watcher.md) | `ProgressCallback | None` | `None` | Optional progress callback. |
| `full_rebuild` | `bool` | `False` | If True, regenerate all pages. Otherwise, only regenerate changed pages. |

**Returns:** [`WikiStructure`](../models.md)



## Class Diagram

```mermaid
classDiagram
    class WikiGenerator {
        -__init__(wiki_path: Path, vector_store: VectorStore, config: Config | None, llm_provider_name: str | None)
        -_get_main_definition_lines() dict[str, tuple[int, int]]
        -_load_wiki_status() WikiGenerationStatus | None
        -_read_status() WikiGenerationStatus | None
        -_save_wiki_status(status: WikiGenerationStatus) None
        -_write_status() None
        -_compute_content_hash(content: str) str
        -_needs_regeneration(page_path: str, source_files: list[str]) bool
        -_load_existing_page(page_path: str) WikiPage | None
        -_read_page() WikiPage | None
        -_record_page_status(page: WikiPage, source_files: list[str]) None
        +generate(index_status: IndexStatus, progress_callback: ProgressCallback | None, full_rebuild: bool) WikiStructure
        -_generate_overview(index_status: IndexStatus) WikiPage
        -_generate_architecture(index_status: IndexStatus) WikiPage
        -_generate_module_docs(index_status: IndexStatus, full_rebuild: bool) tuple[list[WikiPage], int, int]
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[WikiGenerator.__init__]
    N2[WikiGenerator._compute_cont...]
    N3[WikiGenerator._generate_fil...]
    N4[WikiGenerator._generate_mod...]
    N5[WikiGenerator._generate_sin...]
    N6[WikiGenerator._get_main_def...]
    N7[WikiGenerator._load_existin...]
    N8[WikiGenerator._load_wiki_st...]
    N9[WikiGenerator._read_status]
    N10[WikiGenerator._save_wiki_st...]
    N11[WikiGenerator._write_page]
    N12[WikiGenerator.generate]
    N13[WikiPage]
    N14[_load_existing_page]
    N15[_needs_regeneration]
    N16[_record_page_status]
    N17[dump]
    N18[exists]
    N19[generate]
    N20[generate_wiki]
    N21[get_config]
    N22[hexdigest]
    N23[load]
    N24[model_dump]
    N25[model_validate]
    N26[search]
    N27[sha256]
    N28[time]
    N29[to_thread]
    N20 --> N21
    N20 --> N19
    N1 --> N21
    N8 --> N18
    N8 --> N23
    N8 --> N25
    N8 --> N29
    N9 --> N23
    N9 --> N25
    N10 --> N24
    N10 --> N17
    N10 --> N29
    N2 --> N22
    N2 --> N27
    N7 --> N18
    N7 --> N0
    N7 --> N28
    N7 --> N13
    N7 --> N29
    N12 --> N0
    N12 --> N15
    N12 --> N14
    N12 --> N16
    N12 --> N26
    N12 --> N28
    N12 --> N22
    N12 --> N27
    N12 --> N24
    N4 --> N0
    N4 --> N15
    N4 --> N14
    N4 --> N16
    N4 --> N26
    N4 --> N19
    N4 --> N13
    N4 --> N28
    N5 --> N0
    N5 --> N15
    N5 --> N14
    N5 --> N16
    N5 --> N26
    N5 --> N19
    N5 --> N18
    N5 --> N13
    N5 --> N28
    N3 --> N13
    N3 --> N28
    N3 --> N16
    N11 --> N29
    classDef func fill:#e1f5fe
    class N0,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12 method
```

## Relevant Source Files

- `src/local_deepwiki/generators/wiki.py:65-963`
