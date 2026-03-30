"""Diff-related analysis handlers: analyze_diff and ask_about_diff."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

# Git subprocess timeout values (seconds)
GIT_DIFF_TIMEOUT = 30
GIT_FILE_DIFF_TIMEOUT = 10

# Size limits for diff content
MAX_DIFF_CONTENT_LENGTH = 5000
MAX_DIFF_TEXT_LENGTH = 10000

# Maximum affected entities to return in diff analysis
MAX_AFFECTED_ENTITIES = 100

from local_deepwiki.config import get_config
from local_deepwiki.core.rate_limiter import get_rate_limiter
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import (
    ValidationError,
    path_not_found_error,
    sanitize_error_message,
)
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._index_helpers import _load_index_status
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import AnalyzeDiffArgs, AskAboutDiffArgs
from local_deepwiki.providers.embeddings import get_embedding_provider
from local_deepwiki.security import Permission, get_access_controller

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DiffSynthesisContext:
    """Immutable context for LLM-based diff answer synthesis.

    Bundles the parameters of _synthesize_diff_answer to reduce its
    parameter count from 8 to a manageable level.
    """

    question: str
    diff_text: str
    base_ref: str
    head_ref: str
    additional_context: str


# Compiled once; used by both handle_analyze_diff and handle_ask_about_diff.
_GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9_.\/\-~^]+$")


def _validate_git_refs(
    refs: list[tuple[str, str]],
) -> None:
    """Validate git ref strings to prevent injection.

    Args:
        refs: List of (field_name, ref_value) tuples.

    Raises:
        ValidationError: If any ref is invalid.
    """
    for ref_name, ref_value in refs:
        if not _GIT_REF_PATTERN.match(ref_value):
            raise ValidationError(
                message=f"Invalid git ref: {ref_value}",
                hint="Git refs must contain only alphanumeric chars, /, -, _, ~, ^, and .",
                field=ref_name,
                value=ref_value,
            )


async def _run_git_diff(
    repo_path: Path,
    base_ref: str,
    head_ref: str,
    *,
    extra_args: list[str] | None = None,
    timeout: int = GIT_DIFF_TIMEOUT,
) -> subprocess.CompletedProcess[str] | list[TextContent]:
    """Run a git diff command and return the result or an error response.

    Args:
        repo_path: Repository path.
        base_ref: Base git ref.
        head_ref: Head git ref.
        extra_args: Additional args inserted after ``head_ref``.
        timeout: Subprocess timeout in seconds.

    Returns:
        ``CompletedProcess`` on success, or ``list[TextContent]`` error response.
    """
    cmd = ["git", "diff"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend([base_ref, head_ref])

    try:
        diff_result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if diff_result.returncode != 0:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "error": f"git diff failed: {sanitize_error_message(diff_result.stderr.strip())}",
                        },
                        indent=2,
                    ),
                )
            ]
        return diff_result
    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"git diff timed out after {timeout} seconds",
                    },
                    indent=2,
                ),
            )
        ]


def _parse_diff_name_status(stdout: str) -> list[dict[str, Any]]:
    """Parse ``git diff --name-status`` output into changed-file dicts.

    Args:
        stdout: Raw stdout from the git diff command.

    Returns:
        List of dicts with ``file`` and ``status`` keys.
    """
    status_map = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
    }
    changed_files: list[dict[str, Any]] = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status_code, file_name = parts
            status = status_map.get(status_code[0], "modified")
            changed_files.append({"file": file_name, "status": status})
    return changed_files


async def _fetch_per_file_diff_content(
    repo_path: Path,
    base_ref: str,
    head_ref: str,
    changed_files: list[dict[str, Any]],
) -> None:
    """Mutate *changed_files* in-place to add ``diff_content`` per file.

    Args:
        repo_path: Repository path.
        base_ref: Base git ref.
        head_ref: Head git ref.
        changed_files: Changed-file dicts to augment.
    """
    for cf in changed_files:
        try:
            file_diff = await asyncio.to_thread(
                subprocess.run,
                [
                    "git",
                    "diff",
                    base_ref,
                    head_ref,
                    "--",
                    cf["file"],
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=GIT_FILE_DIFF_TIMEOUT,
            )
            cf["diff_content"] = file_diff.stdout[:MAX_DIFF_CONTENT_LENGTH]
        except (subprocess.TimeoutExpired, OSError):
            cf["diff_content"] = "(diff content unavailable)"


def _build_diff_summary(
    changed_files: list[dict[str, Any]],
    affected_wiki_pages: list[dict[str, str]],
    affected_entities: list[dict[str, str]],
) -> dict[str, int]:
    """Build a summary dict from diff analysis results.

    Args:
        changed_files: Changed-file dicts.
        affected_wiki_pages: Wiki pages affected by the diff.
        affected_entities: Code entities affected by the diff.

    Returns:
        Summary dict with counts.
    """
    return {
        "total_changed_files": len(changed_files),
        "added": sum(1 for f in changed_files if f["status"] == "added"),
        "modified": sum(1 for f in changed_files if f["status"] == "modified"),
        "deleted": sum(1 for f in changed_files if f["status"] == "deleted"),
        "affected_wiki_pages": len(affected_wiki_pages),
        "affected_entities": len(affected_entities),
    }


async def _build_structured_diff_result(
    repo_path: Path,
    changed_files: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Map changed files to wiki pages and entities via the index.

    Args:
        repo_path: Resolved repository path.
        changed_files: List of changed-file dicts with ``file`` and ``status`` keys.

    Returns:
        Tuple of (affected_wiki_pages, affected_entities) lists.
    """
    affected_wiki_pages: list[dict[str, str]] = []
    affected_entities: list[dict[str, str]] = []
    try:
        _index_status, wiki_path, _config = await _load_index_status(repo_path)
        changed_file_set = {cf["file"] for cf in changed_files}

        toc_path = wiki_path / "toc.json"
        if toc_path.exists():
            toc_content = await asyncio.to_thread(toc_path.read_text)
            toc_data = json.loads(toc_content)
            pages = (
                toc_data if isinstance(toc_data, list) else toc_data.get("pages", [])
            )
            for page in pages:
                source_file = page.get("source_file", "")
                if source_file in changed_file_set:
                    affected_wiki_pages.append(
                        {
                            "title": page.get("title", ""),
                            "path": page.get("path", ""),
                            "source_file": source_file,
                        }
                    )

        search_path = wiki_path / "search.json"
        if search_path.exists():
            search_content = await asyncio.to_thread(search_path.read_text)
            search_data = json.loads(search_content)
            for entity in search_data.get("entities", []):
                if entity.get("file", "") in changed_file_set:
                    affected_entities.append(
                        {
                            "name": entity.get("display_name", entity.get("name", "")),
                            "type": entity.get("entity_type", ""),
                            "file": entity.get("file", ""),
                        }
                    )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        KeyError,
        ValidationError,
    ) as e:
        logger.debug("Could not load wiki/entity mapping for diff analysis: %s", e)
    return affected_wiki_pages, affected_entities


@handle_tool_errors
async def handle_analyze_diff(args: dict[str, Any]) -> list[TextContent]:
    """Handle analyze_diff tool call.

    Analyzes git diff and maps changed files to affected wiki pages and entities.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = AnalyzeDiffArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _validate_git_refs(
        [
            ("base_ref", validated.base_ref),
            ("head_ref", validated.head_ref),
        ]
    )

    # Run git diff --name-status
    diff_result = await _run_git_diff(
        repo_path,
        validated.base_ref,
        validated.head_ref,
        extra_args=["--name-status"],
    )
    if isinstance(diff_result, list):
        return diff_result

    changed_files = _parse_diff_name_status(diff_result.stdout)

    if not changed_files:
        return make_tool_text_content(
            "analyze_diff",
            {
                "status": "success",
                "base_ref": validated.base_ref,
                "head_ref": validated.head_ref,
                "message": "No file changes found between the specified refs.",
                "changed_files": [],
                "affected_wiki_pages": [],
                "affected_entities": [],
            },
        )

    if validated.include_content:
        await _fetch_per_file_diff_content(
            repo_path,
            validated.base_ref,
            validated.head_ref,
            changed_files,
        )

    affected_wiki_pages, affected_entities = await _build_structured_diff_result(
        repo_path, changed_files
    )

    summary = _build_diff_summary(changed_files, affected_wiki_pages, affected_entities)

    result = {
        "status": "success",
        "base_ref": validated.base_ref,
        "head_ref": validated.head_ref,
        "summary": summary,
        "changed_files": changed_files,
        "affected_wiki_pages": affected_wiki_pages,
        "affected_entities": affected_entities[:MAX_AFFECTED_ENTITIES],
    }

    logger.info(
        "Diff analysis: %d files changed, %d wiki pages affected",
        len(changed_files),
        len(affected_wiki_pages),
    )
    return make_tool_text_content("analyze_diff", result)


async def _prepare_diff_context(
    question: str,
    max_context: int,
    vector_db_path: Any,
    embedding_provider: Any,
) -> tuple[str, list[dict[str, Any]]]:
    """Search the vector store for context relevant to *question*.

    Args:
        question: The user's question about the diff.
        max_context: Maximum number of code chunks to retrieve.
        vector_db_path: Path to the LanceDB vector store.
        embedding_provider: Provider for computing query embeddings.

    Returns:
        Tuple of (additional_context_string, sources_list).
    """
    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []

    if vector_db_path.exists():
        vector_store = VectorStore(vector_db_path, embedding_provider)
        search_results = await vector_store.search(question, limit=max_context)
        for sr in search_results:
            chunk = sr.chunk
            context_parts.append(
                f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
                f"Type: {chunk.chunk_type.value}\n"
                f"```\n{chunk.content}\n```"
            )
            sources.append(
                {
                    "file": chunk.file_path,
                    "lines": f"{chunk.start_line}-{chunk.end_line}",
                    "type": chunk.chunk_type.value,
                    "score": sr.score,
                }
            )

    additional_context = (
        "\n\n---\n\n".join(context_parts)
        if context_parts
        else "(No additional code context available)"
    )
    return additional_context, sources


async def _synthesize_diff_answer(
    diff_ctx: DiffSynthesisContext,
    wiki_path: Any,
    config: Any,
    embedding_provider: Any,
) -> str:
    """Call the LLM to synthesize an answer about the diff.

    Args:
        diff_ctx: Immutable context with question, diff text, refs, and RAG context.
        wiki_path: Path to wiki directory (for LLM cache).
        config: Application config object.
        embedding_provider: Provider for embedding (needed by cached LLM).

    Returns:
        The LLM-generated answer string.
    """
    from local_deepwiki.providers.llm import get_cached_llm_provider

    cache_path = wiki_path / "llm_cache.lance"
    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=embedding_provider,
        cache_config=config.llm_cache,
        llm_config=config.llm,
    )

    prompt = (
        f"You are analyzing recent code changes. Answer this question about the diff:\n\n"
        f"Question: {diff_ctx.question}\n\n"
        f"## Git Diff (changes between {diff_ctx.base_ref} and {diff_ctx.head_ref}):\n"
        f"```diff\n{diff_ctx.diff_text}\n```\n\n"
        f"## Additional Code Context (from the codebase):\n{diff_ctx.additional_context}\n\n"
        f"Provide a clear, specific answer based on the diff and context. "
        f"Focus on what changed, why it might matter, and any potential issues."
    )
    system_prompt = "You are a code review assistant. Analyze code diffs and answer questions accurately."

    rate_limiter = get_rate_limiter()
    async with rate_limiter:
        return await llm.generate(prompt, system_prompt=system_prompt)


async def _rag_answer_about_diff(
    question: str,
    diff_text: str,
    repo_path: Path,
    validated: AskAboutDiffArgs,
) -> tuple[str, list[dict[str, Any]]]:
    """Run RAG retrieval and LLM synthesis for a diff question.

    Args:
        question: The user's question.
        diff_text: (Possibly truncated) diff text.
        repo_path: Resolved repository path.
        validated: Validated request arguments.

    Returns:
        Tuple of (answer_string, sources_list).
    """
    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)
    wiki_path = config.get_wiki_path(repo_path)
    embedding_provider = get_embedding_provider(config.embedding)

    additional_context, sources = await _prepare_diff_context(
        question, validated.max_context, vector_db_path, embedding_provider
    )

    diff_ctx = DiffSynthesisContext(
        question=question,
        diff_text=diff_text,
        base_ref=validated.base_ref,
        head_ref=validated.head_ref,
        additional_context=additional_context,
    )
    answer = await _synthesize_diff_answer(
        diff_ctx,
        wiki_path,
        config,
        embedding_provider,
    )
    return answer, sources


@handle_tool_errors
async def handle_ask_about_diff(args: dict[str, Any]) -> list[TextContent]:
    """Handle ask_about_diff tool call.

    RAG-based Q&A about recent code changes, combining git diff
    with vector search context and LLM synthesis.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = AskAboutDiffArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    question = validated.question

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _validate_git_refs(
        [
            ("base_ref", validated.base_ref),
            ("head_ref", validated.head_ref),
        ]
    )

    # Get the diff
    diff_result = await _run_git_diff(
        repo_path,
        validated.base_ref,
        validated.head_ref,
    )
    if isinstance(diff_result, list):
        return diff_result

    diff_text = diff_result.stdout
    if not diff_text.strip():
        return make_tool_text_content(
            "ask_about_diff",
            {
                "status": "success",
                "question": question,
                "answer": "No changes found between the specified refs. There is nothing to analyze.",
                "sources": [],
            },
        )

    # Truncate diff if very large
    if len(diff_text) > MAX_DIFF_TEXT_LENGTH:
        diff_text = (
            diff_text[:MAX_DIFF_TEXT_LENGTH]
            + f"\n... (diff truncated, showing first {MAX_DIFF_TEXT_LENGTH} chars)"
        )

    answer, sources = await _rag_answer_about_diff(
        question,
        diff_text,
        repo_path,
        validated,
    )

    result = {
        "status": "success",
        "question": question,
        "base_ref": validated.base_ref,
        "head_ref": validated.head_ref,
        "answer": answer,
        "diff_stats": {
            "diff_length": len(diff_result.stdout),
            "truncated": len(diff_result.stdout) > MAX_DIFF_TEXT_LENGTH,
        },
        "sources": sources,
    }

    logger.info("Ask about diff: '%s...' for %s", question[:50], repo_path)
    return make_tool_text_content("ask_about_diff", result)
