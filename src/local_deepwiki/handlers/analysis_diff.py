"""Diff-related analysis handlers: analyze_diff and ask_about_diff."""

import asyncio
import json
import re
import subprocess
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

from local_deepwiki.handlers._shared import (
    AnalyzeDiffArgs,
    AskAboutDiffArgs,
    Permission,
    ValidationError,
    VectorStore,
    _load_index_status,
    get_access_controller,
    get_config,
    get_embedding_provider,
    get_rate_limiter,
    handle_tool_errors,
    logger,
    path_not_found_error,
    sanitize_error_message,
)


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

    # Validate git refs to prevent injection
    ref_pattern = re.compile(r"^[a-zA-Z0-9_.\/\-~^]+$")
    for ref_name, ref_value in [
        ("base_ref", validated.base_ref),
        ("head_ref", validated.head_ref),
    ]:
        if not ref_pattern.match(ref_value):
            raise ValidationError(
                message=f"Invalid git ref: {ref_value}",
                hint="Git refs must contain only alphanumeric chars, /, -, _, ~, ^, and .",
                field=ref_name,
                value=ref_value,
            )

    # Run git diff --name-status
    try:
        diff_result = subprocess.run(
            [
                "git",
                "diff",
                "--name-status",
                validated.base_ref,
                validated.head_ref,
            ],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=GIT_DIFF_TIMEOUT,
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
    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"git diff timed out after {GIT_DIFF_TIMEOUT} seconds",
                    },
                    indent=2,
                ),
            )
        ]

    # Parse git diff output
    status_map = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
    }
    changed_files: list[dict[str, Any]] = []
    for line in diff_result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status_code, file_name = parts
            status = status_map.get(status_code[0], "modified")
            changed_files.append({"file": file_name, "status": status})

    if not changed_files:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "base_ref": validated.base_ref,
                        "head_ref": validated.head_ref,
                        "message": "No file changes found between the specified refs.",
                        "changed_files": [],
                        "affected_wiki_pages": [],
                        "affected_entities": [],
                    },
                    indent=2,
                ),
            )
        ]

    # Optionally get diff content per file
    if validated.include_content:
        for cf in changed_files:
            try:
                file_diff = subprocess.run(
                    [
                        "git",
                        "diff",
                        validated.base_ref,
                        validated.head_ref,
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

    # Try to load index and map to wiki pages
    affected_wiki_pages: list[dict[str, str]] = []
    affected_entities: list[dict[str, str]] = []
    try:
        _index_status, wiki_path, _config = await _load_index_status(repo_path)

        # Map to wiki pages via toc.json
        toc_path = wiki_path / "toc.json"
        if toc_path.exists():
            toc_content = await asyncio.to_thread(toc_path.read_text)
            toc_data = json.loads(toc_content)
            pages = (
                toc_data if isinstance(toc_data, list) else toc_data.get("pages", [])
            )
            changed_file_set = {cf["file"] for cf in changed_files}
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

        # Map to entities via search.json
        search_path = wiki_path / "search.json"
        if search_path.exists():
            search_content = await asyncio.to_thread(search_path.read_text)
            search_data = json.loads(search_content)
            entities = search_data.get("entities", [])
            changed_file_set = {cf["file"] for cf in changed_files}
            for entity in entities:
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
        # FileNotFoundError: no index exists
        # json.JSONDecodeError: corrupted toc/search JSON
        # OSError: file read issues
        # KeyError: unexpected data format
        # ValidationError: repository not indexed
        logger.debug(f"Could not load wiki/entity mapping for diff analysis: {e}")

    # Summary
    summary = {
        "total_changed_files": len(changed_files),
        "added": sum(1 for f in changed_files if f["status"] == "added"),
        "modified": sum(1 for f in changed_files if f["status"] == "modified"),
        "deleted": sum(1 for f in changed_files if f["status"] == "deleted"),
        "affected_wiki_pages": len(affected_wiki_pages),
        "affected_entities": len(affected_entities),
    }

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
        f"Diff analysis: {len(changed_files)} files changed, "
        f"{len(affected_wiki_pages)} wiki pages affected"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    # Validate git refs to prevent injection
    ref_pattern = re.compile(r"^[a-zA-Z0-9_.\/\-~^]+$")
    for ref_name, ref_value in [
        ("base_ref", validated.base_ref),
        ("head_ref", validated.head_ref),
    ]:
        if not ref_pattern.match(ref_value):
            raise ValidationError(
                message=f"Invalid git ref: {ref_value}",
                hint="Git refs must contain only alphanumeric chars, /, -, _, ~, ^, and .",
                field=ref_name,
                value=ref_value,
            )

    # Get the diff
    try:
        diff_result = subprocess.run(
            ["git", "diff", validated.base_ref, validated.head_ref],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=GIT_DIFF_TIMEOUT,
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
    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"git diff timed out after {GIT_DIFF_TIMEOUT} seconds",
                    },
                    indent=2,
                ),
            )
        ]

    diff_text = diff_result.stdout
    if not diff_text.strip():
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "question": question,
                        "answer": "No changes found between the specified refs. There is nothing to analyze.",
                        "sources": [],
                    },
                    indent=2,
                ),
            )
        ]

    # Truncate diff if very large
    if len(diff_text) > MAX_DIFF_TEXT_LENGTH:
        diff_text = (
            diff_text[:MAX_DIFF_TEXT_LENGTH]
            + f"\n... (diff truncated, showing first {MAX_DIFF_TEXT_LENGTH} chars)"
        )

    # Get additional context from vector store
    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)
    wiki_path = config.get_wiki_path(repo_path)

    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []

    embedding_provider = get_embedding_provider(config.embedding)

    if vector_db_path.exists():
        vector_store = VectorStore(vector_db_path, embedding_provider)

        # Search for relevant context using the question
        search_results = await vector_store.search(
            question, limit=validated.max_context
        )

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

    # Generate answer using LLM
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
        f"Question: {question}\n\n"
        f"## Git Diff (changes between {validated.base_ref} and {validated.head_ref}):\n"
        f"```diff\n{diff_text}\n```\n\n"
        f"## Additional Code Context (from the codebase):\n{additional_context}\n\n"
        f"Provide a clear, specific answer based on the diff and context. "
        f"Focus on what changed, why it might matter, and any potential issues."
    )

    system_prompt = "You are a code review assistant. Analyze code diffs and answer questions accurately."

    rate_limiter = get_rate_limiter()
    async with rate_limiter:
        answer = await llm.generate(prompt, system_prompt=system_prompt)

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

    logger.info(f"Ask about diff: '{question[:50]}...' for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
