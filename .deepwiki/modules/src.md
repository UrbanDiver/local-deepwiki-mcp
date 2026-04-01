# Module: git_utils

## Module Purpose

The `git_utils` module provides utilities for working with Git repositories. It includes functionality for validating paths, retrieving repository information, building source file URLs for hosting services like GitHub and GitLab, and detecting staleness of wiki pages based on source file modification dates.

## Key Classes and Functions

### Classes

**[GitPathValidationError](../files/src/local_deepwiki/core/git_utils.md)**
Raised when a path fails git-specific validation.

**[GitRepoInfo](../files/src/local_deepwiki/core/git_utils.md)**
Information about a git repository, including remote URL, host, owner, repo name, and default branch.

**[StaleInfo](../files/src/local_deepwiki/core/git_utils.md)**
Information about a potentially stale wiki page, including the page path, generation time, source files, newest source modification date, and days stale.

### Functions

**_validate_git_path**
Validate a path for safe use in git commands, preventing option injection and ensuring the path exists.

**_validate_repo_path**
Validate a repository path for safe use in git commands, performing all checks from `_validate_git_path` plus repository-specific checks.

**[get_git_remote_url](../files/src/local_deepwiki/core/git_utils.md)**
Get the remote origin URL from git config.

**[parse_remote_url](../files/src/local_deepwiki/core/git_utils.md)**
Parse remote URL to extract host, owner, and repo name, handling various URL formats.

**[get_default_branch](../files/src/local_deepwiki/core/git_utils.md)**
Get the default branch name for the repository by checking current HEAD, remote HEAD, or falling back to 'main'.

**[get_repo_info](../files/src/local_deepwiki/core/git_utils.md)**
Get complete git repository information including remote URL, host, owner, repo name, and default branch.

**[is_github_repo](../files/src/local_deepwiki/core/git_utils.md)**
Check if a repository is hosted on GitHub by examining the remote URL.

**_build_line_anchor_gitlab**
Return a GitLab-style line anchor fragment (e.g., ``#L5-10``).

**_build_line_anchor_github**
Return a GitHub-style line anchor fragment (e.g., ``#L5-L10``).

**_build_gitlab_url**
Build a GitLab source URL using the ``/-/blob/`` path prefix.

**_build_github_url**
Build a GitHub-style source URL, also used as the default fallback.

**build_source_url**
Build a URL to the source file on GitHub/GitLab based on repository information and optional line numbers.

**get_file_last_modified**
Get the last modification date of a file from git history.

**get_files_last_modified**
Get last modification dates for multiple files efficiently using a single git log command.

**check_page_staleness**
Check if a wiki page is potentially stale by comparing source file modification dates with the page generation time.

## How Components Interact

The module's components work together to provide a comprehensive Git utility suite:

1. Path validation functions (`_validate_git_path`, `_validate_repo_path`) ensure safe operations
2. Repository information functions ([`get_repo_info`](../files/src/local_deepwiki/core/git_utils.md), [`get_default_branch`](../files/src/local_deepwiki/core/git_utils.md)) gather metadata
3. URL building functions ([`build_source_url`](../files/src/local_deepwiki/core/git_utils.md), `_build_github_url`, `_build_gitlab_url`) create links to source files
4. Staleness detection functions ([`check_page_staleness`](../files/src/local_deepwiki/core/git_utils.md), [`get_files_last_modified`](../files/src/local_deepwiki/core/git_utils.md)) compare modification times
5. Remote URL parsing ([`parse_remote_url`](../files/src/local_deepwiki/core/git_utils.md)) handles different hosting service formats

## Usage Examples

```python
from pathlib import Path
from local_deepwiki.core.git_utils import get_repo_info, build_source_url, check_page_staleness

# Get repository information
repo_path = Path("/path/to/repo")
repo_info = get_repo_info(repo_path)
print(repo_info.host, repo_info.owner, repo_info.repo)

# Build a source URL
url = build_source_url(repo_info, "src/main.py", start_line=10, end_line=20)
print(url)

# Check if a page is stale
stale_info = check_page_staleness(
    repo_path,
    "docs/api.md",
    generated_at=1678886400.0,
    source_files=["src/main.py", "src/utils.py"]
)
if stale_info:
    print(f"Page is stale by {stale_info.days_stale} days")
```

## Dependencies

- `re`
- `subprocess`
- `dataclasses`
- `datetime`
- `pathlib`
- `local_deepwiki.logging`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/core/git_utils.py:28-31`](../files/src/local_deepwiki/core/git_utils.md)
- [`src/local_deepwiki/core/chunker.py:50-63`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/server.py:92-94`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/core/vectorstore/embedding.py:20-30`](../files/src/local_deepwiki/core/vectorstore/embedding.md)
- [`src/local_deepwiki/core/graph_rag/store.py:44-411`](../files/src/local_deepwiki/core/graph_rag/store.md)
- [`src/local_deepwiki/config/provider_models.py:10-20`](../files/src/local_deepwiki/config/provider_models.md)
- [`src/local_deepwiki/core/indexer.py:233-263`](../files/src/local_deepwiki/core/indexer.md)
- `src/local_deepwiki/providers/llm/__init__.py:16-19`
- [`src/local_deepwiki/cli/init_cli.py:30-43`](../files/src/local_deepwiki/cli/init_cli.md)
- [`src/local_deepwiki/web/app.py:87-96`](../files/src/local_deepwiki/web/app.md)


*Showing 10 of 263 source files.*
