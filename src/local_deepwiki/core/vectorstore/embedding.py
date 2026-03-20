"""Embedding batch processing with retry, deduplication, and rate limiting."""

from __future__ import annotations

import asyncio
import random
from operator import attrgetter

from local_deepwiki.config import EmbeddingBatchConfig
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import EmbeddingProvider

from .schema import BatchEmbeddingResult, EmbeddingProgress
from .utils import RateLimiter

logger = get_logger(__name__)


def is_local_provider(embedding_provider: EmbeddingProvider) -> bool:
    """Check if the embedding provider is local (sentence-transformers).

    Args:
        embedding_provider: The embedding provider to check.

    Returns:
        True if provider is local, False for API-based providers.
    """
    provider_name = embedding_provider.name.lower()
    return provider_name.startswith("local:") or "sentence" in provider_name


def get_optimal_batch_config(
    config: EmbeddingBatchConfig,
    embedding_provider: EmbeddingProvider,
) -> tuple[int, int]:
    """Get optimal batch size and concurrency based on provider type.

    Args:
        config: Embedding batch configuration.
        embedding_provider: The embedding provider.

    Returns:
        Tuple of (batch_size, concurrency).
    """
    is_local = is_local_provider(embedding_provider)

    batch_size = config.batch_size
    concurrency = config.concurrency

    if is_local:
        batch_size = max(batch_size, 100)
        concurrency = max(concurrency, 4)
    else:
        batch_size = min(batch_size, 50)
        concurrency = min(concurrency, 4)

    return batch_size, concurrency


def _is_retryable_error(e: Exception) -> bool:
    """Determine if an embedding error is retryable."""
    error_str = str(e).lower()
    return (
        isinstance(e, (ConnectionError, TimeoutError, OSError))
        or ("rate" in error_str and "limit" in error_str)
        or "overloaded" in error_str
        or "503" in error_str
        or "502" in error_str
        or "timeout" in error_str
    )


def _handle_batch_error(
    e: Exception,
    batch_index: int,
    retry_count: int,
    config: EmbeddingBatchConfig,
    progress: EmbeddingProgress,
) -> tuple[bool, float]:
    """Handle a batch embedding error — decide whether to retry and compute delay.

    Args:
        e: The exception that occurred.
        batch_index: Batch index for logging.
        retry_count: Current retry count (already incremented).
        config: Embedding batch configuration.
        progress: Progress tracker.

    Returns:
        Tuple of (should_retry, delay_seconds). If should_retry is False, the
        caller should return a failed BatchEmbeddingResult.
    """
    if not _is_retryable_error(e) or retry_count >= config.retry_max_attempts:
        logger.warning(
            "Batch %d failed after %d attempts: %s",
            batch_index,
            retry_count,
            e,
        )
        progress.update(success=False)
        return False, 0.0

    delay = config.retry_base_delay * (2 ** (retry_count - 1))
    delay = delay * (0.5 + random.random())
    logger.warning(
        "Batch %d failed (attempt %d): %s. Retrying in %.2fs...",
        batch_index,
        retry_count,
        e,
        delay,
    )
    return True, delay


async def embed_single_batch_with_retry(
    batch_index: int,
    texts: list[str],
    embedding_provider: EmbeddingProvider,
    config: EmbeddingBatchConfig,
    *,
    rate_limiter: RateLimiter | None,
    progress: EmbeddingProgress,
    semaphore: asyncio.Semaphore,
) -> BatchEmbeddingResult:
    """Embed a single batch with retry logic and rate limiting.

    Args:
        batch_index: Index of this batch for ordering results.
        texts: Texts to embed in this batch.
        embedding_provider: Provider for generating embeddings.
        config: Embedding batch configuration.
        rate_limiter: Optional rate limiter for API calls.
        progress: Progress tracker to update.
        semaphore: Semaphore for concurrency control.

    Returns:
        BatchEmbeddingResult with embeddings or error.
    """
    retry_count = 0

    async with semaphore:
        while retry_count < config.retry_max_attempts:
            try:
                if rate_limiter is not None:
                    await rate_limiter.acquire()

                embeddings = await embedding_provider.embed(texts)
                progress.update(success=True)

                return BatchEmbeddingResult(
                    batch_index=batch_index,
                    embeddings=embeddings,
                    retry_count=retry_count,
                )

            except (
                ConnectionError,
                TimeoutError,
                OSError,
                RuntimeError,
                ValueError,
            ) as e:
                retry_count += 1
                should_retry, delay = _handle_batch_error(
                    e, batch_index, retry_count, config, progress
                )
                if not should_retry:
                    return BatchEmbeddingResult(
                        batch_index=batch_index,
                        embeddings=None,
                        error=e,
                        retry_count=retry_count,
                    )
                await asyncio.sleep(delay)

    progress.update(success=False)
    return BatchEmbeddingResult(
        batch_index=batch_index,
        embeddings=None,
        error=RuntimeError("Unexpected: exhausted retries without returning"),
        retry_count=retry_count,
    )


def _deduplicate_texts(texts: list[str]) -> tuple[list[str], dict[str, int]]:
    """Return unique texts and a mapping from text to its unique index."""
    unique_texts: list[str] = []
    text_to_index: dict[str, int] = {}
    for text in texts:
        if text not in text_to_index:
            text_to_index[text] = len(unique_texts)
            unique_texts.append(text)
    return unique_texts, text_to_index


def _split_into_batches(texts: list[str], batch_size: int) -> list[list[str]]:
    """Split a list of texts into fixed-size batches."""
    return [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]


def _remap_embeddings(
    unique_embeddings: list[list[float]],
    texts: list[str],
    text_to_index: dict[str, int],
) -> list[list[float]]:
    """Remap unique embeddings back to the original (possibly duplicate) text order.

    Args:
        unique_embeddings: Embeddings for the deduplicated unique texts.
        texts: Original input texts (may contain duplicates).
        text_to_index: Mapping from text string to its index in unique_embeddings.

    Returns:
        Embeddings in the same order as the original ``texts`` list.
    """
    return [unique_embeddings[text_to_index[t]] for t in texts]


async def _embed_single_batch(
    batch_texts: list[str],
    embedding_provider: EmbeddingProvider,
    config: EmbeddingBatchConfig,
    rate_limiter: RateLimiter | None,
    *,
    log_progress: bool,
) -> list[list[float]]:
    """Embed a single batch using the fast path (no parallel overhead).

    Args:
        batch_texts: Texts that form the single batch.
        embedding_provider: Provider for generating embeddings.
        config: Embedding batch configuration.
        rate_limiter: Optional rate limiter for API calls.
        log_progress: Whether to log a completion message.

    Returns:
        List of embedding vectors for the batch texts.

    Raises:
        RuntimeError: If the batch fails after all retry attempts.
    """
    progress = EmbeddingProgress(total_texts=len(batch_texts), total_batches=1)
    semaphore = asyncio.Semaphore(1)
    result = await embed_single_batch_with_retry(
        0,
        batch_texts,
        embedding_provider,
        config,
        rate_limiter=rate_limiter,
        progress=progress,
        semaphore=semaphore,
    )
    if result.error is not None:
        raise RuntimeError(f"Failed to embed batch: {result.error}")
    if log_progress:
        logger.debug("Embedded 1/1 batches (%s unique texts)", len(batch_texts))
    return result.embeddings or []


def _merge_batch_results(
    results: list[BatchEmbeddingResult],
    total_batches: int,
) -> list[list[float]]:
    """Collect embeddings from sorted batch results, raising on any failure.

    Args:
        results: List of BatchEmbeddingResult objects (already sorted by batch_index).
        total_batches: Total number of batches (for error messages).

    Returns:
        Flat list of embeddings in batch order.

    Raises:
        RuntimeError: If any batch failed.
    """
    errors: list[tuple[int, Exception]] = []
    all_embeddings: list[list[float]] = []

    for result in results:
        if result.error is not None:
            errors.append((result.batch_index, result.error))
        elif result.embeddings is not None:
            all_embeddings.extend(result.embeddings)

    if errors:
        error_msgs = [f"Batch {idx}: {err}" for idx, err in errors]
        logger.error(
            "Embedding failed for %s batches:\n%s", len(errors), "\n".join(error_msgs)
        )
        raise RuntimeError(
            f"Failed to embed {len(errors)} out of {total_batches} batches. "
            f"First error: {errors[0][1]}"
        )

    return all_embeddings


async def batch_embed(
    texts: list[str],
    embedding_provider: EmbeddingProvider,
    config: EmbeddingBatchConfig,
    rate_limiter: RateLimiter | None,
    *,
    batch_size: int | None = None,
    log_progress: bool = False,
) -> list[list[float]]:
    """Generate embeddings in parallel batches with deduplication.

    Uses concurrent batch processing for faster embedding generation.
    For local providers, uses higher concurrency. For API providers,
    respects rate limits and uses lower concurrency.

    Args:
        texts: List of text strings to embed.
        embedding_provider: Provider for generating embeddings.
        config: Embedding batch configuration.
        rate_limiter: Optional rate limiter for API calls.
        batch_size: Number of texts to embed per batch. If None, uses config default.
        log_progress: Whether to log batch progress.

    Returns:
        List of embedding vectors in the same order as input texts.

    Raises:
        RuntimeError: If any batches fail after all retry attempts.
    """
    if not texts:
        return []

    unique_texts, text_to_index = _deduplicate_texts(texts)

    duplicates_saved = len(texts) - len(unique_texts)
    if duplicates_saved > 0:
        logger.debug(
            "Embedding dedup: %d texts -> %d unique (%d duplicates skipped)",
            len(texts),
            len(unique_texts),
            duplicates_saved,
        )

    optimal_batch_size, optimal_concurrency = get_optimal_batch_config(
        config, embedding_provider
    )
    batch_size = batch_size or optimal_batch_size

    batches = _split_into_batches(unique_texts, batch_size)
    total_batches = len(batches)

    # For single batch, still use retry logic but without parallel overhead
    if total_batches == 1:
        unique_embeddings = await _embed_single_batch(
            batches[0],
            embedding_provider,
            config,
            rate_limiter,
            log_progress=log_progress,
        )
        return _remap_embeddings(unique_embeddings, texts, text_to_index)

    progress = EmbeddingProgress(
        total_texts=len(unique_texts),
        total_batches=total_batches,
    )

    if log_progress:
        logger.info(
            "Starting parallel embedding: %d unique texts in %d batches "
            "(batch_size=%d, concurrency=%d)",
            len(unique_texts),
            total_batches,
            batch_size,
            optimal_concurrency,
        )

    semaphore = asyncio.Semaphore(optimal_concurrency)

    tasks = [
        embed_single_batch_with_retry(
            i,
            batch_texts,
            embedding_provider,
            config,
            rate_limiter=rate_limiter,
            progress=progress,
            semaphore=semaphore,
        )
        for i, batch_texts in enumerate(batches)
    ]

    results: list[BatchEmbeddingResult] = await asyncio.gather(*tasks)

    if log_progress:
        progress.log_progress()

    results = sorted(results, key=attrgetter("batch_index"))

    all_embeddings = _merge_batch_results(results, total_batches)

    if log_progress:
        elapsed = progress.elapsed_seconds
        rate = len(unique_texts) / elapsed if elapsed > 0 else 0
        logger.info(
            "Embedding complete: %d unique texts in %.2fs (%.1f texts/sec)",
            len(unique_texts),
            elapsed,
            rate,
        )

    return _remap_embeddings(all_embeddings, texts, text_to_index)


async def batch_embed_sequential(
    texts: list[str],
    embedding_provider: EmbeddingProvider,
    batch_size: int,
    *,
    log_progress: bool = False,
) -> list[list[float]]:
    """Generate embeddings in sequential batches (legacy method).

    This is the original sequential implementation, kept for backward
    compatibility and testing purposes.

    Args:
        texts: List of text strings to embed.
        embedding_provider: Provider for generating embeddings.
        batch_size: Number of texts to embed per batch.
        log_progress: Whether to log batch progress.

    Returns:
        List of embedding vectors.
    """
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = await embedding_provider.embed(batch)
        embeddings.extend(batch_embeddings)
        if log_progress and len(texts) > batch_size:
            logger.debug(
                "Embedded batch %d/%d",
                i // batch_size + 1,
                (len(texts) + batch_size - 1) // batch_size,
            )
    return embeddings
