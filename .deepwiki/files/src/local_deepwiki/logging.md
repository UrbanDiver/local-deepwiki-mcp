# Logging Module

## File Overview

The `logging.py` module provides centralized logging configuration for the local-deepwiki package. It offers a simple interface to set up logging with customizable levels, formats, and output destinations.

## Functions

### setup_logging

```python
def setup_logging(
    level: str | int | None = None,
    format_style: Literal["simple", "detailed"] = "simple",
    stream: bool = True,
    log_file: str | None = None,
) -> logging.Logger:
```

Configures logging for the local-deepwiki package with flexible options for different use cases.

**Parameters:**
- `level` (str | int | None): Log level specification. Accepts standard logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO, or can be overridden by the `DEEPWIKI_LOG_LEVEL` environment variable
- `format_style` (Literal["simple", "detailed"]): Output format style. "simple" provides basic log format, while "detailed" includes file and line information
- `stream` (bool): Whether to output logs to stderr. Defaults to True
- `log_file` (str | None): Optional file path for writing logs to a file

**Returns:**
- `logging.Logger`: The configured logger instance

### get_logger

The module also includes a `get_logger` function, though its complete signature and implementation details are not visible in the provided code.

## Usage Examples

### Basic Logging Setup

```python
from local_deepwiki.logging import setup_logging

# Simple logging to stderr
logger = setup_logging()

# Set specific log level
logger = setup_logging(level="DEBUG")

# Use detailed format with file/line info
logger = setup_logging(format_style="detailed")
```

### File Logging

```python
# Log to both stderr and file
logger = setup_logging(
    level="INFO",
    format_style="detailed",
    stream=True,
    log_file="deepwiki.log"
)

# Log only to file
logger = setup_logging(
    stream=False,
    log_file="deepwiki.log"
)
```

### Environment Variable Configuration

The logging level can be controlled via environment variable:

```bash
export DEEPWIKI_LOG_LEVEL=DEBUG
```

## Related Components

This module uses Python's standard `logging` library and integrates with the `os` and `sys` modules for environment variable access and stream handling. The typing module provides type hints for better code clarity and IDE support.

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

- [git_utils](core/git_utils.md) - uses this
- [server](server.md) - uses this
- [test_examples](generators/test_examples.md) - uses this
- [llm_cache](core/llm_cache.md) - uses this
- [vectorstore](core/vectorstore.md) - uses this
