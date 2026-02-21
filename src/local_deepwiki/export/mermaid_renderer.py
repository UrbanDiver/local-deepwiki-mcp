"""Mermaid diagram rendering utilities for PDF and HTML export.

Provides functions to check for mermaid-cli (mmdc) availability,
render mermaid diagrams to PNG or SVG, and extract mermaid code
blocks from markdown content.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Default timeout for mermaid CLI rendering (seconds)
MERMAID_RENDER_TIMEOUT = 30

# Cache for mermaid CLI availability check
_mmdc_available: bool | None = None


def is_mmdc_available() -> bool:
    """Check if mermaid-cli (mmdc) is available on the system.

    Returns:
        True if mmdc is available, False otherwise.
    """
    global _mmdc_available
    if _mmdc_available is not None:
        return _mmdc_available

    _mmdc_available = shutil.which("mmdc") is not None
    if _mmdc_available:
        logger.debug("Mermaid CLI (mmdc) is available")
    else:
        logger.debug("Mermaid CLI (mmdc) not found - diagrams will use placeholder")
    return _mmdc_available


def render_mermaid_to_png(
    diagram_code: str, timeout: int = MERMAID_RENDER_TIMEOUT
) -> bytes | None:
    """Render a mermaid diagram to PNG using mermaid-cli.

    Args:
        diagram_code: The mermaid diagram code.
        timeout: Timeout in seconds for the mmdc command.

    Returns:
        PNG bytes if successful, None if rendering failed.
    """
    if not is_mmdc_available():
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_file = tmp_path / "diagram.mmd"
            output_file = tmp_path / "diagram.png"

            # Write diagram to temp file
            input_file.write_text(diagram_code)

            # Run mmdc to generate PNG (embeds fonts as pixels)
            result = subprocess.run(
                [
                    "mmdc",
                    "-i",
                    str(input_file),
                    "-o",
                    str(output_file),
                    "-b",
                    "white",  # White background for PDF
                    "-s",
                    "2",  # Scale 2x for better quality
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.warning("Mermaid CLI failed: %s", result.stderr)
                return None

            if not output_file.exists():
                logger.warning("Mermaid CLI did not produce output file")
                return None

            return output_file.read_bytes()

    except subprocess.TimeoutExpired:
        logger.warning("Mermaid CLI timed out after %ss", timeout)
        return None
    except (subprocess.SubprocessError, OSError, ValueError, UnicodeDecodeError) as e:
        # subprocess.SubprocessError: Process execution failures (CalledProcessError, etc.)
        # OSError: File system or process spawning issues
        # ValueError: Invalid diagram code or subprocess parameters
        # UnicodeDecodeError: Output decoding errors
        logger.warning("Error rendering mermaid diagram: %s", e)
        return None


def render_mermaid_to_svg(
    diagram_code: str, timeout: int = MERMAID_RENDER_TIMEOUT
) -> str | None:
    """Render a mermaid diagram to SVG using mermaid-cli.

    Note: SVG may have font issues in PDF. Use render_mermaid_to_png for PDF export.

    Args:
        diagram_code: The mermaid diagram code.
        timeout: Timeout in seconds for the mmdc command.

    Returns:
        SVG string if successful, None if rendering failed.
    """
    if not is_mmdc_available():
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_file = tmp_path / "diagram.mmd"
            output_file = tmp_path / "diagram.svg"

            # Write diagram to temp file
            input_file.write_text(diagram_code)

            # Run mmdc to generate SVG
            result = subprocess.run(
                [
                    "mmdc",
                    "-i",
                    str(input_file),
                    "-o",
                    str(output_file),
                    "-b",
                    "transparent",  # Transparent background
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.warning("Mermaid CLI failed: %s", result.stderr)
                return None

            if not output_file.exists():
                logger.warning("Mermaid CLI did not produce output file")
                return None

            svg_content = output_file.read_text()
            return svg_content

    except subprocess.TimeoutExpired:
        logger.warning("Mermaid CLI timed out after %ss", timeout)
        return None
    except (subprocess.SubprocessError, OSError, ValueError, UnicodeDecodeError) as e:
        # subprocess.SubprocessError: Process execution failures (CalledProcessError, etc.)
        # OSError: File system or process spawning issues
        # ValueError: Invalid diagram code or subprocess parameters
        # UnicodeDecodeError: Output decoding errors
        logger.warning("Error rendering mermaid diagram: %s", e)
        return None


def extract_mermaid_blocks(content: str) -> list[tuple[str, str]]:
    """Extract mermaid code blocks from markdown content.

    Args:
        content: Markdown content.

    Returns:
        List of (full_match, diagram_code) tuples.
    """
    # Match ```mermaid ... ``` blocks
    pattern = r"```mermaid\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    blocks = []
    for match in matches:
        full_block = f"```mermaid\n{match}```"
        diagram_code = match.strip()
        blocks.append((full_block, diagram_code))

    return blocks
