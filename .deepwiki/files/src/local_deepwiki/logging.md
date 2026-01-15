# logging.py

## File Overview

This module provides logging configuration functionality for the local-deepwiki package. It contains utilities to set up and configure loggers with customizable output formats, levels, and destinations.

## Functions

### setup_logging

```python
def setup_logging(
    level: str | int | None = None,
    format_style: Literal["simple", "detailed"] = "simple",
    stream: bool = True,
    log_file: str | None = None,
) -> logging.Logger
```

Configures logging for the local-deepwiki package with flexible options for output format and destination.

**Parameters:**
- `level` (str | int | None): Log level specification (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO, or uses the DEEPWIKI_LOG_LEVEL environment variable if set
- `format_style` (Literal["simple", "detailed"]): Format style for log messages. "simple" provides basic formatting, while "detailed" includes file and line information
- `stream` (bool): Whether to enable logging to stderr. Defaults to True
- `log_file` (str | None): Optional file path for writing log output to a file

**Returns:**
- `logging.Logger`: The configured logger instance

### get_logger

A function for retrieving logger instances (signature not fully visible in the provided code).

## Usage Examples

### Basic Logging Setup

```python
from local_deepwiki.logging import setup_logging

# Simple setup with default INFO level
logger = setup_logging()

# Setup with specific log level
logger = setup_logging(level="DEBUG")

# Setup with detailed formatting
logger = setup_logging(format_style="detailed")
```

### File and Stream Logging

```python
# Log to both stderr and a file
logger = setup_logging(
    level="WARNING",
    format_style="detailed",
    stream=True,
    log_file="app.log"
)

# Log only to file
logger = setup_logging(
    stream=False,
    log_file="debug.log"
)
```

### Environment Variable Configuration

The setup_logging function respects the `DEEPWIKI_LOG_LEVEL` environment variable for default log level configuration when no explicit level is provided.

## Related Components

This module uses Python's standard `logging` module and integrates with the broader local-deepwiki package ecosystem. It provides the logging infrastructure that other components in the package can utilize for consistent log output formatting and management.

## API Reference

### Functions

#### `setup_logging`

```python
def setup_logging(level: str | int | None = None, format_style: Literal["simple", "detailed"] = "simple", stream: bool = True, log_file: str | None = None) -> logging.Logger
```

Configure logging for the local-deepwiki package.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | `str | int | None` | `None` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO, or DEEPWIKI_LOG_LEVEL env var. |
| `format_style` | `Literal["simple", "detailed"]` | `"simple"` | "simple" for basic format, "detailed" for file/line info. |
| `stream` | `bool` | `True` | Whether to log to stderr. |
| `log_file` | `str | None` | `None` | Optional file path for logging. |

**Returns:** `logging.Logger`


#### `get_logger`

```python
def get_logger(name: str) -> logging.Logger
```

Get a logger for a specific module.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | - | Module name (typically __name__). |

**Returns:** `logging.Logger`



## Call Graph

```mermaid
flowchart TD
    N0[FileHandler]
    N1[Formatter]
    N2[StreamHandler]
    N3[addHandler]
    N4[getLogger]
    N5[get_logger]
    N6[setFormatter]
    N7[setLevel]
    N8[setup_logging]
    N8 --> N4
    N8 --> N7
    N8 --> N1
    N8 --> N2
    N8 --> N6
    N8 --> N3
    N8 --> N0
    N5 --> N4
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8 func
```

## Relevant Source Files

- `src/local_deepwiki/logging.py:19-70`

## See Also

- [llm_cache](core/llm_cache.md) - uses this
- [git_utils](core/git_utils.md) - uses this
- [test_examples](generators/test_examples.md) - uses this
- [chunker](core/chunker.md) - uses this
- [vectorstore](core/vectorstore.md) - uses this
