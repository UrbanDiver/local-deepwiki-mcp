"""Bug detection MCP handler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.errors import path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import DetectBugsArgs
from local_deepwiki.security import Permission, get_access_controller

logger = get_logger(__name__)

# Number of source lines to extract around a finding for LLM context.
_CONTEXT_LINES = 10


def _extract_code_context(
    repo_path: Path,
    file_path: str,
    line: int,
    context_lines: int = _CONTEXT_LINES,
) -> str:
    """Extract ~2*context_lines of source around a finding for LLM context.

    Returns the extracted snippet or an empty string if the file cannot be read.
    """
    target = repo_path / file_path
    try:
        source_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    start = max(0, line - context_lines - 1)
    end = min(len(source_lines), line + context_lines)
    numbered = [f"{i + 1:>4} | {source_lines[i]}" for i in range(start, end)]
    return "\n".join(numbered)


async def _enrich_findings(
    findings: list[dict[str, Any]],
    repo_path: Path,
    top_n: int,
) -> list[dict[str, Any]]:
    """Enrich the top *top_n* findings with LLM verification.

    For each top finding, extracts code context and asks the LLM whether it
    is a real bug, what would go wrong, and how to fix it. Findings the LLM
    marks as ``verified=false`` are demoted to ``"low"`` confidence.

    Returns a **new** list: enriched findings first, then remaining
    un-enriched findings (no mutation of originals).
    """
    from local_deepwiki.providers.llm import get_llm_provider

    provider = get_llm_provider()

    to_enrich = findings[:top_n]
    remaining = findings[top_n:]

    enriched: list[dict[str, Any]] = []
    for finding in to_enrich:
        code_context = _extract_code_context(
            repo_path,
            finding.get("file", ""),
            finding.get("line", 0),
        )

        prompt = (
            "You are a code reviewer. Analyze this potential bug finding and "
            "respond with ONLY a JSON object (no markdown fences).\n\n"
            f"Pattern: {finding.get('pattern', '')}\n"
            f"File: {finding.get('file', '')}\n"
            f"Line: {finding.get('line', 0)}\n"
            f"Message: {finding.get('message', '')}\n"
            f"Snippet: {finding.get('snippet', '')}\n\n"
            f"Code context:\n{code_context}\n\n"
            "Respond with this JSON structure:\n"
            '{"verified": true/false, "explanation": "why this is or is not '
            'a bug", "suggestion": "how to fix it if it is a bug"}'
        )

        try:
            raw = await provider.generate(prompt, temperature=0.2, max_tokens=512)
            parsed = json.loads(raw.strip())
            verified = bool(parsed.get("verified", True))
            explanation = str(parsed.get("explanation", ""))
            suggestion = str(parsed.get("suggestion", ""))

            confidence = finding.get("confidence", "medium")
            if not verified:
                confidence = "low"

            enriched.append(
                {
                    **finding,
                    "confidence": confidence,
                    "verified": verified,
                    "explanation": explanation,
                    "suggestion": suggestion,
                }
            )
        except Exception:
            logger.debug(
                "Failed to enrich finding %s:%s, keeping original",
                finding.get("file", ""),
                finding.get("line", 0),
            )
            enriched.append({**finding})

    # Append remaining un-enriched findings (immutable — new dicts)
    enriched.extend({**f} for f in remaining)
    return enriched


@handle_tool_errors
async def handle_detect_bugs(args: dict[str, Any]) -> list[TextContent]:
    """Handle detect_bugs tool call.

    Scans a repository for potential bugs using AST pattern matching.
    Optionally enriches top findings with LLM verification.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = DetectBugsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.bug_detection import analyze_bugs

    result = analyze_bugs(
        repo_path,
        min_confidence=validated.min_confidence,
        languages=validated.languages,
        exclude_tests=validated.exclude_tests,
        file_path=validated.file_path,
        top_n=validated.top_n,
    )

    if validated.enrich and result.get("findings"):
        try:
            result = {
                **result,
                "findings": await _enrich_findings(
                    result["findings"], repo_path, validated.enrich_top_n
                ),
            }
        except Exception:
            logger.debug("LLM enrichment unavailable, returning static findings")

    logger.info(
        "Bug scan: %d findings (%d returned) in %d files for %s",
        result.get("total_findings", 0),
        result.get("returned", 0),
        result.get("files_scanned", 0),
        repo_path,
    )
    return make_tool_text_content("detect_bugs", result)
