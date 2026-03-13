"""Shared helpers for wiki output quality tests."""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from local_deepwiki.providers.base import EmbeddingProvider, LLMProvider


class DeterministicLLMProvider(LLMProvider):
    """LLM provider that returns template-based markdown.

    Returns predictable content based on prompt keywords so that
    wiki pages have real markdown structure without calling an actual LLM.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Return template-based markdown based on prompt keywords."""
        lower = prompt.lower()
        if "overview" in lower or "module" in lower:
            return (
                "## Module Purpose\n\n"
                "This module provides core functionality.\n\n"
                "## Key Classes and Functions\n\n"
                "- **MainClass** - Primary class\n\n"
                "## How Components Interact\n\n"
                "Components work together via imports.\n\n"
                "## Usage Examples\n\n"
                "```python\nfrom module import MainClass\n```\n\n"
                "## Dependencies\n\n"
                "Depends on standard library."
            )
        if "architecture" in lower:
            return (
                "## System Overview\n\n"
                "The system follows a modular architecture.\n\n"
                "## Key Components\n\n"
                "- Parser\n- Models\n- Processor"
            )
        if "file" in lower:
            return (
                "## File Overview\n\n"
                "This file contains implementation details.\n\n"
                "## Key Functions\n\n"
                "- main function"
            )
        return "## Documentation\n\nGenerated content."

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield the full response as a single chunk."""
        result = await self.generate(
            prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        yield result

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "deterministic:test"


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that returns hash-based vectors.

    Produces deterministic, fixed-dimension vectors by hashing the input text.
    This enables real vector store operations without a model download.
    """

    def __init__(self, dim: int = 384) -> None:
        self._dimension = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate hash-based embedding vectors."""
        return [self._hash_to_vector(t) for t in texts]

    @property
    def dimension(self) -> int:
        """Embedding vector dimensionality."""
        return self._dimension

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "deterministic:hash"

    def _hash_to_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        # Extend hash to fill dimension
        extended = h * ((self._dimension * 4 // len(h)) + 1)
        floats = struct.unpack(f"{self._dimension}f", extended[: self._dimension * 4])
        # Normalize to [-1, 1] range
        max_val = max(abs(f) for f in floats) or 1.0
        return [f / max_val for f in floats]


# Bad patterns that should never appear in wiki output
BAD_PATTERNS = [
    (re.compile(r"<MagicMock\b"), "MagicMock object reference"),
    (re.compile(r"<Mock\b"), "Mock object reference"),
    (re.compile(r"<AsyncMock\b"), "AsyncMock object reference"),
    (re.compile(r"<[A-Z][a-zA-Z]+ .* id='[0-9]+'"), "Python object repr"),
    (re.compile(r"name='mock\.\w+"), "Mock attribute reference"),
    (re.compile(r"^## None$", re.MULTILINE), "None as heading"),
    (re.compile(r"^- None$", re.MULTILINE), "None as list item"),
]


def scan_page_for_quality_issues(content: str, page_path: str) -> list[str]:
    """Scan a wiki page for common quality issues.

    Args:
        content: Markdown content of the page.
        page_path: Path of the page (for error messages).

    Returns:
        List of issue descriptions. Empty if no issues found.
    """
    issues: list[str] = []

    # Check bad patterns (skip content inside code blocks)
    non_code = _strip_code_blocks(content)
    for pattern, description in BAD_PATTERNS:
        if pattern.search(non_code):
            issues.append(f"{page_path}: {description} found in content")

    # Check for empty sections (heading followed immediately by heading)
    # Use non_code to avoid false positives from Python comments in code blocks
    nc_lines = non_code.split("\n")
    for i in range(len(nc_lines) - 1):
        if nc_lines[i].startswith("#") and nc_lines[i + 1].startswith("#"):
            issues.append(f"{page_path}: Empty section: {nc_lines[i].strip()}")

    # Check for unclosed mermaid blocks
    mermaid_opens = content.count("```mermaid")
    total_closes = content.count("```")
    # Each mermaid block needs an open + close = 2 backtick-triples
    if mermaid_opens > 0 and total_closes < mermaid_opens * 2:
        issues.append(f"{page_path}: Possibly unclosed mermaid block")

    return issues


def _strip_code_blocks(content: str) -> str:
    """Remove fenced code blocks from markdown content."""
    return re.sub(r"```[\s\S]*?```", "", content)


def extract_markdown_links(content: str) -> list[tuple[str, str]]:
    """Extract all markdown links from content.

    Returns:
        List of (link_text, link_target) tuples.
    """
    return re.findall(r"\[([^\]]*)\]\(([^)]+)\)", content)


def find_broken_links(wiki_path: Path) -> list[tuple[str, str, str]]:
    """Find all broken internal links across wiki pages.

    Args:
        wiki_path: Path to the .deepwiki directory.

    Returns:
        List of (source_page, link_text, broken_target) tuples.
    """
    broken: list[tuple[str, str, str]] = []

    for md_file in wiki_path.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        page_rel = str(md_file.relative_to(wiki_path))
        page_dir = md_file.parent

        # Strip code blocks to avoid false positives from template links
        content_no_code = _strip_code_blocks(content)

        for link_text, link_target in extract_markdown_links(content_no_code):
            # Skip external links, anchors, and mailto
            if link_target.startswith(("http://", "https://", "#", "mailto:")):
                continue

            # Strip anchor from target
            target_path = link_target.split("#")[0]
            if not target_path:
                continue

            # Resolve relative to page's directory
            resolved = (page_dir / target_path).resolve()
            if not resolved.exists():
                broken.append((page_rel, link_text, link_target))

    return broken
