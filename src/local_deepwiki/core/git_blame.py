"""Git blame integration for tracking code authorship.

Provides functions to query git blame information for individual lines,
line ranges, and entire files with per-entity blame resolution.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from local_deepwiki.core.git_utils import (
    GIT_BLAME_FILE_TIMEOUT,
    GIT_BLAME_LINE_TIMEOUT,
    GIT_BLAME_RANGE_TIMEOUT,
    GitPathValidationError,
    _validate_git_path,
    _validate_repo_path,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BlameInfo:
    """Git blame information for a line or range."""

    author: str
    author_email: str | None
    date: datetime
    commit_hash: str
    summary: str | None = None  # Commit message summary


@dataclass(frozen=True, slots=True)
class EntityBlameInfo:
    """Blame information for a code entity (function, class, method)."""

    entity_name: str
    entity_type: str  # 'function', 'class', 'method'
    start_line: int
    end_line: int
    last_modified_by: str
    last_modified_date: datetime
    commit_hash: str
    commit_summary: str | None = None


def get_line_blame(
    repo_path: Path,
    file_path: str,
    line_number: int,
) -> BlameInfo | None:
    """Get git blame information for a specific line.

    Args:
        repo_path: Path to the repository root.
        file_path: Relative path to the file.
        line_number: Line number to blame (1-indexed).

    Returns:
        BlameInfo or None if blame fails.
    """
    try:
        validated_repo = _validate_repo_path(repo_path)
        # Validate file_path relative to repo (construct full path for validation)
        full_file_path = validated_repo / file_path
        _validate_git_path(full_file_path)

        # Use porcelain format for easy parsing
        # Use -- separator to prevent option injection from file_path
        result = subprocess.run(
            [
                "git",
                "blame",
                "-L",
                f"{line_number},{line_number}",
                "--porcelain",
                "--",
                file_path,
            ],
            cwd=validated_repo,
            capture_output=True,
            text=True,
            timeout=GIT_BLAME_LINE_TIMEOUT,
        )
        if result.returncode != 0:
            return None

        return _parse_porcelain_blame(result.stdout)

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError,
        GitPathValidationError,
    ) as e:
        logger.debug("Failed to get git blame: %s", e)
        return None


def get_range_blame(
    repo_path: Path,
    file_path: str,
    start_line: int,
    end_line: int,
) -> BlameInfo | None:
    """Get the most recent blame information for a line range.

    Returns the blame info for the most recently modified line in the range.

    Args:
        repo_path: Path to the repository root.
        file_path: Relative path to the file.
        start_line: Starting line number (1-indexed).
        end_line: Ending line number (1-indexed).

    Returns:
        BlameInfo for the most recently modified line, or None.
    """
    try:
        validated_repo = _validate_repo_path(repo_path)
        # Validate file_path relative to repo
        full_file_path = validated_repo / file_path
        _validate_git_path(full_file_path)

        # Use -- separator to prevent option injection from file_path
        result = subprocess.run(
            [
                "git",
                "blame",
                "-L",
                f"{start_line},{end_line}",
                "--porcelain",
                "--",
                file_path,
            ],
            cwd=validated_repo,
            capture_output=True,
            text=True,
            timeout=GIT_BLAME_RANGE_TIMEOUT,
        )
        if result.returncode != 0:
            return None

        # Parse all blame entries and find the most recent
        entries = _parse_all_porcelain_blame(result.stdout)
        if not entries:
            return None

        # Return the most recently modified entry
        return max(entries, key=lambda e: e.date)

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError,
        GitPathValidationError,
    ) as e:
        logger.debug("Failed to get git blame for range: %s", e)
        return None


def _parse_porcelain_blame(output: str) -> BlameInfo | None:
    """Parse git blame porcelain format output for a single entry.

    Args:
        output: Git blame porcelain output.

    Returns:
        BlameInfo or None if parsing fails.
    """
    entries = _parse_all_porcelain_blame(output)
    return entries[0] if entries else None


def _is_commit_hash_line(line: str) -> bool:
    """Return True if the line starts with a 40-char hex commit hash."""
    return len(line) >= 40 and all(c in "0123456789abcdef" for c in line[:40])


def _parse_blame_header(
    lines: list[str], start: int
) -> tuple[str | None, str | None, int | None, str | None, int]:
    """Parse blame header lines starting at *start* (after the commit-hash line).

    Reads lines until it hits a tab (source line) and returns the parsed
    author fields plus the new line index.

    Args:
        lines: All split lines of the porcelain output.
        start: Index of the first header line (the line after the hash line).

    Returns:
        Tuple of (author, author_email, author_time, summary, new_index)
        where new_index points past the source line.
    """
    author: str | None = None
    author_email: str | None = None
    author_time: int | None = None
    summary: str | None = None

    i = start
    while i < len(lines) and not lines[i].startswith("\t"):
        header_line = lines[i]
        if header_line.startswith("author "):
            author = header_line[7:]
        elif header_line.startswith("author-mail "):
            author_email = header_line[12:].strip("<>")
        elif header_line.startswith("author-time "):
            try:
                author_time = int(header_line[12:])
            except ValueError:
                pass
        elif header_line.startswith("summary "):
            summary = header_line[8:]
        i += 1

    # Skip the source line (starts with tab)
    if i < len(lines) and lines[i].startswith("\t"):
        i += 1

    return author, author_email, author_time, summary, i


def _parse_all_porcelain_blame(output: str) -> list[BlameInfo]:
    """Parse git blame porcelain format output for multiple entries.

    Porcelain format has header lines followed by the actual source line.
    Header includes: commit hash, author, author-mail, author-time, etc.

    Args:
        output: Git blame porcelain output.

    Returns:
        List of BlameInfo objects.
    """
    entries: list[BlameInfo] = []
    lines = output.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        if _is_commit_hash_line(line):
            commit_hash = line[:40]
            author, author_email, author_time, summary, i = _parse_blame_header(
                lines, i + 1
            )
            if author and author_time:
                entries.append(
                    BlameInfo(
                        author=author,
                        author_email=author_email,
                        date=datetime.fromtimestamp(author_time, tz=timezone.utc),
                        commit_hash=commit_hash,
                        summary=summary,
                    )
                )
        else:
            i += 1

    return entries


def get_file_entity_blame(
    repo_path: Path,
    file_path: str,
    entities: list[tuple[str, str, int, int]],  # [(name, type, start, end), ...]
) -> list[EntityBlameInfo]:
    """Get blame information for multiple code entities in a file.

    This is more efficient than calling get_range_blame for each entity,
    as it runs a single git blame command for the entire file.

    Args:
        repo_path: Path to the repository root.
        file_path: Relative path to the file.
        entities: List of (entity_name, entity_type, start_line, end_line) tuples.

    Returns:
        List of EntityBlameInfo objects.
    """
    if not entities:
        return []

    try:
        validated_repo = _validate_repo_path(repo_path)
        # Validate file_path relative to repo
        full_file_path = validated_repo / file_path
        _validate_git_path(full_file_path)

        # Get blame for entire file
        # Use -- separator to prevent option injection from file_path
        result = subprocess.run(
            ["git", "blame", "--porcelain", "--", file_path],
            cwd=validated_repo,
            capture_output=True,
            text=True,
            timeout=GIT_BLAME_FILE_TIMEOUT,
        )
        if result.returncode != 0:
            return []

        # Parse blame output - build line -> BlameInfo mapping
        line_blame = _parse_line_blame_map(result.stdout)
        if not line_blame:
            return []

        # For each entity, find the most recently modified line
        entity_blames: list[EntityBlameInfo] = []

        for name, entity_type, start, end in entities:
            # Get blame entries for this range
            range_blames: list[BlameInfo] = []
            for line_num in range(start, end + 1):
                if line_num in line_blame:
                    range_blames.append(line_blame[line_num])

            if range_blames:
                # Find most recently modified
                most_recent = max(range_blames, key=lambda b: b.date)
                entity_blames.append(
                    EntityBlameInfo(
                        entity_name=name,
                        entity_type=entity_type,
                        start_line=start,
                        end_line=end,
                        last_modified_by=most_recent.author,
                        last_modified_date=most_recent.date,
                        commit_hash=most_recent.commit_hash,
                        commit_summary=most_recent.summary,
                    )
                )

        return entity_blames

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError,
        GitPathValidationError,
    ) as e:
        logger.debug("Failed to get file entity blame: %s", e)
        return []


def _parse_blame_entry(
    lines: list[str],
    hash_line: str,
    start: int,
    commit_cache: dict[str, BlameInfo],
) -> tuple[int, BlameInfo | None, int]:
    """Parse a single blame entry from the porcelain output.

    Args:
        lines: All split lines of the porcelain output.
        hash_line: The commit-hash line (first line of this entry).
        start: Index of the first header line after the hash line.
        commit_cache: Cache mapping commit hash -> BlameInfo for abbreviated entries.

    Returns:
        Tuple of (final_line, blame_info_or_None, new_index).
    """
    parts = hash_line.split()
    commit_hash = parts[0]
    final_line = int(parts[2]) if len(parts) >= 3 else 0

    author, author_email, author_time, summary, new_index = _parse_blame_header(
        lines, start
    )

    blame_info: BlameInfo | None = None
    if author and author_time and final_line > 0:
        blame_info = BlameInfo(
            author=author,
            author_email=author_email,
            date=datetime.fromtimestamp(author_time, tz=timezone.utc),
            commit_hash=commit_hash,
            summary=summary,
        )
        commit_cache[commit_hash] = blame_info
    elif final_line > 0 and commit_hash in commit_cache:
        blame_info = commit_cache[commit_hash]

    return final_line, blame_info, new_index


def _parse_line_blame_map(output: str) -> dict[int, BlameInfo]:
    """Parse git blame porcelain output into a line number -> BlameInfo map.

    Git blame porcelain format only includes full author info for the first
    occurrence of each commit hash. Subsequent lines from the same commit
    have abbreviated headers. We cache blame info per commit to handle this.

    Args:
        output: Git blame porcelain output for entire file.

    Returns:
        Dictionary mapping line numbers to BlameInfo.
    """
    line_blame: dict[int, BlameInfo] = {}
    commit_cache: dict[str, BlameInfo] = {}
    lines = output.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_commit_hash_line(line):
            final_line, blame_info, i = _parse_blame_entry(
                lines, line, i + 1, commit_cache
            )
            if blame_info is not None and final_line > 0:
                line_blame[final_line] = blame_info
        else:
            i += 1

    return line_blame


def format_blame_date(dt: datetime) -> str:
    """Format a blame date for display.

    Args:
        dt: Datetime object.

    Returns:
        Formatted date string like "Jan 15, 2025" or "2 days ago" for recent dates.
    """
    now = datetime.now(tz=timezone.utc)
    # Handle naive datetimes by assuming UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt

    if diff.days == 0:
        return "today"
    elif diff.days == 1:
        return "yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    elif diff.days < 30:
        weeks = diff.days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    elif diff.days < 365:
        return dt.strftime("%b %d, %Y")
    else:
        return dt.strftime("%b %d, %Y")
