"""Custom prompt template system for local-deepwiki.

Supports loading prompts from external files with variable interpolation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Prompt file names that can be customized
PROMPT_FILES = {
    "wiki_system": "wiki_system.md",
    "research_decomposition": "research_decomposition.md",
    "research_gap_analysis": "research_gap_analysis.md",
    "research_synthesis": "research_synthesis.md",
}

# Variable pattern for template interpolation: {variable_name}
VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


class PromptTemplate:
    """A prompt template with variable interpolation support."""

    def __init__(self, template: str, source: str = "default"):
        """Initialize a prompt template.

        Args:
            template: The template string with optional {variable} placeholders.
            source: Description of where this template came from (for debugging).
        """
        self.template = template
        self.source = source

    def render(self, **variables: Any) -> str:
        """Render the template with variable substitution.

        Args:
            **variables: Variables to substitute into the template.

        Returns:
            The rendered template string.

        Example:
            template = PromptTemplate("Document the {language} code in {file_path}")
            result = template.render(language="Python", file_path="src/main.py")
        """
        result = self.template

        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))

        return result

    def get_variables(self) -> list[str]:
        """Get list of variable names used in this template.

        Returns:
            List of variable names found in the template.
        """
        return VARIABLE_PATTERN.findall(self.template)

    def __str__(self) -> str:
        """Return the raw template string."""
        return self.template


class PromptLoader:
    """Load prompt templates from files or config with fallback chain."""

    def __init__(
        self,
        custom_dir: Path | None = None,
        repo_path: Path | None = None,
    ):
        """Initialize the prompt loader.

        Args:
            custom_dir: Optional custom directory containing prompt files.
            repo_path: Optional repository path to check for .deepwiki/prompts/.
        """
        self.custom_dir = custom_dir
        self.repo_path = repo_path
        self._cache: dict[str, PromptTemplate] = {}

    def _get_search_paths(self) -> list[Path]:
        """Get ordered list of directories to search for prompt files.

        Returns:
            List of paths to check, in priority order.
        """
        paths = []

        # 1. Custom directory (highest priority)
        if self.custom_dir and self.custom_dir.exists():
            paths.append(self.custom_dir)

        # 2. Repository's .deepwiki/prompts/ directory
        if self.repo_path:
            repo_prompts = self.repo_path / ".deepwiki" / "prompts"
            if repo_prompts.exists():
                paths.append(repo_prompts)

        # 3. User's home config directory
        home_prompts = Path.home() / ".config" / "local-deepwiki" / "prompts"
        if home_prompts.exists():
            paths.append(home_prompts)

        return paths

    def load_prompt(
        self,
        name: str,
        default: str,
        provider: str | None = None,
    ) -> PromptTemplate:
        """Load a prompt template by name.

        Searches for prompt files in priority order:
        1. Custom directory (if specified)
        2. Repository's .deepwiki/prompts/
        3. User's ~/.config/local-deepwiki/prompts/
        4. Falls back to the provided default

        Provider-specific prompts can be loaded by looking for files like:
        - wiki_system.anthropic.md (provider-specific)
        - wiki_system.md (generic)

        Args:
            name: Prompt name (e.g., "wiki_system", "research_synthesis").
            default: Default prompt text if no file is found.
            provider: Optional provider name for provider-specific prompts.

        Returns:
            PromptTemplate loaded from file or default.
        """
        # Check cache first
        cache_key = f"{name}:{provider or 'default'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build list of filenames to try
        filenames_to_try = []
        if provider:
            # Provider-specific first (e.g., wiki_system.anthropic.md)
            filenames_to_try.append(f"{name}.{provider}.md")
            filenames_to_try.append(f"{name}.{provider}.txt")
        # Generic fallback
        filenames_to_try.append(f"{name}.md")
        filenames_to_try.append(f"{name}.txt")

        # Search directories in priority order
        for search_path in self._get_search_paths():
            for filename in filenames_to_try:
                prompt_file = search_path / filename
                if prompt_file.exists():
                    try:
                        content = prompt_file.read_text().strip()
                        template = PromptTemplate(
                            content,
                            source=str(prompt_file),
                        )
                        logger.debug("Loaded custom prompt '%s' from %s", name, prompt_file)
                        self._cache[cache_key] = template
                        return template
                    except OSError as e:
                        logger.warning("Failed to read prompt file %s: %s", prompt_file, e)
                        continue

        # Fall back to default
        template = PromptTemplate(default, source="built-in default")
        self._cache[cache_key] = template
        return template

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()


class PromptManager:
    """Manage prompts for wiki generation with custom template support."""

    def __init__(
        self,
        custom_dir: Path | None = None,
        repo_path: Path | None = None,
    ):
        """Initialize the prompt manager.

        Args:
            custom_dir: Optional custom directory containing prompt files.
            repo_path: Optional repository path for per-project prompts.
        """
        self.loader = PromptLoader(custom_dir=custom_dir, repo_path=repo_path)

        # Import here to avoid circular import
        from local_deepwiki.config import (
            RESEARCH_DECOMPOSITION_PROMPTS,
            RESEARCH_GAP_ANALYSIS_PROMPTS,
            RESEARCH_SYNTHESIS_PROMPTS,
            WIKI_SYSTEM_PROMPTS,
        )

        self._defaults = {
            "wiki_system": WIKI_SYSTEM_PROMPTS,
            "research_decomposition": RESEARCH_DECOMPOSITION_PROMPTS,
            "research_gap_analysis": RESEARCH_GAP_ANALYSIS_PROMPTS,
            "research_synthesis": RESEARCH_SYNTHESIS_PROMPTS,
        }

    def get_wiki_system_prompt(
        self,
        provider: str = "anthropic",
        **variables: Any,
    ) -> str:
        """Get the wiki system prompt for a provider.

        Args:
            provider: LLM provider name.
            **variables: Variables to interpolate into the template.

        Returns:
            Rendered prompt string.
        """
        default = self._defaults["wiki_system"].get(
            provider,
            self._defaults["wiki_system"]["anthropic"],
        )
        template = self.loader.load_prompt("wiki_system", default, provider)
        return template.render(**variables)

    def get_research_decomposition_prompt(
        self,
        provider: str = "anthropic",
        **variables: Any,
    ) -> str:
        """Get the research decomposition prompt for a provider.

        Args:
            provider: LLM provider name.
            **variables: Variables to interpolate into the template.

        Returns:
            Rendered prompt string.
        """
        default = self._defaults["research_decomposition"].get(
            provider,
            self._defaults["research_decomposition"]["anthropic"],
        )
        template = self.loader.load_prompt("research_decomposition", default, provider)
        return template.render(**variables)

    def get_research_gap_analysis_prompt(
        self,
        provider: str = "anthropic",
        **variables: Any,
    ) -> str:
        """Get the research gap analysis prompt for a provider.

        Args:
            provider: LLM provider name.
            **variables: Variables to interpolate into the template.

        Returns:
            Rendered prompt string.
        """
        default = self._defaults["research_gap_analysis"].get(
            provider,
            self._defaults["research_gap_analysis"]["anthropic"],
        )
        template = self.loader.load_prompt("research_gap_analysis", default, provider)
        return template.render(**variables)

    def get_research_synthesis_prompt(
        self,
        provider: str = "anthropic",
        **variables: Any,
    ) -> str:
        """Get the research synthesis prompt for a provider.

        Args:
            provider: LLM provider name.
            **variables: Variables to interpolate into the template.

        Returns:
            Rendered prompt string.
        """
        default = self._defaults["research_synthesis"].get(
            provider,
            self._defaults["research_synthesis"]["anthropic"],
        )
        template = self.loader.load_prompt("research_synthesis", default, provider)
        return template.render(**variables)


def get_prompt_manager(
    custom_dir: Path | None = None,
    repo_path: Path | None = None,
) -> PromptManager:
    """Get a prompt manager instance.

    Args:
        custom_dir: Optional custom prompts directory.
        repo_path: Optional repository path for per-project prompts.

    Returns:
        Configured PromptManager instance.
    """
    return PromptManager(custom_dir=custom_dir, repo_path=repo_path)
