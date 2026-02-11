"""Provider and diagram type enums used by tool argument models."""

from __future__ import annotations

from enum import Enum


class LLMProviderType(str, Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class EmbeddingProviderType(str, Enum):
    """Supported embedding providers."""

    LOCAL = "local"
    OPENAI = "openai"


class DiagramType(str, Enum):
    """Types of diagrams that can be generated."""

    CLASS = "class"
    DEPENDENCY = "dependency"
    MODULE = "module"
    SEQUENCE = "sequence"
    LANGUAGE_PIE = "language_pie"


class CodemapFocusType(str, Enum):
    """Focus modes for codemap generation."""

    EXECUTION_FLOW = "execution_flow"
    DATA_FLOW = "data_flow"
    DEPENDENCY_CHAIN = "dependency_chain"
