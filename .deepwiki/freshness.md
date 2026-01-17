# Documentation Freshness Report

This page identifies documentation that may be outdated compared to the source code.
Pages are flagged when source files have been modified after the documentation was generated.

## Summary

| Metric | Value |
|--------|-------|
| Total file pages | 46 |
| Potentially stale | 3 |
| Up to date | 43 |
| Freshness | 93% |

## ⚠️ Potentially Stale Documentation

The following pages may need review. Source files were modified after documentation was generated.

| Page | Days Stale | Last Doc Update | Source Modified |
|------|------------|-----------------|-----------------|
| [git_utils](files/src/local_deepwiki/core/git_utils.md) | 0 | today | today |
| [stale_detection](files/src/local_deepwiki/generators/stale_detection.md) | 0 | today | today |
| [wiki](files/src/local_deepwiki/generators/wiki.md) | 0 | today | today |

## Recommendations

To refresh stale documentation:

1. **Re-index the repository** with `force=True` to regenerate all pages
2. **Incremental update** will automatically regenerate pages when source files change
3. **Manual review** may be needed for pages where only comments or docstrings changed

---
*Report generated: 2026-01-16 19:06:06*