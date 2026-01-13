# File Overview

This file contains unit tests for the manifest parsing and caching functionality in the `local_deepwiki.generators.manifest` module. It tests the parsing of various manifest files (like `pyproject.toml`, `package.json`, `requirements.txt`, `go.mod`, etc.), the caching mechanism, and the handling of multiple manifest files in a project directory.

# Classes

## TestProjectManifest

Tests for the [ProjectManifest](../src/local_deepwiki/generators/manifest.md) dataclass.

### Methods

#### test_has_data_empty
Empty manifest has no data.

#### test_has_data_with_name
Manifest with name has data.

#### test_has_data_with_dependencies
Manifest with dependencies has data.

## TestParsePyprojectToml

Tests for parsing `pyproject.toml` files.

### Methods

#### test_parse_basic_pyproject
Parse a basic `pyproject.toml`.

## TestParsePackageJson

Tests for parsing `package.json` files.

### Methods

#### test_parse_basic_package_json
Parse a basic `package.json`.

## TestParseRequirementsTxt

Tests for parsing `requirements.txt` files.

### Methods

#### test_parse_basic_requirements
Parse a basic `requirements.txt`.

## TestParseCargoToml

Tests for parsing `Cargo.toml` files.

### Methods

#### test_parse_basic_cargo_toml
Parse a basic `Cargo.toml`.

## TestParseGoMod

Tests for parsing `go.mod` files.

### Methods

#### test_parse_basic_go_mod
Parse a basic `go.mod`.

## TestGetDirectoryTree

Tests for getting directory tree.

### Methods

#### test_get_directory_tree
Get directory tree.

## TestMultipleManifests

Tests for handling multiple manifest files.

### Methods

#### test_pyproject_takes_precedence
`pyproject.toml` takes precedence over `requirements.txt`.

## TestManifestCaching

Tests for manifest caching functionality.

### Methods

#### test_get_manifest_mtimes_empty_repo
Returns mtimes for existing manifest files.

#### test_get_manifest_mtimes_with_files
Returns mtimes for existing manifest files.

#### test_cache_entry_serialization
Cache entry can be serialized and deserialized.

#### test_cache_valid_when_unchanged
Cache is valid when no manifest files have changed.

#### test_cache_invalid_when_file_modified
Cache is invalid when a manifest file is modified.

#### test_cache_invalid_when_file_added
Cache is invalid when a new manifest file is added.

#### test_cache_invalid_when_file_removed
Cache is invalid when a manifest file is removed.

#### test_get_cached_manifest_creates_cache
[`get_cached_manifest`](../src/local_deepwiki/generators/manifest.md) creates cache file on first call.

#### test_get_cached_manifest_uses_cache
[`get_cached_manifest`](../src/local_deepwiki/generators/manifest.md) uses cache on subsequent calls.

#### test_get_cached_manifest_invalidates_on_change
[`get_cached_manifest`](../src/local_deepwiki/generators/manifest.md) re-parses when file changes.

#### test_get_cached_manifest_default_cache_dir
[`get_cached_manifest`](../src/local_deepwiki/generators/manifest.md) uses `.deepwiki` in repo by default.

# Functions

## _get_manifest_mtimes

Returns mtimes for existing manifest files.

### Parameters

- `root` (Path): The root directory to scan for manifest files.

### Returns

- `dict`: A dictionary mapping manifest file names to their modification times.

## _is_cache_valid

Checks if the cache is still valid based on file modification times.

### Parameters

- `entry` ([ManifestCacheEntry](../src/local_deepwiki/generators/manifest.md)): The cache entry to validate.
- `mtimes` (dict): Current modification times of manifest files.

### Returns

- `bool`: True if the cache is valid, False otherwise.

## get_cached_manifest

Retrieves a cached manifest or parses a new one if the cache is invalid.

### Parameters

- `root` (Path): The root directory to parse.
- `cache_dir` (Path, optional): The directory to use for caching. Defaults to `.deepwiki` in the root.

### Returns

- [`ProjectManifest`](../src/local_deepwiki/generators/manifest.md): The parsed or cached manifest.

## get_directory_tree

Generates a directory tree structure.

### Parameters

- `root` (Path): The root directory to scan.

### Returns

- `dict`: A dictionary representing the directory tree.

## parse_manifest

Parses manifest files in a directory and returns a [ProjectManifest](../src/local_deepwiki/generators/manifest.md).

### Parameters

- `root` (Path): The root directory to scan for manifest files.

### Returns

- [`ProjectManifest`](../src/local_deepwiki/generators/manifest.md): The parsed manifest.

# Usage Examples

## Parsing a Manifest

```python
from pathlib import Path
from local_deepwiki.generators.manifest import parse_manifest

manifest = parse_manifest(Path("/path/to/project"))
```

## Using Cached Manifest

```python
from pathlib import Path
from local_deepwiki.generators.manifest import get_cached_manifest

manifest = get_cached_manifest(Path("/path/to/project"), cache_dir=Path("/path/to/cache"))
```

## Getting Manifest Modification Times

```python
from pathlib import Path
from local_deepwiki.generators.manifest import _get_manifest_mtimes

mtimes = _get_manifest_mtimes(Path("/path/to/project"))
```

# Related Components

This file works with the following components from `local_deepwiki.generators.manifest`:

- [`ManifestCacheEntry`](../src/local_deepwiki/generators/manifest.md)
- [`ProjectManifest`](../src/local_deepwiki/generators/manifest.md)
- `_get_manifest_mtimes`
- `_is_cache_valid`
- [`get_cached_manifest`](../src/local_deepwiki/generators/manifest.md)
- [`get_directory_tree`](../src/local_deepwiki/generators/manifest.md)
- [`parse_manifest`](../src/local_deepwiki/generators/manifest.md)

## API Reference

### class `TestProjectManifest`

Tests for [ProjectManifest](../src/local_deepwiki/generators/manifest.md) dataclass.

**Methods:**

#### `test_has_data_empty`

```python
def test_has_data_empty()
```

Empty manifest has no data.

#### `test_has_data_with_name`

```python
def test_has_data_with_name()
```

Manifest with name has data.

#### `test_has_data_with_dependencies`

```python
def test_has_data_with_dependencies()
```

Manifest with dependencies has data.

#### `test_get_tech_stack_summary_empty`

```python
def test_get_tech_stack_summary_empty()
```

Empty manifest returns default message.

#### `test_get_tech_stack_summary_with_language`

```python
def test_get_tech_stack_summary_with_language()
```

Manifest with language shows it in summary.

#### `test_get_dependency_list_formatted`

```python
def test_get_dependency_list_formatted()
```

Dependencies are formatted correctly.


### class `TestParsePyprojectToml`

Tests for parsing pyproject.toml files.

**Methods:**

#### `test_parse_basic_pyproject`

```python
def test_parse_basic_pyproject()
```

Parse a basic pyproject.toml.


### class `TestParsePackageJson`

Tests for parsing package.json files.

**Methods:**

#### `test_parse_basic_package_json`

```python
def test_parse_basic_package_json()
```

Parse a basic package.json.


### class `TestParseRequirementsTxt`

Tests for parsing requirements.txt files.

**Methods:**

#### `test_parse_basic_requirements`

```python
def test_parse_basic_requirements()
```

Parse a basic requirements.txt.


### class `TestParseCargoToml`

Tests for parsing Cargo.toml files.

**Methods:**

#### `test_parse_basic_cargo`

```python
def test_parse_basic_cargo()
```

Parse a basic Cargo.toml.


### class `TestParseGoMod`

Tests for parsing go.mod files.

**Methods:**

#### `test_parse_basic_go_mod`

```python
def test_parse_basic_go_mod()
```

Parse a basic go.mod.


### class `TestGetDirectoryTree`

Tests for directory tree generation.

**Methods:**

#### `test_basic_tree`

```python
def test_basic_tree()
```

Generate a basic directory tree.

#### `test_skips_hidden_dirs`

```python
def test_skips_hidden_dirs()
```

Hidden directories are skipped.

#### `test_skips_node_modules`

```python
def test_skips_node_modules()
```

node_modules is skipped.

#### `test_respects_max_items`

```python
def test_respects_max_items()
```

Respects max_items limit.


### class `TestMultipleManifests`

Tests for handling multiple manifest files.

**Methods:**

#### `test_pyproject_takes_precedence`

```python
def test_pyproject_takes_precedence()
```

pyproject.toml takes precedence over requirements.txt.


### class `TestManifestCaching`

Tests for manifest caching functionality.

**Methods:**

#### `test_get_manifest_mtimes_empty_repo`

```python
def test_get_manifest_mtimes_empty_repo()
```

Empty repo returns no mtimes.

#### `test_get_manifest_mtimes_with_files`

```python
def test_get_manifest_mtimes_with_files()
```

Returns mtimes for existing manifest files.

#### `test_cache_entry_serialization`

```python
def test_cache_entry_serialization()
```

Cache entry can be serialized and deserialized.

#### `test_cache_valid_when_unchanged`

```python
def test_cache_valid_when_unchanged()
```

Cache is valid when files haven't changed.

#### `test_cache_invalid_when_file_modified`

```python
def test_cache_invalid_when_file_modified()
```

Cache is invalid when a file is modified.

#### `test_cache_invalid_when_file_added`

```python
def test_cache_invalid_when_file_added()
```

Cache is invalid when a new manifest file is added.

#### `test_cache_invalid_when_file_removed`

```python
def test_cache_invalid_when_file_removed()
```

Cache is invalid when a manifest file is removed.

#### `test_get_cached_manifest_creates_cache`

```python
def test_get_cached_manifest_creates_cache()
```

[get_cached_manifest](../src/local_deepwiki/generators/manifest.md) creates cache file on first call.

#### `test_get_cached_manifest_uses_cache`

```python
def test_get_cached_manifest_uses_cache()
```

[get_cached_manifest](../src/local_deepwiki/generators/manifest.md) uses cache on subsequent calls.

#### `test_get_cached_manifest_invalidates_on_change`

```python
def test_get_cached_manifest_invalidates_on_change()
```

[get_cached_manifest](../src/local_deepwiki/generators/manifest.md) re-parses when file changes.

#### `test_get_cached_manifest_default_cache_dir`

```python
def test_get_cached_manifest_default_cache_dir()
```

[get_cached_manifest](../src/local_deepwiki/generators/manifest.md) uses .deepwiki in repo by default.



## Class Diagram

```mermaid
classDiagram
    class TestGetDirectoryTree {
        +test_basic_tree()
        +test_skips_hidden_dirs()
        +test_skips_node_modules()
        +test_respects_max_items()
    }
    class TestManifestCaching {
        +test_get_manifest_mtimes_empty_repo()
        +test_get_manifest_mtimes_with_files()
        +test_cache_entry_serialization()
        +test_cache_valid_when_unchanged()
        +test_cache_invalid_when_file_modified()
        +test_cache_invalid_when_file_added()
        +test_cache_invalid_when_file_removed()
        +test_get_cached_manifest_creates_cache()
        +test_get_cached_manifest_uses_cache()
        +test_get_cached_manifest_invalidates_on_change()
        +test_get_cached_manifest_default_cache_dir()
    }
    class TestMultipleManifests {
        +test_pyproject_takes_precedence()
    }
    class TestParseCargoToml {
        +test_parse_basic_cargo()
    }
    class TestParseGoMod {
        +test_parse_basic_go_mod()
    }
    class TestParsePackageJson {
        +test_parse_basic_package_json()
    }
    class TestParsePyprojectToml {
        +test_parse_basic_pyproject()
    }
    class TestParseRequirementsTxt {
        +test_parse_basic_requirements()
    }
    class TestProjectManifest {
        +test_has_data_empty()
        +test_has_data_with_name()
        +test_has_data_with_dependencies()
        +test_get_tech_stack_summary_empty()
        +test_get_tech_stack_summary_with_language()
        +test_get_dependency_list_formatted()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[ManifestCacheEntry]
    N1[Path]
    N2[ProjectManifest]
    N3[TemporaryDirectory]
    N4[TestGetDirectoryTree.test_b...]
    N5[TestGetDirectoryTree.test_r...]
    N6[TestGetDirectoryTree.test_s...]
    N7[TestGetDirectoryTree.test_s...]
    N8[TestManifestCaching.test_ca...]
    N9[TestManifestCaching.test_ge...]
    N10[TestManifestCaching.test_ge...]
    N11[TestManifestCaching.test_ge...]
    N12[TestManifestCaching.test_ge...]
    N13[TestManifestCaching.test_ge...]
    N14[TestManifestCaching.test_ge...]
    N15[TestMultipleManifests.test_...]
    N16[TestParseCargoToml.test_par...]
    N17[TestParseGoMod.test_parse_b...]
    N18[TestParsePackageJson.test_p...]
    N19[TestParsePyprojectToml.test...]
    N20[TestParseRequirementsTxt.te...]
    N21[_is_cache_valid]
    N22[exists]
    N23[get_cached_manifest]
    N24[get_directory_tree]
    N25[has_data]
    N26[mkdir]
    N27[parse_manifest]
    N28[touch]
    N29[write_text]
    N19 --> N3
    N19 --> N1
    N19 --> N29
    N19 --> N27
    N18 --> N3
    N18 --> N1
    N18 --> N29
    N18 --> N27
    N20 --> N3
    N20 --> N1
    N20 --> N29
    N20 --> N27
    N16 --> N3
    N16 --> N1
    N16 --> N29
    N16 --> N27
    N17 --> N3
    N17 --> N1
    N17 --> N29
    N17 --> N27
    N4 --> N3
    N4 --> N1
    N4 --> N26
    N4 --> N28
    N4 --> N24
    N6 --> N3
    N6 --> N1
    N6 --> N26
    N6 --> N28
    N6 --> N24
    N7 --> N3
    N7 --> N1
    N7 --> N26
    N7 --> N24
    N5 --> N3
    N5 --> N1
    N5 --> N28
    N5 --> N24
    N15 --> N3
    N15 --> N1
    N15 --> N29
    N15 --> N27
    N13 --> N3
    N13 --> N1
    N14 --> N3
    N14 --> N1
    N14 --> N29
    N8 --> N0
    N9 --> N3
    N9 --> N1
    N9 --> N29
    N9 --> N23
    N9 --> N22
    N12 --> N3
    N12 --> N1
    N12 --> N29
    N12 --> N23
    N12 --> N22
    N11 --> N3
    N11 --> N1
    N11 --> N29
    N11 --> N23
    N10 --> N3
    N10 --> N1
    N10 --> N29
    N10 --> N23
    N10 --> N22
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20 method
```

## Relevant Source Files

- `tests/test_manifest.py:19-61`

## See Also

- [manifest](../src/local_deepwiki/generators/manifest.md) - dependency
- [test_indexer](test_indexer.md) - shares 3 dependencies
- [test_incremental_wiki](test_incremental_wiki.md) - shares 3 dependencies
