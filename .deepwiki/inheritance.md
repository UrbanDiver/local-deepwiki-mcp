# Class Inheritance

This page shows the class inheritance hierarchies in the codebase.

## Inheritance Diagram

```mermaid
classDiagram
    class AnthropicConfig
    class AnthropicProvider
    class CachingLLMProvider
    class ChunkType
    class ChunkingConfig
    class CodeChunk
    class Config
    class DebouncedHandler
    class DeepResearchConfig
    class DeepResearchResult
    class EmbeddingConfig
    class EmbeddingProvider {
        <<abstract>>
    }
    class FileInfo
    class IndexStatus
    class LLMCacheConfig
    class LLMConfig
    class LLMProvider {
        <<abstract>>
    }
    class Language
    class LocalEmbeddingConfig
    class LocalEmbeddingProvider
    class MockEmbeddingProvider
    class MockLLMProvider
    class OllamaConfig
    class OllamaConnectionError
    class OllamaModelNotFoundError
    class OllamaProvider
    class OpenAIEmbeddingConfig
    class OpenAIEmbeddingProvider
    class OpenAILLMConfig
    class OpenAILLMProvider
    class OutputConfig
    class ParsingConfig
    class ProgressCallback
    class PromptsConfig
    class ProviderPromptsConfig
    class ResearchCancelledError
    class ResearchPreset
    class ResearchProgress
    class ResearchProgressType
    class ResearchStep
    class ResearchStepType
    class SearchResult
    class SourceReference
    class SubQuestion
    class WikiConfig
    class WikiGenerationStatus
    class WikiPage
    class WikiPageStatus
    class WikiStructure
    AnthropicProvider --|> LLMProvider
    CachingLLMProvider --|> LLMProvider
    LocalEmbeddingProvider --|> EmbeddingProvider
    MockEmbeddingProvider --|> EmbeddingProvider
    MockLLMProvider --|> LLMProvider
    OllamaProvider --|> LLMProvider
    OpenAIEmbeddingProvider --|> EmbeddingProvider
    OpenAILLMProvider --|> LLMProvider
```

## Inheritance Trees

- **[EmbeddingProvider](files/src/local_deepwiki/providers/base.md)** (abstract) `base.py` - Abstract base class for embedding providers.
  └─ **[LocalEmbeddingProvider](files/src/local_deepwiki/providers/embeddings/local.md)** `local.py` - Embedding provider using local sentence-transformers models.
  └─ **MockEmbeddingProvider** `test_vectorstore.py` - Mock embedding provider for testing.
  └─ **[OpenAIEmbeddingProvider](files/src/local_deepwiki/providers/embeddings/openai.md)** `openai.py` - Embedding provider using OpenAI API.

- **[LLMProvider](files/src/local_deepwiki/providers/base.md)** (abstract) `base.py` - Abstract base class for LLM providers.
  └─ **[AnthropicProvider](files/src/local_deepwiki/providers/llm/anthropic.md)** `anthropic.py` - LLM provider using Anthropic API.
  └─ **[CachingLLMProvider](files/src/local_deepwiki/providers/llm/cached.md)** `cached.py` - LLM provider [wrapper](files/src/local_deepwiki/providers/base.md) that caches responses.
  └─ **MockLLMProvider** `test_deep_research.py` - Mock LLM provider for testing.
  └─ **[OllamaProvider](files/src/local_deepwiki/providers/llm/ollama.md)** `ollama.py` - LLM provider using local Ollama.
  └─ **[OpenAILLMProvider](files/src/local_deepwiki/providers/llm/openai.md)** `openai.py` - LLM provider using OpenAI API.

## All Classes

| Class | Inherits From | File |
|-------|---------------|------|
| [`AnthropicConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`AnthropicProvider`](files/src/local_deepwiki/providers/llm/anthropic.md) | [`LLMProvider`](files/src/local_deepwiki/providers/base.md) | [anthropic.py](files/src/local_deepwiki/providers/llm/anthropic.md) |
| [`CachingLLMProvider`](files/src/local_deepwiki/providers/llm/cached.md) | [`LLMProvider`](files/src/local_deepwiki/providers/base.md) | [cached.py](files/src/local_deepwiki/providers/llm/cached.md) |
| [`ChunkType`](files/src/local_deepwiki/models.md) | `str`, `Enum` | [models.py](files/src/local_deepwiki/models.md) |
| [`ChunkingConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`CodeChunk`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`Config`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`DebouncedHandler`](files/src/local_deepwiki/watcher.md) | `FileSystemEventHandler` | [watcher.py](files/src/local_deepwiki/watcher.md) |
| [`DeepResearchConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`DeepResearchResult`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`EmbeddingConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md) | `ABC` | [base.py](files/src/local_deepwiki/providers/base.md) |
| [`FileInfo`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`IndexStatus`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`LLMCacheConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`LLMConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`LLMProvider`](files/src/local_deepwiki/providers/base.md) | `ABC` | [base.py](files/src/local_deepwiki/providers/base.md) |
| [`Language`](files/src/local_deepwiki/models.md) | `str`, `Enum` | [models.py](files/src/local_deepwiki/models.md) |
| [`LocalEmbeddingConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`LocalEmbeddingProvider`](files/src/local_deepwiki/providers/embeddings/local.md) | [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md) | [local.py](files/src/local_deepwiki/providers/embeddings/local.md) |
| `MockEmbeddingProvider` | [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md) | [test_vectorstore.py](files/tests/test_vectorstore.md) |
| `MockLLMProvider` | [`LLMProvider`](files/src/local_deepwiki/providers/base.md) | [test_deep_research.py](files/tests/test_deep_research.md) |
| [`OllamaConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`OllamaConnectionError`](files/src/local_deepwiki/providers/llm/ollama.md) | `Exception` | [ollama.py](files/src/local_deepwiki/providers/llm/ollama.md) |
| [`OllamaModelNotFoundError`](files/src/local_deepwiki/providers/llm/ollama.md) | `Exception` | [ollama.py](files/src/local_deepwiki/providers/llm/ollama.md) |
| [`OllamaProvider`](files/src/local_deepwiki/providers/llm/ollama.md) | [`LLMProvider`](files/src/local_deepwiki/providers/base.md) | [ollama.py](files/src/local_deepwiki/providers/llm/ollama.md) |
| [`OpenAIEmbeddingConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`OpenAIEmbeddingProvider`](files/src/local_deepwiki/providers/embeddings/openai.md) | [`EmbeddingProvider`](files/src/local_deepwiki/providers/base.md) | [openai.py](files/src/local_deepwiki/providers/embeddings/openai.md) |
| [`OpenAILLMConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`OpenAILLMProvider`](files/src/local_deepwiki/providers/llm/openai.md) | [`LLMProvider`](files/src/local_deepwiki/providers/base.md) | [openai.py](files/src/local_deepwiki/providers/llm/openai.md) |
| [`OutputConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`ParsingConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`ProgressCallback`](files/src/local_deepwiki/models.md) | `Protocol` | [models.py](files/src/local_deepwiki/models.md) |
| [`PromptsConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`ProviderPromptsConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`ResearchCancelledError`](files/src/local_deepwiki/core/deep_research.md) | `Exception` | [deep_research.py](files/src/local_deepwiki/core/deep_research.md) |
| [`ResearchPreset`](files/src/local_deepwiki/config.md) | `str`, `Enum` | [config.py](files/src/local_deepwiki/config.md) |
| [`ResearchProgress`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`ResearchProgressType`](files/src/local_deepwiki/models.md) | `str`, `Enum` | [models.py](files/src/local_deepwiki/models.md) |
| [`ResearchStep`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`ResearchStepType`](files/src/local_deepwiki/models.md) | `str`, `Enum` | [models.py](files/src/local_deepwiki/models.md) |
| [`SearchResult`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`SourceReference`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`SubQuestion`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`WikiConfig`](files/src/local_deepwiki/config.md) | `BaseModel` | [config.py](files/src/local_deepwiki/config.md) |
| [`WikiGenerationStatus`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`WikiPage`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`WikiPageStatus`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |
| [`WikiStructure`](files/src/local_deepwiki/models.md) | `BaseModel` | [models.py](files/src/local_deepwiki/models.md) |

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_provider_factories.py:21-99`
- `tests/test_parser.py:24-123`
- `tests/test_retry.py:8-144`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-75`
- `tests/test_chunker.py:13-428`
- `tests/test_changelog.py:18-96`
- `tests/test_coverage.py:13-50`
- `tests/test_vectorstore.py:9-28`
- `tests/test_wiki_coverage.py:50-120`


*Showing 10 of 100 source files.*
