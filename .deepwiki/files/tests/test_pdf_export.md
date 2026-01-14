# test_pdf_export.py

## File Overview

This test file provides comprehensive testing for PDF export functionality in the local_deepwiki package. It tests the PdfExporter class and related utility functions for converting wiki content to PDF format, including mermaid diagram handling and markdown rendering.

## Classes

### TestPdfExporter

Tests the core PdfExporter class functionality for converting wiki content to PDF format.

**Key Methods:**
- `test_collect_pages_in_order` - Verifies that pages are collected according to TOC ordering
- `test_extract_paths_from_toc` - Tests extraction of file paths from table of contents
- `test_build_toc_html` - Tests generation of HTML table of contents
- `test_export_single_creates_pdf` - Verifies single PDF creation functionality
- `test_export_single_with_directory_output` - Tests PDF creation when output is a directory
- `test_export_separate_creates_multiple_pdfs` - Tests creation of separate PDFs for each page
- `test_export_separate_preserves_directory_structure` - Verifies directory structure preservation

### TestExportToPdf

Tests the `export_to_pdf` convenience function for PDF export operations.

**Key Methods:**
- `test_raises_for_nonexistent_wiki` - Verifies error handling for invalid wiki paths

**Fixtures:**
- `simple_wiki` - Creates a minimal wiki structure for testing

### TestRenderMarkdownForPdf

Tests PDF-specific markdown rendering functionality.

**Key Methods:**
- `test_basic_markdown` - Tests basic markdown to HTML conversion
- `test_code_blocks` - Tests fenced code block rendering
- `test_tables` - Tests table rendering for PDF output

### TestMermaidHandling

Tests mermaid diagram handling when CLI tools are not available.

**Key Methods:**
- `test_mermaid_replaced_with_note` - Verifies mermaid diagrams are replaced with informational notes
- `test_regular_code_blocks_preserved` - Ensures regular code blocks remain unaffected

### TestIsMmdcAvailable

Tests the mermaid CLI availability detection functionality.

**Key Methods:**
- `test_mmdc_available` - Tests detection when mermaid CLI is available
- `test_mmdc_not_available` - Tests behavior when CLI is unavailable

### TestRenderMermaidToPng

Tests PNG rendering of mermaid diagrams using the CLI.

**Key Methods:**
- `test_returns_none_when_mmdc_unavailable` - Tests fallback when CLI is unavailable
- `test_returns_none_on_cli_error` - Tests error handling for CLI failures

### TestMermaidCliRendering

Tests mermaid diagram rendering when CLI tools are available.

**Key Methods:**
- `test_renders_mermaid_when_cli_available` - Tests PNG rendering when CLI is present

## Functions Tested

The test file validates these imported functions:

- `export_to_pdf` - Main convenience function for PDF export
- `extract_mermaid_blocks` - Extracts mermaid diagram blocks from markdown
- [`extract_title`](../src/local_deepwiki/web/app.md) - Extracts title from markdown content
- `is_mmdc_available` - Checks if mermaid CLI is available
- `render_markdown_for_pdf` - Renders markdown optimized for PDF output
- `render_mermaid_to_png` - Renders mermaid diagrams as PNG images
- `render_mermaid_to_svg` - Renders mermaid diagrams as SVG images

## Usage Examples

### Testing PDF Export

```python
# Test single PDF creation
exporter = PdfExporter(sample_wiki, output_path)
result = exporter.export_single()
assert result == output_path

# Test separate PDF creation
results = exporter.export_separate()
assert len(results) == 4  # Number of markdown files
```

### Testing Markdown Rendering

```python
# Test basic markdown conversion
md = "# Hello\n\nThis is a paragraph."
html = render_markdown_for_pdf(md)
assert "<h1" in html
assert "Hello" in html
```

### Testing Mermaid Handling

```python
# Test mermaid diagram replacement
md = '''```mermaid
graph TD
    A[Start] --> B[End]
```'''
html = render_markdown_for_pdf(md, render_mermaid=False)
assert "mermaid-note" in html
```

## Related Components

This test file works with several components from the `local_deepwiki.export.pdf` module:

- **PdfExporter** - Main class for PDF export operations
- **PRINT_CSS** - CSS constants for PDF styling
- **WeasyPrint integration** - Mocked HTML-to-PDF conversion
- **Subprocess operations** - For mermaid CLI interaction

The tests use pytest fixtures and mocking to isolate functionality and test various scenarios including CLI availability, file system operations, and error conditions.

## API Reference

### class `TestRenderMarkdownForPdf`

Tests for PDF-specific markdown rendering.

**Methods:**

#### `test_basic_markdown`

```python
def test_basic_markdown()
```

Test basic markdown conversion.

#### `test_code_blocks`

```python
def test_code_blocks()
```

Test fenced code blocks.

#### `test_tables`

```python
def test_tables()
```

Test markdown tables.

#### `test_mermaid_blocks_replaced_with_note`

```python
def test_mermaid_blocks_replaced_with_note()
```

Test that mermaid blocks are replaced with a note when CLI unavailable.

#### `test_multiple_mermaid_blocks`

```python
def test_multiple_mermaid_blocks()
```

Test handling multiple mermaid blocks when CLI unavailable.


### class `TestExtractTitle`

Tests for title extraction.

**Methods:**

#### `test_h1_title`

```python
def test_h1_title(tmp_path: Path)
```

Test extracting H1 title.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |

#### `test_bold_title`

```python
def test_bold_title(tmp_path: Path)
```

Test extracting bold title.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |

#### `test_fallback_to_filename`

```python
def test_fallback_to_filename(tmp_path: Path)
```

Test fallback to filename when no title found.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |

#### `test_h1_with_leading_whitespace`

```python
def test_h1_with_leading_whitespace(tmp_path: Path)
```

Test extracting H1 title with leading whitespace.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |


### class `TestPdfExporter`

Tests for PdfExporter class.

**Methods:**

#### `sample_wiki`

```python
def sample_wiki(tmp_path: Path) -> Path
```

Create a sample wiki structure for testing.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |

#### `test_collect_pages_in_order`

```python
def test_collect_pages_in_order(sample_wiki: Path, tmp_path: Path)
```

Test that pages are collected in TOC order.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_extract_paths_from_toc`

```python
def test_extract_paths_from_toc(sample_wiki: Path, tmp_path: Path)
```

Test extracting paths from nested TOC.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_build_toc_html`

```python
def test_build_toc_html(sample_wiki: Path, tmp_path: Path)
```

Test building TOC HTML.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_export_single_creates_pdf`

```python
def test_export_single_creates_pdf(mock_html_class, sample_wiki: Path, tmp_path: Path)
```

Test that export_single creates a PDF file.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_export_single_with_directory_output`

```python
def test_export_single_with_directory_output(mock_html_class, sample_wiki: Path, tmp_path: Path)
```

Test export_single with directory as output path.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_export_separate_creates_multiple_pdfs`

```python
def test_export_separate_creates_multiple_pdfs(mock_html_class, sample_wiki: Path, tmp_path: Path)
```

Test that export_separate creates multiple PDF files.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_export_separate_preserves_directory_structure`

```python
def test_export_separate_preserves_directory_structure(mock_html_class, sample_wiki: Path, tmp_path: Path)
```

Test that export_separate preserves directory structure.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `sample_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |


### class `TestExportToPdf`

Tests for the export_to_pdf convenience function.

**Methods:**

#### `simple_wiki`

```python
def simple_wiki(tmp_path: Path) -> Path
```

Create a simple wiki for testing.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |

#### `test_raises_for_nonexistent_wiki`

```python
def test_raises_for_nonexistent_wiki(tmp_path: Path)
```

Test that export raises for nonexistent wiki path.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | `Path` | - | - |

#### `test_default_output_path_single`

```python
def test_default_output_path_single(mock_html_class, simple_wiki: Path)
```

Test default output path for single file mode.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `simple_wiki` | `Path` | - | - |

#### `test_default_output_path_separate`

```python
def test_default_output_path_separate(mock_html_class, simple_wiki: Path)
```

Test default output path for separate file mode.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `simple_wiki` | `Path` | - | - |

#### `test_custom_output_path`

```python
def test_custom_output_path(mock_html_class, simple_wiki: Path, tmp_path: Path)
```

Test custom output path.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `simple_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |

#### `test_string_paths_accepted`

```python
def test_string_paths_accepted(mock_html_class, simple_wiki: Path, tmp_path: Path)
```

Test that string paths are accepted.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_html_class` | - | - | - |
| `simple_wiki` | `Path` | - | - |
| `tmp_path` | `Path` | - | - |


### class `TestPrintCss`

Tests for print CSS content.

**Methods:**

#### `test_print_css_has_page_rules`

```python
def test_print_css_has_page_rules()
```

Test that print CSS has @page rules.

#### `test_print_css_has_page_numbers`

```python
def test_print_css_has_page_numbers()
```

Test that print CSS includes page numbers.

#### `test_print_css_avoids_page_breaks_in_code`

```python
def test_print_css_avoids_page_breaks_in_code()
```

Test that print CSS avoids page breaks inside code blocks.

#### `test_print_css_keeps_headings_with_content`

```python
def test_print_css_keeps_headings_with_content()
```

Test that print CSS keeps headings with following content.


### class `TestMermaidHandling`

Tests for mermaid diagram handling in PDF export without CLI.

**Methods:**

#### `test_mermaid_replaced_with_note`

```python
def test_mermaid_replaced_with_note()
```

Test that mermaid diagrams are replaced with a note when CLI unavailable.

#### `test_regular_code_blocks_preserved`

```python
def test_regular_code_blocks_preserved()
```

Test that regular code blocks are preserved.

#### `test_mixed_code_blocks`

```python
def test_mixed_code_blocks()
```

Test document with both mermaid and regular code blocks.


### class `TestExtractMermaidBlocks`

Tests for mermaid block extraction.

**Methods:**

#### `test_extract_single_block`

```python
def test_extract_single_block()
```

Test extracting a single mermaid block.

#### `test_extract_multiple_blocks`

```python
def test_extract_multiple_blocks()
```

Test extracting multiple mermaid blocks.

#### `test_no_mermaid_blocks`

```python
def test_no_mermaid_blocks()
```

Test content with no mermaid blocks.

#### `test_diagram_code_stripped`

```python
def test_diagram_code_stripped()
```

Test that diagram code is stripped of whitespace.


### class `TestIsMmdcAvailable`

Tests for mermaid CLI availability check.

**Methods:**

#### `test_mmdc_available`

```python
def test_mmdc_available(mock_which)
```

Test when mmdc is available.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_which` | - | - | - |

#### `test_mmdc_not_available`

```python
def test_mmdc_not_available(mock_which)
```

Test when mmdc is not available.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_which` | - | - | - |

#### `test_result_is_cached`

```python
def test_result_is_cached(mock_which)
```

Test that the result is cached.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_which` | - | - | - |


### class `TestRenderMermaidToSvg`

Tests for mermaid to SVG rendering.

**Methods:**

#### `test_returns_none_when_mmdc_unavailable`

```python
def test_returns_none_when_mmdc_unavailable(mock_available)
```

Test that None is returned when mmdc is not available.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |

#### `test_renders_svg_successfully`

```python
def test_renders_svg_successfully(mock_available, mock_run, tmp_path)
```

Test successful SVG rendering.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |
| `mock_run` | - | - | - |
| `tmp_path` | - | - | - |

#### `test_returns_none_on_cli_error`

```python
def test_returns_none_on_cli_error(mock_available, mock_run)
```

Test that None is returned on CLI error.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |
| `mock_run` | - | - | - |

#### `test_handles_timeout`

```python
def test_handles_timeout(mock_available)
```

Test that timeout is handled gracefully.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |


### class `TestRenderMermaidToPng`

Tests for mermaid to PNG rendering.

**Methods:**

#### `test_returns_none_when_mmdc_unavailable`

```python
def test_returns_none_when_mmdc_unavailable(mock_available)
```

Test that None is returned when mmdc is not available.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |

#### `test_returns_none_on_cli_error`

```python
def test_returns_none_on_cli_error(mock_available, mock_run)
```

Test that None is returned on CLI error.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |
| `mock_run` | - | - | - |

#### `test_handles_timeout`

```python
def test_handles_timeout(mock_available)
```

Test that timeout is handled gracefully.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |


### class `TestMermaidCliRendering`

Tests for mermaid rendering with CLI available (uses PNG).

**Methods:**

#### `test_renders_mermaid_when_cli_available`

```python
def test_renders_mermaid_when_cli_available(mock_available, mock_render)
```

Test that mermaid diagrams are rendered as PNG when CLI is available.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |
| `mock_render` | - | - | - |

#### `test_falls_back_on_render_failure`

```python
def test_falls_back_on_render_failure(mock_available, mock_render)
```

Test fallback to placeholder when render fails.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |
| `mock_render` | - | - | - |

#### `test_renders_multiple_diagrams`

```python
def test_renders_multiple_diagrams(mock_available, mock_render)
```

Test rendering multiple mermaid diagrams as PNG.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_available` | - | - | - |
| `mock_render` | - | - | - |



## Class Diagram

```mermaid
classDiagram
    class TestExportToPdf {
        +simple_wiki() -> Path
        +test_raises_for_nonexistent_wiki()
        +test_default_output_path_single()
        +test_default_output_path_separate()
        +test_custom_output_path()
        +test_string_paths_accepted()
    }
    class TestExtractMermaidBlocks {
        +test_extract_single_block()
        +test_extract_multiple_blocks()
        +test_no_mermaid_blocks()
        +foo()
        +test_diagram_code_stripped()
    }
    class TestExtractTitle {
        +test_h1_title()
        +test_bold_title()
        +test_fallback_to_filename()
        +test_h1_with_leading_whitespace()
    }
    class TestIsMmdcAvailable {
        +test_mmdc_available()
        +test_mmdc_not_available()
        +test_result_is_cached()
    }
    class TestMermaidCliRendering {
        +test_renders_mermaid_when_cli_available()
        +test_falls_back_on_render_failure()
        +test_renders_multiple_diagrams()
    }
    class TestMermaidHandling {
        +test_mermaid_replaced_with_note()
        +test_regular_code_blocks_preserved()
        +hello()
        +test_mixed_code_blocks()
        +foo()
    }
    class TestPdfExporter {
        +sample_wiki(tmp_path: Path) Path
        +test_collect_pages_in_order(sample_wiki: Path, tmp_path: Path)
        +test_extract_paths_from_toc(sample_wiki: Path, tmp_path: Path)
        +test_build_toc_html(sample_wiki: Path, tmp_path: Path)
        +test_export_single_creates_pdf(mock_html_class, sample_wiki: Path, tmp_path: Path)
        +test_export_single_with_directory_output(mock_html_class, sample_wiki: Path, tmp_path: Path)
        +test_export_separate_creates_multiple_pdfs(mock_html_class, sample_wiki: Path, tmp_path: Path)
        +test_export_separate_preserves_directory_structure(mock_html_class, sample_wiki: Path, tmp_path: Path)
    }
    class TestPrintCss {
        +test_print_css_has_page_rules()
        +test_print_css_has_page_numbers()
        +test_print_css_avoids_page_breaks_in_code()
        +test_print_css_keeps_headings_with_content()
    }
    class TestRenderMarkdownForPdf {
        +test_basic_markdown()
        +test_code_blocks()
        +hello()
        +test_tables()
        +test_mermaid_blocks_replaced_with_note()
        +test_multiple_mermaid_blocks()
    }
    class TestRenderMermaidToPng {
        +test_returns_none_when_mmdc_unavailable()
        +test_returns_none_on_cli_error()
        +test_handles_timeout()
    }
    class TestRenderMermaidToSvg {
        +test_returns_none_when_mmdc_unavailable()
        +test_renders_svg_successfully()
        +test_returns_none_on_cli_error()
        +test_handles_timeout()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[MagicMock]
    N1[PdfExporter]
    N2[TestExportToPdf.simple_wiki]
    N3[TestExportToPdf.test_raises...]
    N4[TestExtractTitle.test_bold_...]
    N5[TestExtractTitle.test_fallb...]
    N6[TestExtractTitle.test_h1_title]
    N7[TestExtractTitle.test_h1_wi...]
    N8[TestPdfExporter.sample_wiki]
    N9[TestPdfExporter.test_build_...]
    N10[TestPdfExporter.test_collec...]
    N11[TestPdfExporter.test_export...]
    N12[TestPdfExporter.test_export...]
    N13[TestPdfExporter.test_export...]
    N14[TestPdfExporter.test_export...]
    N15[TestPdfExporter.test_extrac...]
    N16[TestRenderMermaidToPng.test...]
    N17[TestRenderMermaidToSvg.test...]
    N18[assert_called_once]
    N19[export_separate]
    N20[export_single]
    N21[export_to_pdf]
    N22[extract_mermaid_blocks]
    N23[extract_title]
    N24[is_mmdc_available]
    N25[mkdir]
    N26[render_markdown_for_pdf]
    N27[render_mermaid_to_png]
    N28[render_mermaid_to_svg]
    N29[write_text]
    N6 --> N29
    N6 --> N23
    N4 --> N29
    N4 --> N23
    N5 --> N29
    N5 --> N23
    N7 --> N29
    N7 --> N23
    N8 --> N25
    N8 --> N29
    N10 --> N1
    N15 --> N1
    N9 --> N1
    N13 --> N0
    N13 --> N1
    N13 --> N20
    N13 --> N18
    N14 --> N25
    N14 --> N0
    N14 --> N1
    N14 --> N20
    N11 --> N0
    N11 --> N1
    N11 --> N19
    N12 --> N0
    N12 --> N1
    N12 --> N19
    N2 --> N25
    N2 --> N29
    N3 --> N21
    N17 --> N28
    N16 --> N27
    classDef func fill:#e1f5fe
    class N0,N1,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17 method
```

## Relevant Source Files

- `tests/test_pdf_export.py:21-80`

## See Also

- [test_indexer](test_indexer.md) - shares 4 dependencies
