# Wiki Generator Documentation

The `wiki.py` module provides functionality to generate comprehensive wiki documentation for code repositories using vector search and LLMs.

## Overview

The `WikiGenerator` class orchestrates the generation of wiki documentation by:
1. Analyzing code structure from an indexed repository
2. Using vector search to retrieve relevant code context
3. Generating documentation using LLMs
4. Writing structured markdown pages to disk

## Classes

### `WikiGenerator`

Main class for generating wiki documentation.

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

**Parameters:**
- `wiki_path`: Path to wiki output directory
- `vector_store`: Vector store with indexed code
- `config`: Optional configuration
- `llm_provider_name`: Override LLM provider ("ollama", "anthropic", "openai")

#### Methods

##### `generate(index_status, progress_callback)`

Generate wiki documentation for the indexed repository.

**Parameters:**
- `index_status`: The index status with file information
- `progress_callback`: Optional progress callback

**Returns:**
- `WikiStructure` with generated pages

##### `_generate_overview(index_status)`

Generate overview documentation.

##### `_generate_architecture(index_status)`

Generate architecture documentation with diagrams.

##### `_generate_module_docs(index_status)`

Generate documentation for each module/directory.

##### `_generate_modules_index(module_pages)`

Generate index page for modules.

##### `_generate_file_docs(index_status, progress_callback)`

Generate documentation for individual source files.

##### `_generate_files_index(file_pages)`

Generate index page for file documentation.

##### `_generate_dependencies(index_status)`

Generate dependencies documentation.

##### `_write_page(page)`

Write a wiki page to disk.

## Functions

### `generate_wiki(repo_path, wiki_path, vector_store, index_status, config, llm_provider, progress_callback)`

Convenience function to generate wiki documentation.

**Parameters:**
- `repo_path`: Path to the repository
- `wiki_path`: Path for wiki output
- `vector_store`: Indexed vector store
- `index_status`: Index status
- `config`: Optional configuration
- `llm_provider`: Optional LLM provider override
- `progress_callback`: Optional progress callback

**Returns:**
- `WikiStructure` with generated pages

## Usage Example

```python
from pathlib import Path
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.models import IndexStatus

# Assuming you have an indexed vector store and index status
wiki_path = Path("./wiki_output")
vector_store = VectorStore()
index_status = IndexStatus()

# Generate wiki documentation
wiki_structure = await generate_wiki(
    repo_path=Path("./my_repo"),
    wiki_path=wiki_path,
    vector_store=vector_store,
    index_status=index_status,
    llm_provider="openai"
)
```