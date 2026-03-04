"""Provider and diagram type enums used by tool argument models."""

from __future__ import annotations

from enum import StrEnum


class LLMProviderType(StrEnum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GROK = "grok"


class EmbeddingProviderType(StrEnum):
    """Supported embedding providers."""

    LOCAL = "local"
    OPENAI = "openai"


class DiagramType(StrEnum):
    """Types of diagrams that can be generated."""

    CLASS = "class"
    DEPENDENCY = "dependency"
    MODULE = "module"
    SEQUENCE = "sequence"
    LANGUAGE_PIE = "language_pie"


class CodemapFocusType(StrEnum):
    """Focus modes for codemap generation."""

    EXECUTION_FLOW = "execution_flow"
    DATA_FLOW = "data_flow"
    DEPENDENCY_CHAIN = "dependency_chain"
