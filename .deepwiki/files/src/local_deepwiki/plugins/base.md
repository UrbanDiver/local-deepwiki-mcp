# File: `src/local_deepwiki/plugins/base.py`

## File Overview

This file defines the foundational base classes for plugins within the `local-deepwiki` system. It provides a standardized interface for extending the functionality of the tool through plugins, enabling support for new programming languages, custom wiki generators, and embedding providers.

The purpose of this file is to enforce a consistent structure for plugin development while allowing extensibility. By defining abstract base classes, it ensures that all plugins implement required methods and properties, facilitating integration into the core system.

## Key Concepts

### Plugin Architecture

The plugin architecture is built around several key abstractions:
- `PluginMetadata`: Provides metadata about a plugin such as name, version, and dependencies.
- `Plugin`: The base class for all plugins, defining lifecycle methods (`initialize`, `cleanup`) and requiring a `metadata` property.
- `LanguageParserPlugin`: Extends `Plugin` to add support for parsing source code in new programming languages.
- `WikiGeneratorPlugin`: Allows adding custom wiki page generation logic.
- `EmbeddingProviderPlugin`: Enables integration of external embedding services.

These abstractions are designed to be extensible and modular, allowing developers to plug in new functionality without modifying core logic.

### Abstract Base Classes and Inheritance

The use of `ABC` (Abstract Base Classes) and `@abstractmethod` ensures that subclasses implement necessary interfaces. This design choice promotes correctness by preventing incomplete implementations and encourages a clear separation of concerns.

For example, `LanguageParserPlugin` requires subclasses to implement `language_name`, `file_extensions`, and `parse_file`. Similarly, `WikiGeneratorPlugin` requires `generator_name` and `generate`.

### Lifecycle Management

Each plugin can define an `initialize()` and `cleanup()` method, which are called during plugin loading and unloading respectively. This pattern supports resource management and setup/teardown operations needed by plugins, such as connecting to databases or initializing external services.

## Integration

This file is central to the plugin system and is used extensively across the codebase. It's imported and utilized by:
- `PluginMetadata` is used by the plugin registry and test infrastructure.
- `Plugin` serves as a base class for other plugin types and is referenced by the plugin registry and test suites.
- `LanguageParserPlugin` is used by the core initialization logic and registry.
- `WikiGeneratorResult` is used in tests to validate plugin outputs.
- `WikiGeneratorPlugin` is used by the plugin runner and registry.
- `EmbeddingProviderPlugin` is used by the registry and initialization logic.

The classes defined here are essential for building a plugin-based system where different components can be dynamically loaded and executed based on configuration or runtime conditions.

## Design Notes

### Extensibility vs. Complexity

The design balances extensibility with maintainability. While it allows for extensive customization, it enforces a minimal interface that ensures plugins integrate smoothly with the core system. For instance, `WikiGeneratorPlugin` includes optional fields like `priority` and `run_after`, which allow for fine-grained control over execution order without requiring all plugins to implement complex scheduling logic.

### Type Safety and Data Structures

The use of `dataclass` for `PluginMetadata` and `WikiGeneratorResult` provides clean, readable data structures with automatic generation of `__init__`, `__repr__`, and other magic methods. This improves developer experience and reduces boilerplate code.

### File Extension Detection

In `LanguageParserPlugin`, the `detect_language` method uses simple file extension matching (`file_path.suffix.lower() in self.file_extensions`). While not sophisticated, this approach is sufficient for most use cases and avoids the overhead of full file type detection logic.

### Asynchronous Operations

Asynchronous methods are used in `WikiGeneratorPlugin` and `EmbeddingProviderPlugin` to support non-blocking operations, particularly important for I/O-bound tasks like API calls or database interactions. This aligns with modern Python practices and enables better performance under concurrent loads.

### Prioritization and Execution Order

The `WikiGeneratorPlugin` includes a `priority` property and a `run_after` list. This allows for complex generator dependencies and ordering, which is crucial when one generator's output is used as input by another. The default priority of 0 allows built-in generators to run at priority 100, ensuring predictable behavior.

By structuring plugins in this way, `local-deepwiki` supports a flexible and scalable plugin ecosystem that can evolve independently of the core system.

## API Reference

### class `PluginMetadata`

Metadata for a plugin.


<details>
<summary>View Source (lines 23-33) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L23-L33">GitHub</a></summary>

```python
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
```

</details>

### class `Plugin`

**Inherits from:** `ABC`

Base class for all plugins.

**Methods:**


<details>
<summary>View Source (lines 36-57) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L36-L57">GitHub</a></summary>

```python
class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin.

        Called when the plugin is loaded. Override to perform setup.
        """
        pass

    def cleanup(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is unloaded. Override to release resources.
        """
        pass
```

</details>

#### `metadata`

```python
def metadata() -> PluginMetadata
```

Get plugin metadata.


<details>
<summary>View Source (lines 36-57) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L36-L57">GitHub</a></summary>

```python
class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin.

        Called when the plugin is loaded. Override to perform setup.
        """
        pass

    def cleanup(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is unloaded. Override to release resources.
        """
        pass
```

</details>

#### `initialize`

```python
def initialize() -> None
```

Initialize the plugin.  Called when the plugin is loaded. Override to perform setup.


<details>
<summary>View Source (lines 36-57) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L36-L57">GitHub</a></summary>

```python
class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin.

        Called when the plugin is loaded. Override to perform setup.
        """
        pass

    def cleanup(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is unloaded. Override to release resources.
        """
        pass
```

</details>

#### `cleanup`

```python
def cleanup() -> None
```

Clean up plugin resources.  Called when the plugin is unloaded. Override to release resources.



<details>
<summary>View Source (lines 36-57) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L36-L57">GitHub</a></summary>

```python
class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin.

        Called when the plugin is loaded. Override to perform setup.
        """
        pass

    def cleanup(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is unloaded. Override to release resources.
        """
        pass
```

</details>

### class `LanguageParserPlugin`

**Inherits from:** `Plugin`

Plugin for adding support for new programming languages.  Subclass this to add parsing support for languages not built into local-deepwiki.

**Methods:**


<details>
<summary>View Source (lines 60-126) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L60-L126">GitHub</a></summary>

```python
class LanguageParserPlugin(Plugin):
    """Plugin for adding support for new programming languages.

    Subclass this to add parsing support for languages not built into
    local-deepwiki.

    Example:
        class ScalaParserPlugin(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="scala-parser",
                    version="1.0.0",
                    description="Scala language support",
                )

            @property
            def language_name(self) -> str:
                return "scala"

            @property
            def file_extensions(self) -> list[str]:
                return [".scala", ".sc"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                # Parse Scala source and return chunks
                ...
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Get the language name (lowercase, e.g., 'scala', 'elixir')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Get list of file extensions this plugin handles.

        Include the dot, e.g., ['.scala', '.sc'].
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        """Parse a source file and extract code chunks.

        Args:
            file_path: Path to the source file.
            source: The file contents as bytes.

        Returns:
            List of CodeChunk objects extracted from the file.
        """
        pass

    def detect_language(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this plugin should handle the file.
        """
        return file_path.suffix.lower() in self.file_extensions
```

</details>

#### `language_name`

```python
def language_name() -> str
```

Get the language name (lowercase, e.g., 'scala', 'elixir').


<details>
<summary>View Source (lines 60-126) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L60-L126">GitHub</a></summary>

```python
class LanguageParserPlugin(Plugin):
    """Plugin for adding support for new programming languages.

    Subclass this to add parsing support for languages not built into
    local-deepwiki.

    Example:
        class ScalaParserPlugin(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="scala-parser",
                    version="1.0.0",
                    description="Scala language support",
                )

            @property
            def language_name(self) -> str:
                return "scala"

            @property
            def file_extensions(self) -> list[str]:
                return [".scala", ".sc"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                # Parse Scala source and return chunks
                ...
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Get the language name (lowercase, e.g., 'scala', 'elixir')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Get list of file extensions this plugin handles.

        Include the dot, e.g., ['.scala', '.sc'].
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        """Parse a source file and extract code chunks.

        Args:
            file_path: Path to the source file.
            source: The file contents as bytes.

        Returns:
            List of CodeChunk objects extracted from the file.
        """
        pass

    def detect_language(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this plugin should handle the file.
        """
        return file_path.suffix.lower() in self.file_extensions
```

</details>

#### `file_extensions`

```python
def file_extensions() -> list[str]
```

Get list of file extensions this plugin handles.  Include the dot, e.g., ['.scala', '.sc'].


<details>
<summary>View Source (lines 60-126) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L60-L126">GitHub</a></summary>

```python
class LanguageParserPlugin(Plugin):
    """Plugin for adding support for new programming languages.

    Subclass this to add parsing support for languages not built into
    local-deepwiki.

    Example:
        class ScalaParserPlugin(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="scala-parser",
                    version="1.0.0",
                    description="Scala language support",
                )

            @property
            def language_name(self) -> str:
                return "scala"

            @property
            def file_extensions(self) -> list[str]:
                return [".scala", ".sc"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                # Parse Scala source and return chunks
                ...
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Get the language name (lowercase, e.g., 'scala', 'elixir')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Get list of file extensions this plugin handles.

        Include the dot, e.g., ['.scala', '.sc'].
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        """Parse a source file and extract code chunks.

        Args:
            file_path: Path to the source file.
            source: The file contents as bytes.

        Returns:
            List of CodeChunk objects extracted from the file.
        """
        pass

    def detect_language(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this plugin should handle the file.
        """
        return file_path.suffix.lower() in self.file_extensions
```

</details>

#### `parse_file`

```python
def parse_file(file_path: Path, source: bytes) -> list[CodeChunk]
```

Parse a source file and extract code chunks.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |
| `source` | `bytes` | - | The file contents as bytes. |


<details>
<summary>View Source (lines 60-126) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L60-L126">GitHub</a></summary>

```python
class LanguageParserPlugin(Plugin):
    """Plugin for adding support for new programming languages.

    Subclass this to add parsing support for languages not built into
    local-deepwiki.

    Example:
        class ScalaParserPlugin(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="scala-parser",
                    version="1.0.0",
                    description="Scala language support",
                )

            @property
            def language_name(self) -> str:
                return "scala"

            @property
            def file_extensions(self) -> list[str]:
                return [".scala", ".sc"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                # Parse Scala source and return chunks
                ...
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Get the language name (lowercase, e.g., 'scala', 'elixir')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Get list of file extensions this plugin handles.

        Include the dot, e.g., ['.scala', '.sc'].
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        """Parse a source file and extract code chunks.

        Args:
            file_path: Path to the source file.
            source: The file contents as bytes.

        Returns:
            List of CodeChunk objects extracted from the file.
        """
        pass

    def detect_language(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this plugin should handle the file.
        """
        return file_path.suffix.lower() in self.file_extensions
```

</details>

#### `detect_language`

```python
def detect_language(file_path: Path) -> bool
```

Check if this plugin can handle the given file.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to check. |



<details>
<summary>View Source (lines 60-126) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L60-L126">GitHub</a></summary>

```python
class LanguageParserPlugin(Plugin):
    """Plugin for adding support for new programming languages.

    Subclass this to add parsing support for languages not built into
    local-deepwiki.

    Example:
        class ScalaParserPlugin(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="scala-parser",
                    version="1.0.0",
                    description="Scala language support",
                )

            @property
            def language_name(self) -> str:
                return "scala"

            @property
            def file_extensions(self) -> list[str]:
                return [".scala", ".sc"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                # Parse Scala source and return chunks
                ...
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Get the language name (lowercase, e.g., 'scala', 'elixir')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Get list of file extensions this plugin handles.

        Include the dot, e.g., ['.scala', '.sc'].
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        """Parse a source file and extract code chunks.

        Args:
            file_path: Path to the source file.
            source: The file contents as bytes.

        Returns:
            List of CodeChunk objects extracted from the file.
        """
        pass

    def detect_language(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this plugin should handle the file.
        """
        return file_path.suffix.lower() in self.file_extensions
```

</details>

### class `WikiGeneratorResult`

Result from a wiki generator plugin.


<details>
<summary>View Source (lines 130-137) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L130-L137">GitHub</a></summary>

```python
class WikiGeneratorResult:
    """Result from a wiki generator plugin."""

    pages: list[WikiPage]
    """Generated wiki pages."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Optional metadata about the generation."""
```

</details>

### class `WikiGeneratorPlugin`

**Inherits from:** `Plugin`

Plugin for adding custom wiki page generators.  Subclass this to add new types of wiki pages or sections.

**Methods:**


<details>
<summary>View Source (lines 140-212) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L140-L212">GitHub</a></summary>

```python
class WikiGeneratorPlugin(Plugin):
    """Plugin for adding custom wiki page generators.

    Subclass this to add new types of wiki pages or sections.

    Example:
        class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="api-docs-generator",
                    version="1.0.0",
                    description="Generate API documentation pages",
                )

            @property
            def generator_name(self) -> str:
                return "api_docs"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                # Generate API documentation pages
                ...
    """

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Get the generator name (used for identification)."""
        pass

    @property
    def priority(self) -> int:
        """Get the generator priority (higher runs first).

        Default is 0. Built-in generators run at priority 100.
        """
        return 0

    @property
    def run_after(self) -> list[str]:
        """Get list of generator names this should run after.

        Use this for generators that depend on output from other generators.
        """
        return []

    @abstractmethod
    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with:
                - 'vector_store': VectorStore instance
                - 'llm': LLM provider instance
                - 'config': Config instance
                - 'existing_pages': List of already-generated WikiPage objects

        Returns:
            WikiGeneratorResult with generated pages.
        """
        pass
```

</details>

#### `generator_name`

```python
def generator_name() -> str
```

Get the generator name (used for identification).


<details>
<summary>View Source (lines 140-212) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L140-L212">GitHub</a></summary>

```python
class WikiGeneratorPlugin(Plugin):
    """Plugin for adding custom wiki page generators.

    Subclass this to add new types of wiki pages or sections.

    Example:
        class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="api-docs-generator",
                    version="1.0.0",
                    description="Generate API documentation pages",
                )

            @property
            def generator_name(self) -> str:
                return "api_docs"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                # Generate API documentation pages
                ...
    """

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Get the generator name (used for identification)."""
        pass

    @property
    def priority(self) -> int:
        """Get the generator priority (higher runs first).

        Default is 0. Built-in generators run at priority 100.
        """
        return 0

    @property
    def run_after(self) -> list[str]:
        """Get list of generator names this should run after.

        Use this for generators that depend on output from other generators.
        """
        return []

    @abstractmethod
    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with:
                - 'vector_store': VectorStore instance
                - 'llm': LLM provider instance
                - 'config': Config instance
                - 'existing_pages': List of already-generated WikiPage objects

        Returns:
            WikiGeneratorResult with generated pages.
        """
        pass
```

</details>

#### `priority`

```python
def priority() -> int
```

Get the generator priority (higher runs first).  Default is 0. Built-in generators run at priority 100.


<details>
<summary>View Source (lines 140-212) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L140-L212">GitHub</a></summary>

```python
class WikiGeneratorPlugin(Plugin):
    """Plugin for adding custom wiki page generators.

    Subclass this to add new types of wiki pages or sections.

    Example:
        class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="api-docs-generator",
                    version="1.0.0",
                    description="Generate API documentation pages",
                )

            @property
            def generator_name(self) -> str:
                return "api_docs"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                # Generate API documentation pages
                ...
    """

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Get the generator name (used for identification)."""
        pass

    @property
    def priority(self) -> int:
        """Get the generator priority (higher runs first).

        Default is 0. Built-in generators run at priority 100.
        """
        return 0

    @property
    def run_after(self) -> list[str]:
        """Get list of generator names this should run after.

        Use this for generators that depend on output from other generators.
        """
        return []

    @abstractmethod
    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with:
                - 'vector_store': VectorStore instance
                - 'llm': LLM provider instance
                - 'config': Config instance
                - 'existing_pages': List of already-generated WikiPage objects

        Returns:
            WikiGeneratorResult with generated pages.
        """
        pass
```

</details>

#### `run_after`

```python
def run_after() -> list[str]
```

Get list of generator names this should run after.  Use this for generators that depend on output from other generators.


<details>
<summary>View Source (lines 140-212) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L140-L212">GitHub</a></summary>

```python
class WikiGeneratorPlugin(Plugin):
    """Plugin for adding custom wiki page generators.

    Subclass this to add new types of wiki pages or sections.

    Example:
        class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="api-docs-generator",
                    version="1.0.0",
                    description="Generate API documentation pages",
                )

            @property
            def generator_name(self) -> str:
                return "api_docs"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                # Generate API documentation pages
                ...
    """

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Get the generator name (used for identification)."""
        pass

    @property
    def priority(self) -> int:
        """Get the generator priority (higher runs first).

        Default is 0. Built-in generators run at priority 100.
        """
        return 0

    @property
    def run_after(self) -> list[str]:
        """Get list of generator names this should run after.

        Use this for generators that depend on output from other generators.
        """
        return []

    @abstractmethod
    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with:
                - 'vector_store': VectorStore instance
                - 'llm': LLM provider instance
                - 'config': Config instance
                - 'existing_pages': List of already-generated WikiPage objects

        Returns:
            WikiGeneratorResult with generated pages.
        """
        pass
```

</details>

#### `generate`

```python
async def generate(index_status: IndexStatus, wiki_path: Path, context: dict[str, Any]) -> WikiGeneratorResult
```

Generate wiki pages.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | `IndexStatus` | - | The repository index status. |
| `wiki_path` | `Path` | - | Path to the wiki output directory. |
| `context` | `dict[str, Any]` | - | Context dictionary with: - 'vector_store': VectorStore instance - 'llm': LLM provider instance - 'config': Config instance - 'existing_pages': List of already-generated WikiPage objects |



<details>
<summary>View Source (lines 140-212) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L140-L212">GitHub</a></summary>

```python
class WikiGeneratorPlugin(Plugin):
    """Plugin for adding custom wiki page generators.

    Subclass this to add new types of wiki pages or sections.

    Example:
        class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="api-docs-generator",
                    version="1.0.0",
                    description="Generate API documentation pages",
                )

            @property
            def generator_name(self) -> str:
                return "api_docs"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                # Generate API documentation pages
                ...
    """

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Get the generator name (used for identification)."""
        pass

    @property
    def priority(self) -> int:
        """Get the generator priority (higher runs first).

        Default is 0. Built-in generators run at priority 100.
        """
        return 0

    @property
    def run_after(self) -> list[str]:
        """Get list of generator names this should run after.

        Use this for generators that depend on output from other generators.
        """
        return []

    @abstractmethod
    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with:
                - 'vector_store': VectorStore instance
                - 'llm': LLM provider instance
                - 'config': Config instance
                - 'existing_pages': List of already-generated WikiPage objects

        Returns:
            WikiGeneratorResult with generated pages.
        """
        pass
```

</details>

### class `EmbeddingProviderPlugin`

**Inherits from:** `Plugin`

Plugin for adding custom embedding providers.  Subclass this to add support for custom embedding models or services.

**Methods:**


<details>
<summary>View Source (lines 215-267) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L215-L267">GitHub</a></summary>

```python
class EmbeddingProviderPlugin(Plugin):
    """Plugin for adding custom embedding providers.

    Subclass this to add support for custom embedding models or services.

    Example:
        class CohereEmbeddingPlugin(EmbeddingProviderPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="cohere-embeddings",
                    version="1.0.0",
                    description="Cohere embedding support",
                )

            @property
            def provider_name(self) -> str:
                return "cohere"

            async def embed(self, texts: list[str]) -> list[list[float]]:
                # Call Cohere API to generate embeddings
                ...

            def get_dimension(self) -> int:
                return 1024  # Cohere embed-english-v3.0 dimension
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (used in config)."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        pass
```

</details>

#### `provider_name`

```python
def provider_name() -> str
```

Get the provider name (used in config).


<details>
<summary>View Source (lines 215-267) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L215-L267">GitHub</a></summary>

```python
class EmbeddingProviderPlugin(Plugin):
    """Plugin for adding custom embedding providers.

    Subclass this to add support for custom embedding models or services.

    Example:
        class CohereEmbeddingPlugin(EmbeddingProviderPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="cohere-embeddings",
                    version="1.0.0",
                    description="Cohere embedding support",
                )

            @property
            def provider_name(self) -> str:
                return "cohere"

            async def embed(self, texts: list[str]) -> list[list[float]]:
                # Call Cohere API to generate embeddings
                ...

            def get_dimension(self) -> int:
                return 1024  # Cohere embed-english-v3.0 dimension
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (used in config)."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        pass
```

</details>

#### `embed`

```python
async def embed(texts: list[str]) -> list[list[float]]
```

Generate embeddings for texts.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `texts` | `list[str]` | - | List of text strings to embed. |


<details>
<summary>View Source (lines 215-267) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L215-L267">GitHub</a></summary>

```python
class EmbeddingProviderPlugin(Plugin):
    """Plugin for adding custom embedding providers.

    Subclass this to add support for custom embedding models or services.

    Example:
        class CohereEmbeddingPlugin(EmbeddingProviderPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="cohere-embeddings",
                    version="1.0.0",
                    description="Cohere embedding support",
                )

            @property
            def provider_name(self) -> str:
                return "cohere"

            async def embed(self, texts: list[str]) -> list[list[float]]:
                # Call Cohere API to generate embeddings
                ...

            def get_dimension(self) -> int:
                return 1024  # Cohere embed-english-v3.0 dimension
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (used in config)."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        pass
```

</details>

#### `get_dimension`

```python
def get_dimension() -> int
```

Get the embedding dimension.




<details>
<summary>View Source (lines 215-267) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/plugins/base.py#L215-L267">GitHub</a></summary>

```python
class EmbeddingProviderPlugin(Plugin):
    """Plugin for adding custom embedding providers.

    Subclass this to add support for custom embedding models or services.

    Example:
        class CohereEmbeddingPlugin(EmbeddingProviderPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="cohere-embeddings",
                    version="1.0.0",
                    description="Cohere embedding support",
                )

            @property
            def provider_name(self) -> str:
                return "cohere"

            async def embed(self, texts: list[str]) -> list[list[float]]:
                # Call Cohere API to generate embeddings
                ...

            def get_dimension(self) -> int:
                return 1024  # Cohere embed-english-v3.0 dimension
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (used in config)."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        pass
```

</details>

## Class Diagram

```mermaid
classDiagram
    class EmbeddingProviderPlugin {
        <<abstract>>
        +Example: class CohereEmbeddingPlugin(EmbeddingProviderPlugin):
        +metadata() -> PluginMetadata
        +provider_name() -> str
        +embed() -> list[list[float]]
        +get_dimension() -> int
    }
    class LanguageParserPlugin {
        <<abstract>>
        +Example: class ScalaParserPlugin(LanguageParserPlugin):
        +metadata() -> PluginMetadata
        +language_name() -> str
        +file_extensions() -> list[str]
        +parse_file() -> list[CodeChunk]
        +detect_language() -> bool
    }
    class Plugin {
        <<abstract>>
        +metadata() -> PluginMetadata
        +initialize() -> None
        +cleanup() -> None
    }
    class PluginMetadata {
        +name: str
        +version: str
        +description: str
        +author: str
        +dependencies: list[str]
        -__str__() -> str
    }
    class WikiGeneratorPlugin {
        <<abstract>>
        +Example: class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
        +metadata() -> PluginMetadata
        +generator_name() -> str
        +generate() -> WikiGeneratorResult
        +priority() -> int
        +run_after() -> list[str]
    }
    class WikiGeneratorResult {
        +pages: list[WikiPage]
        +metadata: dict[str, Any]
    }
    EmbeddingProviderPlugin --|> Plugin
    LanguageParserPlugin --|> Plugin
    Plugin --|> ABC
    WikiGeneratorPlugin --|> Plugin
```

## Usage Examples

*Examples extracted from test files*

### Test that calling EmbeddingProvider.embed raises TypeError (abstract)

From `test_base_provider.py::TestEmbeddingProviderAbstractMethods::test_embed_abstract_method_body`:

```python
# These calls will execute the pass statements in the abstract base
assert provider.dimension == 768
assert provider.name == "test-embedding"
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `PluginMetadata` | class | Brian Breidenbach | Jan 25, 2026 | `f2db999` Add plugin system for exten... |
| `Plugin` | class | Brian Breidenbach | Jan 25, 2026 | `f2db999` Add plugin system for exten... |
| `LanguageParserPlugin` | class | Brian Breidenbach | Jan 25, 2026 | `f2db999` Add plugin system for exten... |
| `WikiGeneratorResult` | class | Brian Breidenbach | Jan 25, 2026 | `f2db999` Add plugin system for exten... |
| `WikiGeneratorPlugin` | class | Brian Breidenbach | Jan 25, 2026 | `f2db999` Add plugin system for exten... |
| `EmbeddingProviderPlugin` | class | Brian Breidenbach | Jan 25, 2026 | `f2db999` Add plugin system for exten... |

## Relevant Source Files

- `src/local_deepwiki/plugins/base.py:23-33`
