"""Stale documentation detection for wiki pages.

This module identifies wiki pages that may be outdated compared to their
source code, helping maintainers know which documentation needs review.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from local_deepwiki.core.git_utils import (
    StaleInfo,
    check_page_staleness,
    format_blame_date,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import WikiGenerationStatus, WikiPage

logger = get_logger(__name__)


@dataclass
class StaleReport:
    """Summary of stale documentation analysis."""

    total_pages: int
    stale_pages: int
    stale_info: list[StaleInfo]
    generated_at: datetime


def analyze_staleness(
    repo_path: Path,
    wiki_status: WikiGenerationStatus,
    stale_threshold_days: int = 0,
) -> StaleReport:
    """Analyze all wiki pages for staleness.

    Args:
        repo_path: Path to the repository root.
        wiki_status: Wiki generation status with page info.
        stale_threshold_days: Minimum days to consider a page stale.

    Returns:
        StaleReport with analysis results.
    """
    stale_info: list[StaleInfo] = []

    for page_path, page_status in wiki_status.pages.items():
        # Skip non-file pages (overview, architecture, etc.)
        if not page_path.startswith("files/"):
            continue

        info = check_page_staleness(
            repo_path=repo_path,
            page_path=page_path,
            generated_at=page_status.generated_at,
            source_files=page_status.source_files,
            stale_threshold_days=stale_threshold_days,
        )

        if info:
            stale_info.append(info)

    # Sort by days stale (most stale first)
    stale_info.sort(key=lambda x: x.days_stale, reverse=True)

    return StaleReport(
        total_pages=len([p for p in wiki_status.pages if p.startswith("files/")]),
        stale_pages=len(stale_info),
        stale_info=stale_info,
        generated_at=datetime.now(),
    )


def generate_stale_report_page(
    repo_path: Path,
    wiki_status: WikiGenerationStatus,
    stale_threshold_days: int = 0,
) -> WikiPage:
    """Generate a wiki page reporting potentially stale documentation.

    Args:
        repo_path: Path to the repository root.
        wiki_status: Wiki generation status with page info.
        stale_threshold_days: Minimum days to consider a page stale.

    Returns:
        WikiPage with the stale documentation report.
    """
    report = analyze_staleness(repo_path, wiki_status, stale_threshold_days)

    lines = [
        "# Documentation Freshness Report",
        "",
        "This page identifies documentation that may be outdated compared to the source code.",
        "Pages are flagged when source files have been modified after the documentation was generated.",
        "",
    ]

    # Summary section
    if report.stale_pages == 0:
        lines.extend([
            "## ✅ All Documentation Up to Date",
            "",
            f"All {report.total_pages} file documentation pages are current with their source code.",
            "",
        ])
    else:
        freshness_pct = ((report.total_pages - report.stale_pages) / report.total_pages * 100) if report.total_pages > 0 else 100
        lines.extend([
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total file pages | {report.total_pages} |",
            f"| Potentially stale | {report.stale_pages} |",
            f"| Up to date | {report.total_pages - report.stale_pages} |",
            f"| Freshness | {freshness_pct:.0f}% |",
            "",
        ])

        # Stale pages list
        lines.extend([
            "## ⚠️ Potentially Stale Documentation",
            "",
            "The following pages may need review. Source files were modified after documentation was generated.",
            "",
            "| Page | Days Stale | Last Doc Update | Source Modified |",
            "|------|------------|-----------------|-----------------|",
        ])

        for info in report.stale_info:
            # Create relative link to the page
            page_link = f"[{Path(info.page_path).stem}]({info.page_path})"
            doc_date = format_blame_date(info.generated_at)
            source_date = format_blame_date(info.newest_source_date)

            lines.append(
                f"| {page_link} | {info.days_stale} | {doc_date} | {source_date} |"
            )

        lines.append("")

    # Recommendations section
    lines.extend([
        "## Recommendations",
        "",
        "To refresh stale documentation:",
        "",
        "1. **Re-index the repository** with `force=True` to regenerate all pages",
        "2. **Incremental update** will automatically regenerate pages when source files change",
        "3. **Manual review** may be needed for pages where only comments or docstrings changed",
        "",
        "---",
        f"*Report generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}*",
    ])

    return WikiPage(
        path="freshness.md",
        title="Documentation Freshness",
        content="\n".join(lines),
        generated_at=time.time(),
    )


def generate_stale_banner(stale_info: StaleInfo) -> str:
    """Generate a warning banner for a stale page.

    Args:
        stale_info: Staleness information for the page.

    Returns:
        Markdown banner string to prepend to the page.
    """
    source_date = format_blame_date(stale_info.newest_source_date)

    return f"""> ⚠️ **Documentation may be outdated**
>
> Source code was modified {source_date} ({stale_info.days_stale} days after this documentation was generated).
> Consider re-indexing to update this page.

"""


def add_stale_banners(
    pages: list[WikiPage],
    repo_path: Path,
    wiki_status: WikiGenerationStatus,
    stale_threshold_days: int = 1,
) -> list[WikiPage]:
    """Add stale warning banners to pages with outdated documentation.

    Args:
        pages: List of wiki pages to process.
        repo_path: Path to the repository root.
        wiki_status: Wiki generation status with page info.
        stale_threshold_days: Minimum days to show a banner (default: 1).

    Returns:
        List of wiki pages with banners added where appropriate.
    """
    updated_pages: list[WikiPage] = []

    for page in pages:
        page_status = wiki_status.pages.get(page.path)

        if page_status and page.path.startswith("files/"):
            stale_info = check_page_staleness(
                repo_path=repo_path,
                page_path=page.path,
                generated_at=page_status.generated_at,
                source_files=page_status.source_files,
                stale_threshold_days=stale_threshold_days,
            )

            if stale_info:
                banner = generate_stale_banner(stale_info)
                updated_pages.append(WikiPage(
                    path=page.path,
                    title=page.title,
                    content=banner + page.content,
                    generated_at=page.generated_at,
                ))
                continue

        updated_pages.append(page)

    return updated_pages
