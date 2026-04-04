# Documentation Freshness Report

This page identifies documentation that may be outdated compared to the source code.
Pages are flagged when source files have been modified after the documentation was generated.

## Summary

| Metric | Value |
|--------|-------|
| Total file pages | 244 |
| Potentially stale | 3 |
| Up to date | 241 |
| Freshness | 99% |

## ⚠️ Potentially Stale Documentation

The following pages may need review. Source files were modified after documentation was generated.

| Page | Days Stale | Last Doc Update | Source Modified |
|------|------------|-----------------|-----------------|
| [docstrings](files/src/local_deepwiki/core/parser/docstrings.md) | 1 | 2 days ago | today |
| [languages](files/src/local_deepwiki/core/parser/languages.md) | 1 | 2 days ago | today |
| [foundation](files/src/local_deepwiki/models/foundation.md) | 1 | 2 days ago | today |

## Recommendations

To refresh stale documentation:

1. **Re-index the repository** with `force=True` to regenerate all pages
2. **Incremental update** will automatically regenerate pages when source files change
3. **Manual review** may be needed for pages where only comments or docstrings changed

---
*Report generated: 2026-04-04 08:53:51*