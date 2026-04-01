"""Entrypoint for the DeepWiki PR Analysis GitHub Action.

Invokes existing handler functions directly (no MCP protocol overhead)
and produces structured output + a markdown PR comment.
"""

import asyncio
import json
import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_bool(name: str) -> bool:
    return _env(name).lower() in ("true", "1", "yes")


async def run_analysis() -> dict:
    """Run diff analysis and stale docs detection, return combined results."""
    from local_deepwiki.handlers.analysis_diff import handle_analyze_diff
    from local_deepwiki.handlers.generators import handle_detect_stale_docs

    repo_path = str(Path(_env("INPUT_REPO_PATH", ".")).resolve())
    base_ref = _env("INPUT_BASE_REF", "HEAD~1")
    head_ref = _env("INPUT_HEAD_REF", "HEAD")
    stale_threshold = int(_env("INPUT_STALE_THRESHOLD", "0"))
    include_content = _env_bool("INPUT_INCLUDE_CONTENT")

    results = {"diff_analysis": None, "stale_docs": None, "errors": []}

    # --- Diff analysis ---
    try:
        diff_response = await handle_analyze_diff(
            {
                "repo_path": repo_path,
                "base_ref": base_ref,
                "head_ref": head_ref,
                "include_content": include_content,
            }
        )
        diff_text = diff_response[0].text if diff_response else "{}"
        results["diff_analysis"] = json.loads(diff_text)
    except Exception as exc:
        results["errors"].append(f"Diff analysis failed: {exc}")

    # --- Stale docs detection ---
    try:
        stale_response = await handle_detect_stale_docs(
            {
                "repo_path": repo_path,
                "threshold_days": stale_threshold,
            }
        )
        stale_text = stale_response[0].text if stale_response else "{}"
        results["stale_docs"] = json.loads(stale_text)
    except Exception as exc:
        results["errors"].append(f"Stale docs detection failed: {exc}")

    return results


def set_output(name: str, value: str) -> None:
    """Write a value to GITHUB_OUTPUT."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")


def build_comment(results: dict) -> str:
    """Build a markdown PR comment from analysis results."""
    lines = ["## DeepWiki PR Analysis\n"]

    diff = results.get("diff_analysis")
    stale = results.get("stale_docs")
    errors = results.get("errors", [])

    # --- Diff summary ---
    if diff and diff.get("status") == "success":
        summary = diff.get("summary", {})
        total = summary.get("total_changed_files", 0)
        added = summary.get("added", 0)
        modified = summary.get("modified", 0)
        deleted = summary.get("deleted", 0)
        wiki_count = summary.get("affected_wiki_pages", 0)
        entity_count = summary.get("affected_entities", 0)

        lines.append(f"### Changes: {total} files")
        lines.append(f"  +{added} added | ~{modified} modified | -{deleted} deleted\n")

        # Affected wiki pages
        wiki_pages = diff.get("affected_wiki_pages", [])
        if wiki_pages:
            lines.append(f"### Affected Wiki Pages ({wiki_count})")
            lines.append("")
            lines.append("| Page | Source File |")
            lines.append("|------|------------|")
            for page in wiki_pages[:20]:
                title = page.get("title", "Unknown")
                source = page.get("source_file", "")
                lines.append(f"| {title} | `{source}` |")
            if len(wiki_pages) > 20:
                lines.append(f"| ... and {len(wiki_pages) - 20} more | |")
            lines.append("")
        else:
            lines.append("### Affected Wiki Pages: None\n")

        # Affected entities
        entities = diff.get("affected_entities", [])
        if entities:
            lines.append(f"### Affected Entities ({entity_count})")
            lines.append("")
            lines.append("| Entity | Type | File |")
            lines.append("|--------|------|------|")
            for ent in entities[:30]:
                name = ent.get("name", "")
                etype = ent.get("type", "")
                efile = ent.get("file", "")
                lines.append(f"| `{name}` | {etype} | `{efile}` |")
            if len(entities) > 30:
                lines.append(f"| ... and {len(entities) - 30} more | | |")
            lines.append("")
    elif diff:
        lines.append(
            f"> Diff analysis returned: {diff.get('error', 'unknown error')}\n"
        )

    # --- Stale docs ---
    if stale and stale.get("status") == "success":
        stale_pages = stale.get("stale_pages", [])
        if stale_pages:
            lines.append(f"### Stale Documentation ({len(stale_pages)} pages)")
            lines.append("")
            lines.append("| Wiki Page | Source File | Days Since Update |")
            lines.append("|-----------|------------|-------------------|")
            for sp in stale_pages[:15]:
                title = sp.get("wiki_page", sp.get("title", ""))
                source = sp.get("source_file", "")
                days = sp.get("days_since_source_changed", sp.get("days_stale", "?"))
                lines.append(f"| {title} | `{source}` | {days} |")
            if len(stale_pages) > 15:
                lines.append(f"| ... and {len(stale_pages) - 15} more | | |")
            lines.append("")
        else:
            lines.append("### Stale Documentation: None detected\n")
    elif stale and stale.get("status") == "error":
        err = stale.get("error", "")
        if "not indexed" in err.lower() or "not found" in err.lower():
            lines.append(
                "> Wiki not indexed yet. Run `local-deepwiki index_repository` first "
                "to enable stale doc detection.\n"
            )

    # --- Errors ---
    if errors:
        lines.append("### Warnings")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Generated by [local-deepwiki-mcp](https://github.com/UrbanDiver/local-deepwiki-mcp)*"
    )

    return "\n".join(lines)


def main() -> None:
    results = asyncio.run(run_analysis())

    diff = results.get("diff_analysis") or {}
    stale = results.get("stale_docs") or {}
    summary = diff.get("summary", {})

    # Set outputs
    set_output("changed_files", str(summary.get("total_changed_files", 0)))
    set_output("affected_wiki_pages", str(summary.get("affected_wiki_pages", 0)))
    set_output("affected_entities", str(summary.get("affected_entities", 0)))
    set_output("stale_pages", str(len(stale.get("stale_pages", []))))
    set_output("analysis_json", json.dumps(results, separators=(",", ":")))

    # Build and write PR comment
    comment = build_comment(results)
    Path("/tmp/deepwiki-comment.md").write_text(comment)

    # Print summary to action log
    print(f"Changed files: {summary.get('total_changed_files', 0)}")
    print(f"Affected wiki pages: {summary.get('affected_wiki_pages', 0)}")
    print(f"Affected entities: {summary.get('affected_entities', 0)}")
    print(f"Stale pages: {len(stale.get('stale_pages', []))}")

    if results.get("errors"):
        for err in results["errors"]:
            print(f"::warning::{err}")


if __name__ == "__main__":
    main()
