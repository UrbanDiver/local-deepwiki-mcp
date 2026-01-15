# tests/test_web.py

## File Overview

This file contains unit tests for the Flask web application functionality of the local_deepwiki project. It tests core web app features including app initialization, routing, template configuration, breadcrumb generation, and chat endpoints.

## Test Classes

### TestFlaskApp

Tests for Flask app functionality, focusing on app creation and basic routing behavior.

**Key Test Methods:**
- `test_create_app(wiki_dir)` - Verifies that the [create_app](../src/local_deepwiki/web/app.md) function initializes correctly with a valid wiki directory
- `test_create_app_invalid_path()` - Tests that [create_app](../src/local_deepwiki/web/app.md) raises a ValueError when given a non-existent path
- `test_index_redirect(wiki_dir)` - Tests that the root path redirects to `/wiki/index.md`

### TestTemplateConfiguration

Tests for Jinja2 template configuration and template file existence.

**Key Test Methods:**
- `test_template_folder_exists()` - Verifies that the templates folder exists in the module directory
- `test_page_template_exists()` - Confirms that the `page.html` template file exists
- `test_app_configured_with_template_folder` - Tests template folder configuration (method signature truncated in provided code)

### TestBuildBreadcrumb

Tests for breadcrumb generation functionality (implementation details not shown in provided code).

### TestChatEndpoints

Tests for chat endpoint functionality (implementation details not shown in provided code).

## Functions

### wiki_dir

A pytest fixture function that provides a wiki directory for testing purposes (implementation not shown in provided code).

## Usage Examples

```python
# Testing app creation
def test_create_app(wiki_dir):
    app = create_app(wiki_dir)
    assert app is not None

# Testing invalid path handling
def test_create_app_invalid_path():
    with pytest.raises(ValueError, match="does not exist"):
        create_app("/nonexistent/path")
```

## Related Components

This test file imports and tests components from:
- `local_deepwiki.web.app` - The [main](../src/local_deepwiki/export/html.md) Flask application module containing:
  - `_MODULE_DIR` - Module directory constant
  - `app` - Flask application instance
  - [`build_breadcrumb`](../src/local_deepwiki/web/app.md) - Breadcrumb generation function
  - [`create_app`](../src/local_deepwiki/web/app.md) - App factory function

The tests use standard testing libraries:
- `pytest` for test framework functionality
- `tempfile` for temporary file/directory creation
- `pathlib.Path` for file system path operations

## API Reference

### class `TestBuildBreadcrumb`

Tests for [build_breadcrumb](../src/local_deepwiki/web/app.md) function.

**Methods:**

#### `test_root_page_no_breadcrumb`

```python
def test_root_page_no_breadcrumb(wiki_dir)
```

Root pages should have no breadcrumb.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_simple_nested_page`

```python
def test_simple_nested_page(wiki_dir)
```

Pages one level deep should show Home > Section > Page.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_deeply_nested_page`

```python
def test_deeply_nested_page(wiki_dir)
```

Deeply nested pages should show full path.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_index_page_in_section`

```python
def test_index_page_in_section(wiki_dir)
```

Index pages in sections should show proper breadcrumb.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_formatting_underscores_and_dashes`

```python
def test_formatting_underscores_and_dashes(wiki_dir)
```

Underscores and dashes should be replaced with spaces.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |


### class `TestFlaskApp`

Tests for Flask app functionality.

**Methods:**

#### `test_create_app`

```python
def test_create_app(wiki_dir)
```

Test that [create_app](../src/local_deepwiki/web/app.md) initializes correctly.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_create_app_invalid_path`

```python
def test_create_app_invalid_path()
```

Test that [create_app](../src/local_deepwiki/web/app.md) raises error for invalid path.

#### `test_index_redirect`

```python
def test_index_redirect(wiki_dir)
```

Test that / redirects to /wiki/index.md.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_view_page`

```python
def test_view_page(wiki_dir)
```

Test viewing a wiki page.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_view_nested_page_has_breadcrumb`

```python
def test_view_nested_page_has_breadcrumb(wiki_dir)
```

Test that nested pages display breadcrumbs.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_404_for_missing_page`

```python
def test_404_for_missing_page(wiki_dir)
```

Test that missing pages return 404.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |


### class `TestTemplateConfiguration`

Tests for Jinja2 template configuration.

**Methods:**

#### `test_template_folder_exists`

```python
def test_template_folder_exists()
```

Test that the templates folder exists.

#### `test_page_template_exists`

```python
def test_page_template_exists()
```

Test that the page.html template exists.

#### `test_app_configured_with_template_folder`

```python
def test_app_configured_with_template_folder()
```

Test that Flask app has correct template folder configured.

#### `test_template_contains_required_blocks`

```python
def test_template_contains_required_blocks()
```

Test that the template contains essential Jinja2 variables.

#### `test_template_caching_enabled_in_production`

```python
def test_template_caching_enabled_in_production(wiki_dir)
```

Test that template caching is enabled when debug=False.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_chat_template_exists`

```python
def test_chat_template_exists()
```

Test that the chat.html template exists.


### class `TestChatEndpoints`

Tests for chat functionality.

**Methods:**

#### `test_chat_page_renders`

```python
def test_chat_page_renders(wiki_dir)
```

Test that the chat page renders successfully.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_chat_page_has_input_elements`

```python
def test_chat_page_has_input_elements(wiki_dir)
```

Test that the chat page has required input elements.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_api_chat_requires_question`

```python
def test_api_chat_requires_question(wiki_dir)
```

Test that /api/chat returns error for missing question.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_api_research_requires_question`

```python
def test_api_research_requires_question(wiki_dir)
```

Test that /api/research returns error for missing question.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_api_chat_returns_sse`

```python
def test_api_chat_returns_sse(wiki_dir)
```

Test that /api/chat returns Server-Sent Events content type.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_api_research_returns_sse`

```python
def test_api_research_returns_sse(wiki_dir)
```

Test that /api/research returns Server-Sent Events content type.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |

#### `test_page_template_has_chat_link`

```python
def test_page_template_has_chat_link(wiki_dir)
```

Test that wiki pages have a link to the chat interface.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_dir` | - | - | - |


---

### Functions

#### `wiki_dir`

`@pytest.fixture`

```python
def wiki_dir()
```

Create a temporary wiki directory structure.



## Class Diagram

```mermaid
classDiagram
    class TestBuildBreadcrumb {
        +test_root_page_no_breadcrumb()
        +test_simple_nested_page()
        +test_deeply_nested_page()
        +test_index_page_in_section()
        +test_formatting_underscores_and_dashes()
    }
    class TestChatEndpoints {
        +test_chat_page_renders()
        +test_chat_page_has_input_elements()
        +test_api_chat_requires_question()
        +test_api_research_requires_question()
        +test_api_chat_returns_sse()
        +test_api_research_returns_sse()
        +test_page_template_has_chat_link()
    }
    class TestFlaskApp {
        +test_create_app()
        +test_create_app_invalid_path()
        +test_index_redirect()
        +test_view_page()
        +test_view_nested_page_has_breadcrumb()
        +test_404_for_missing_page()
    }
    class TestTemplateConfiguration {
        +test_template_folder_exists()
        +test_page_template_exists()
        +test_app_configured_with_template_folder()
        +test_template_contains_required_blocks()
        +test_template_caching_enabled_in_production()
        +test_chat_template_exists()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[TemporaryDirectory]
    N2[TestBuildBreadcrumb.test_fo...]
    N3[TestBuildBreadcrumb.test_ro...]
    N4[TestBuildBreadcrumb.test_si...]
    N5[TestChatEndpoints.test_api_...]
    N6[TestChatEndpoints.test_api_...]
    N7[TestChatEndpoints.test_api_...]
    N8[TestChatEndpoints.test_api_...]
    N9[TestChatEndpoints.test_chat...]
    N10[TestChatEndpoints.test_chat...]
    N11[TestChatEndpoints.test_page...]
    N12[TestFlaskApp.test_404_for_m...]
    N13[TestFlaskApp.test_create_ap...]
    N14[TestFlaskApp.test_index_red...]
    N15[TestFlaskApp.test_view_nest...]
    N16[TestFlaskApp.test_view_page]
    N17[TestTemplateConfiguration.t...]
    N18[TestTemplateConfiguration.t...]
    N19[TestTemplateConfiguration.t...]
    N20[build_breadcrumb]
    N21[create_app]
    N22[exists]
    N23[get_json]
    N24[is_file]
    N25[mkdir]
    N26[post]
    N27[test_client]
    N28[wiki_dir]
    N29[write_text]
    N28 --> N1
    N28 --> N0
    N28 --> N29
    N28 --> N25
    N3 --> N20
    N4 --> N20
    N2 --> N25
    N2 --> N29
    N2 --> N20
    N13 --> N21
    N14 --> N21
    N14 --> N27
    N16 --> N21
    N16 --> N27
    N15 --> N21
    N15 --> N27
    N12 --> N21
    N12 --> N27
    N19 --> N22
    N18 --> N22
    N18 --> N24
    N17 --> N22
    N17 --> N24
    N10 --> N21
    N10 --> N27
    N9 --> N21
    N9 --> N27
    N5 --> N21
    N5 --> N27
    N5 --> N26
    N5 --> N23
    N7 --> N21
    N7 --> N27
    N7 --> N26
    N7 --> N23
    N6 --> N21
    N6 --> N27
    N6 --> N26
    N8 --> N21
    N8 --> N27
    N8 --> N26
    N11 --> N21
    N11 --> N27
    classDef func fill:#e1f5fe
    class N0,N1,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19 method
```

## Relevant Source Files

- `tests/test_web.py:40-104`

## See Also

- [test_search](test_search.md) - shares 4 dependencies
- [test_parser](test_parser.md) - shares 3 dependencies
- [test_indexer](test_indexer.md) - shares 3 dependencies
