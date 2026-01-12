# File: test_watcher.py

## File Overview

This file contains unit tests for the watcher module, which is responsible for monitoring file system changes in a repository and scheduling reindexing operations. The tests cover the functionality of [`DebouncedHandler`](../src/local_deepwiki/watcher.md) and [`RepositoryWatcher`](../src/local_deepwiki/watcher.md) classes, ensuring that file events are properly handled and debounced to prevent excessive reindexing.

The watcher module integrates with the configuration system to determine debounce intervals and watched file extensions. It works closely with the indexing system to trigger reindexing when relevant files change.

## Classes

### TestWatchedExtensions

This class tests that the correct file extensions are included in the WATCHED_EXTENSIONS constant. It ensures that Python, JavaScript, and other relevant file types are properly configured for monitoring.

Key methods:
- `test_python_extensions`: Verifies that Python file extensions (.py, .pyi) are watched
- `test_javascript_extensions`: Verifies that JavaScript/TypeScript file extensions (.js, .jsx, .ts, .tsx) are watched
- `test_other_extensions`: Verifies that other common extensions are watched

### TestDebouncedHandler

This class tests the [DebouncedHandler](../src/local_deepwiki/watcher.md), which is responsible for handling file system events and scheduling reindexing operations with debouncing to prevent excessive processing.

Key methods:
- `test_should_watch_python_file`: Tests that Python files are correctly identified as watchable
- `test_should_watch_javascript_file`: Tests that JavaScript files are correctly identified as watchable
- `test_should_watch_other_file`: Tests that other watched file types are correctly identified
- `test_should_not_watch_unwatched_file`: Tests that non-watched file types are correctly ignored
- `test_on_modified_schedules_reindex`: Tests that file modifications schedule reindexing
- `test_on_created_schedules_reindex`: Tests that file creation schedules reindexing
- `test_on_deleted_schedules_reindex`: Tests that file deletion schedules reindexing
- `test_directory_events_ignored`: Tests that directory events are ignored
- `test_non_watched_file_ignored`: Tests that non-watched file events are ignored
- `test_multiple_changes_debounced`: Tests that multiple rapid changes are properly debounced

### TestRepositoryWatcher

This class tests the [RepositoryWatcher](../src/local_deepwiki/watcher.md), which manages the file system monitoring for a repository.

Key methods:
- `test_create_watcher`: Tests creating a basic watcher with default settings
- `test_create_watcher_with_options`: Tests creating a watcher with custom configuration options

### TestDebouncedHandlerEvents

This class contains comprehensive tests for the event handling functionality of [DebouncedHandler](../src/local_deepwiki/watcher.md).

## Functions

### handler fixture

A pytest fixture that creates a [DebouncedHandler](../src/local_deepwiki/watcher.md) instance for testing with a temporary directory and a short debounce time (0.1 seconds).

### handler_with_mock fixture

A pytest fixture that creates a [DebouncedHandler](../src/local_deepwiki/watcher.md) instance with mocked dependencies for testing event handling without actual file system operations.

## Usage Examples

### Testing file watching behavior

```python
def test_file_watching_behavior(self, handler_with_mock, tmp_path):
    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.touch()
    
    # Create a mock event for file modification
    event = MagicMock()
    event.is_directory = False
    event.src_path = str(test_file)
    
    # Handle the event
    handler_with_mock.on_modified(event)
    
    # Verify the file was added to pending files
    assert str(test_file) in handler_with_mock._pending_files
```

### Testing debounce functionality

```python
def test_debounce_behavior(self, handler_with_mock, tmp_path):
    # Create multiple rapid file changes
    files = [tmp_path / f"file{i}.py" for i in range(3)]
    for f in files:
        f.touch()
    
    # Process events rapidly
    for f in files:
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(f)
        handler_with_mock.on_modified(event)
    
    # Verify all files are pending (debounced)
    assert len(handler_with_mock._pending_files) == 3
    assert handler_with_mock._timer is not None
```

## Related Components

This file works with the [Config](../src/local_deepwiki/config.md) class to retrieve configuration settings for debounce intervals. It integrates with the [RepositoryWatcher](../src/local_deepwiki/watcher.md) to monitor file system changes and schedule reindexing operations. The tests verify that the [DebouncedHandler](../src/local_deepwiki/watcher.md) properly interacts with the file system monitoring system and that events are correctly processed and debounced to prevent excessive reindexing operations.

## API Reference

### class `TestWatchedExtensions`

Test that watched extensions are correct.

**Methods:**

#### `test_python_extensions`

```python
def test_python_extensions()
```

Test Python extensions are watched.

#### `test_javascript_extensions`

```python
def test_javascript_extensions()
```

Test JavaScript/TypeScript extensions are watched.

#### `test_other_extensions`

```python
def test_other_extensions()
```

Test other language extensions are watched.


### class `TestDebouncedHandler`

Test [DebouncedHandler](../src/local_deepwiki/watcher.md) functionality.

**Methods:**

#### `handler`

```python
def handler(tmp_path)
```

Create a handler for testing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_should_watch_python_file`

```python
def test_should_watch_python_file(handler, tmp_path)
```

Test that Python files are watched.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_watch_typescript_file`

```python
def test_should_watch_typescript_file(handler, tmp_path)
```

Test that TypeScript files are watched.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_not_watch_text_file`

```python
def test_should_not_watch_text_file(handler, tmp_path)
```

Test that text files are not watched.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_not_watch_json_file`

```python
def test_should_not_watch_json_file(handler, tmp_path)
```

Test that JSON files are not watched.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_exclude_node_modules`

```python
def test_should_exclude_node_modules(handler, tmp_path)
```

Test that node_modules files are excluded.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_exclude_venv`

```python
def test_should_exclude_venv(handler, tmp_path)
```

Test that venv files are excluded.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_exclude_pycache`

```python
def test_should_exclude_pycache(handler, tmp_path)
```

Test that __pycache__ files are excluded.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_exclude_git`

```python
def test_should_exclude_git(handler, tmp_path)
```

Test that .git files are excluded.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_should_watch_nested_file`

```python
def test_should_watch_nested_file(handler, tmp_path)
```

Test that nested source files are watched.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_file_outside_repo_not_watched`

```python
def test_file_outside_repo_not_watched(handler, tmp_path)
```

Test that files outside repo are not watched.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | - | - | - |
| `tmp_path` | - | - | - |


### class `TestRepositoryWatcher`

Test [RepositoryWatcher](../src/local_deepwiki/watcher.md) functionality.

**Methods:**

#### `test_create_watcher`

```python
def test_create_watcher(tmp_path)
```

Test creating a watcher.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_create_watcher_with_options`

```python
def test_create_watcher_with_options(tmp_path)
```

Test creating a watcher with options.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_start_stop_watcher`

```python
def test_start_stop_watcher(tmp_path)
```

Test starting and stopping a watcher.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_stop_without_start`

```python
def test_stop_without_start(tmp_path)
```

Test stopping a watcher that was never started.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |


### class `TestDebouncedHandlerEvents`

Test event handling with debouncing.

**Methods:**

#### `handler_with_mock`

```python
def handler_with_mock(tmp_path)
```

Create a handler with mocked reindex.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_on_modified_schedules_reindex`

```python
def test_on_modified_schedules_reindex(handler_with_mock, tmp_path)
```

Test that file modification schedules reindex.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler_with_mock` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_on_created_schedules_reindex`

```python
def test_on_created_schedules_reindex(handler_with_mock, tmp_path)
```

Test that file creation schedules reindex.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler_with_mock` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_on_deleted_schedules_reindex`

```python
def test_on_deleted_schedules_reindex(handler_with_mock, tmp_path)
```

Test that file deletion schedules reindex.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler_with_mock` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_directory_events_ignored`

```python
def test_directory_events_ignored(handler_with_mock, tmp_path)
```

Test that directory events are ignored.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler_with_mock` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_non_watched_file_ignored`

```python
def test_non_watched_file_ignored(handler_with_mock, tmp_path)
```

Test that non-watched files are ignored.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler_with_mock` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_multiple_changes_debounced`

```python
def test_multiple_changes_debounced(handler_with_mock, tmp_path)
```

Test that multiple rapid changes are debounced.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler_with_mock` | - | - | - |
| `tmp_path` | - | - | - |



## Class Diagram

```mermaid
classDiagram
    class TestDebouncedHandler {
        +handler()
        +test_should_watch_python_file()
        +test_should_watch_typescript_file()
        +test_should_not_watch_text_file()
        +test_should_not_watch_json_file()
        +test_should_exclude_node_modules()
        +test_should_exclude_venv()
        +test_should_exclude_pycache()
        +test_should_exclude_git()
        +test_should_watch_nested_file()
        +test_file_outside_repo_not_watched()
    }
    class TestDebouncedHandlerEvents {
        +handler_with_mock()
        +test_on_modified_schedules_reindex()
        +test_on_created_schedules_reindex()
        +test_on_deleted_schedules_reindex()
        +test_directory_events_ignored()
        +test_non_watched_file_ignored()
        +test_multiple_changes_debounced()
    }
    class TestRepositoryWatcher {
        +test_create_watcher()
        +test_create_watcher_with_options()
        +test_start_stop_watcher()
        +test_stop_without_start()
    }
    class TestWatchedExtensions {
        +test_python_extensions()
        +test_javascript_extensions()
        +test_other_extensions()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Config]
    N1[DebouncedHandler]
    N2[MagicMock]
    N3[RepositoryWatcher]
    N4[TestDebouncedHandler.handler]
    N5[TestDebouncedHandler.test_f...]
    N6[TestDebouncedHandler.test_s...]
    N7[TestDebouncedHandler.test_s...]
    N8[TestDebouncedHandler.test_s...]
    N9[TestDebouncedHandler.test_s...]
    N10[TestDebouncedHandler.test_s...]
    N11[TestDebouncedHandler.test_s...]
    N12[TestDebouncedHandler.test_s...]
    N13[TestDebouncedHandler.test_s...]
    N14[TestDebouncedHandler.test_s...]
    N15[TestDebouncedHandlerEvents....]
    N16[TestDebouncedHandlerEvents....]
    N17[TestDebouncedHandlerEvents....]
    N18[TestDebouncedHandlerEvents....]
    N19[TestDebouncedHandlerEvents....]
    N20[TestDebouncedHandlerEvents....]
    N21[TestRepositoryWatcher.test_...]
    N22[TestRepositoryWatcher.test_...]
    N23[TestRepositoryWatcher.test_...]
    N24[_should_watch_file]
    N25[cancel]
    N26[is_running]
    N27[mkdir]
    N28[on_modified]
    N29[touch]
    N4 --> N0
    N4 --> N1
    N13 --> N29
    N13 --> N24
    N14 --> N29
    N14 --> N24
    N11 --> N29
    N11 --> N24
    N10 --> N29
    N10 --> N24
    N7 --> N27
    N7 --> N29
    N7 --> N24
    N9 --> N27
    N9 --> N29
    N9 --> N24
    N8 --> N27
    N8 --> N29
    N8 --> N24
    N6 --> N27
    N6 --> N29
    N6 --> N24
    N12 --> N27
    N12 --> N29
    N12 --> N24
    N5 --> N27
    N5 --> N29
    N5 --> N24
    N21 --> N3
    N21 --> N26
    N22 --> N3
    N22 --> N26
    N23 --> N3
    N23 --> N26
    N15 --> N0
    N15 --> N1
    N20 --> N29
    N20 --> N2
    N20 --> N28
    N20 --> N25
    N18 --> N29
    N18 --> N2
    N18 --> N25
    N19 --> N2
    N19 --> N25
    N17 --> N29
    N17 --> N2
    N17 --> N28
    N16 --> N29
    N16 --> N2
    N16 --> N28
    N16 --> N25
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23 method
```

## See Also

- [watcher](../src/local_deepwiki/watcher.md) - dependency
- [config](../src/local_deepwiki/config.md) - dependency
- [test_incremental_wiki](test_incremental_wiki.md) - shares 4 dependencies
- [indexer](../src/local_deepwiki/core/indexer.md) - shares 3 dependencies
