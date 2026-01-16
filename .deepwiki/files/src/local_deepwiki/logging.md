# logging.py

## File Overview

The logging module provides centralized logging configuration for the local-deepwiki package. It offers a flexible logging setup with support for different output formats, multiple destinations (console and file), and environment-based configuration.

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

Configure logging for the local-deepwiki package with customizable options for level, format, and output destinations.

**Parameters:**
- `level` (str | int | None): Log level such as DEBUG, INFO, WARNING, ERROR, or CRITICAL. Defaults to INFO, or uses the `DEEPWIKI_LOG_LEVEL` environment variable if set
- `format_style` (Literal["simple", "detailed"]): Formatting style - "simple" for basic format or "detailed" for format including file and line information
- `stream` (bool): Whether to enable logging to stderr. Defaults to True
- `log_file` (str | None): Optional file path for file-based logging

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

### File and Console Logging

```python
# Log to both console and file
logger = setup_logging(
    level="INFO",
    format_style="detailed",
    stream=True,
    log_file="app.log"
)

# Log only to file
logger = setup_logging(
    stream=False,
    log_file="app.log"
)
```

### Environment-Based Configuration

The setup_logging function respects the `DEEPWIKI_LOG_LEVEL` environment variable for default log level configuration, allowing external control of logging verbosity without code changes.

## Related Components

This module uses Python's standard `logging` library and integrates with the `os` and `sys` modules for environment variable access and stream handling. The typing module provides type hints for the format style parameter.

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



<details>
<summary>View Source (lines 18-72) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/wiki-enhancements/src/local_deepwiki/logging.py#L18-L72">GitHub</a></summary>

```python
def setup_logging(
    level: str | int | None = None,
    format_style: Literal["simple", "detailed"] = "simple",
    stream: bool = True,
    log_file: str | None = None,
) -> logging.Logger:
    """Configure logging for the local-deepwiki package.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to INFO, or DEEPWIKI_LOG_LEVEL env var.
        format_style: "simple" for basic format, "detailed" for file/line info.
        stream: Whether to log to stderr.
        log_file: Optional file path for logging.

    Returns:
        The configured root logger for the package.
    """
    # Determine log level
    if level is None:
        level = os.environ.get("DEEPWIKI_LOG_LEVEL", "INFO")

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # At this point level is guaranteed to be an int
    log_level: int = level if isinstance(level, int) else logging.INFO

    # Get the package logger
    logger = logging.getLogger(PACKAGE_NAME)
    logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Choose format
    log_format = LOG_FORMAT_DETAILED if format_style == "detailed" else LOG_FORMAT
    formatter = logging.Formatter(log_format)

    # Add stream handler
    if stream:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Don't propagate to root logger
    logger.propagate = False

    return logger
```

</details>

#### `get_logger`

```python
def get_logger(name: str) -> logging.Logger
```

Get a logger for a specific module.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | - | Module name (typically __name__). |

**Returns:** `logging.Logger`




<details>
<summary>View Source (lines 75-89) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/wiki-enhancements/src/local_deepwiki/logging.py#L75-L89">GitHub</a></summary>

```python
def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger instance for the module.
    """
    # If name starts with the package name, use it directly
    if name.startswith(PACKAGE_NAME):
        return logging.getLogger(name)

    # Otherwise, prefix with package name
    return logging.getLogger(f"{PACKAGE_NAME}.{name}")
```

</details>

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

## Used By

Functions and methods in this file and their callers:

- **`FileHandler`**: called by `setup_logging`
- **`Formatter`**: called by `setup_logging`
- **`StreamHandler`**: called by `setup_logging`
- **`addHandler`**: called by `setup_logging`
- **`getLogger`**: called by `get_logger`, `setup_logging`
- **`setFormatter`**: called by `setup_logging`
- **`setLevel`**: called by `setup_logging`

## Relevant Source Files

- `src/local_deepwiki/logging.py:18-72`

## See Also

- [vectorstore](core/vectorstore.md) - uses this
- [chunker](core/chunker.md) - uses this
- [test_examples](generators/test_examples.md) - uses this
- [git_utils](core/git_utils.md) - uses this
