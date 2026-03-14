"""Data-driven term correction for wiki content.

Fixes common factual errors in LLM-generated documentation by applying
a curated correction map. Runs as part of the postprocessing pipeline
before cross-linking.
"""

from __future__ import annotations

import re

# Data-driven correction map: wrong term -> correct term.
# Each entry represents a known LLM hallucination or common mistake.
TERM_CORRECTIONS: dict[str, str] = {
    # Protocol/framework names
    "Model Communication Protocol": "Model Context Protocol",
    "Model Completion Protocol": "Model Context Protocol",
    "Model Connection Protocol": "Model Context Protocol",
    "Multi-Context Protocol": "Model Context Protocol",
    # Tool/library names
    "tree_sitter": "tree-sitter",
    "TreeSitter": "tree-sitter",
    "Tree Sitter": "tree-sitter",
    "LanceDb": "LanceDB",
    "lancedb": "LanceDB",
    "lance db": "LanceDB",
    "Lance DB": "LanceDB",
    "Pydantic": "pydantic",
    "FastMcp": "FastMCP",
    "fastmcp": "FastMCP",
    "FASTMCP": "FastMCP",
    # Acronym expansions
    "Retrieval Augmented Generation": "retrieval-augmented generation",
    "Abstract Syntax Trees": "abstract syntax trees",
}

# Pre-compile patterns for efficiency (case-sensitive matching)
_CORRECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(re.escape(wrong)), right) for wrong, right in TERM_CORRECTIONS.items()
]


def apply_term_corrections(content: str) -> str:
    """Apply data-driven term corrections to wiki content.

    Skips content inside fenced code blocks to avoid corrupting code.

    Args:
        content: Markdown content to correct.

    Returns:
        Content with known incorrect terms replaced.
    """
    lines = content.split("\n")
    result: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Track code block boundaries
        if indent <= 3 and stripped.startswith("```"):
            if in_code_block:
                if not stripped[3:].strip():
                    in_code_block = False
            else:
                in_code_block = True
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        # Apply corrections to non-code lines
        corrected = line
        for pattern, replacement in _CORRECTION_PATTERNS:
            corrected = pattern.sub(replacement, corrected)
        result.append(corrected)

    return "\n".join(result)
