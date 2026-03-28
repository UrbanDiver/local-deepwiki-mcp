# Restore B Grade — Surgical Complexity Reduction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore architecture health from C (73.8) to B (>=75) by extracting helpers from 3 complexity hotspots.

**Architecture:** Pure behavior-preserving refactoring. Extract private helper functions from `run_check` (CC=32), `_build_module_graph` (CC=22), and `generate_module_docs` (CC=25). No new files, no API changes, no test modifications. Existing tests are the correctness proof.

**Tech Stack:** Python, pytest, Rich (for CLI formatting)

---

## Task 1: Extract formatters from `run_check`

The `run_check` function (CC=32, 132 lines) in `cli/check_cli.py` has two large output branches: JSON formatting and Rich table formatting. Extracting these drops `run_check` to ~30 lines and CC ~8.

**Files:**
- Modify: `src/local_deepwiki/cli/check_cli.py`

- [ ] **Step 1: Extract `_format_json_output` helper**

Add this function above `run_check` in `check_cli.py`:

```python
def _format_json_output(
    overall: dict[str, Any],
    thresholds: dict[str, Any],
    violations: list[dict[str, Any]],
    console: Console,
) -> None:
    """Format and print check results as JSON."""
    output = {
        "grade": overall.get("grade", "F"),
        "score": overall.get("score", 0),
        "dimensions": {
            name: dim_data.get("score", 0)
            for name, dim_data in overall.get("dimensions", {}).items()
        },
        "thresholds": thresholds,
        "violations": violations,
        "passed": len(violations) == 0,
    }
    console.print(json.dumps(output, indent=2))
```

- [ ] **Step 2: Extract `_format_rich_table` helper**

Add this function below `_format_json_output`:

```python
def _format_rich_table(
    overall: dict[str, Any],
    thresholds: dict[str, Any],
    violations: list[dict[str, Any]],
    project_name: str,
    console: Console,
) -> None:
    """Format and print check results as a Rich table."""
    table = Table(
        title=f"Architecture Health: {project_name}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status", justify="center")

    grade = overall.get("grade", "F")
    score = overall.get("score", 0)

    # Overall row
    min_grade = thresholds.get("min_grade")
    grade_status = (
        "[green]PASS[/green]"
        if min_grade is None or _grade_passes(grade, min_grade)
        else "[red]FAIL[/red]"
    )
    table.add_row(
        "Grade",
        grade,
        str(min_grade) if min_grade else "-",
        grade_status,
    )

    min_score = thresholds.get("min_score")
    score_status = (
        "[green]PASS[/green]"
        if min_score is None or score >= min_score
        else "[red]FAIL[/red]"
    )
    table.add_row(
        "Score",
        str(score),
        str(min_score) if min_score else "-",
        score_status,
    )

    # Dimension rows
    for dim in ("complexity", "coupling", "smells", "layers"):
        dim_score = overall.get("dimensions", {}).get(dim, {}).get("score", 0)
        threshold_key = f"min_{dim}"
        min_dim = thresholds.get(threshold_key)
        dim_status = (
            "[green]PASS[/green]"
            if min_dim is None or dim_score >= min_dim
            else "[red]FAIL[/red]"
        )
        table.add_row(
            dim.capitalize(),
            str(dim_score),
            str(min_dim) if min_dim else "-",
            dim_status,
        )

    console.print(table)

    if violations:
        console.print(f"\n[red]{len(violations)} violation(s) found.[/red]")
        for v in violations:
            console.print(f"  [red]- {v['message']}[/red]")
    else:
        console.print("\n[green]All checks passed.[/green]")
```

- [ ] **Step 3: Rewrite `run_check` to use the helpers**

Replace the body of `run_check` (lines 126-257) with:

```python
def run_check(
    repo_path: Path,
    *,
    json_output: bool = False,
    console: Console | None = None,
) -> int:
    """Run the architecture quality gate.

    Returns:
        0 if all thresholds pass (or none configured).
        1 if any threshold is violated.
        2 on infrastructure error (missing repo, analysis failure).
    """
    if console is None:
        console = Console()

    # Validate repo exists
    if not repo_path.exists() or not repo_path.is_dir():
        console.print(f"[red]Repository not found: {repo_path}[/red]")
        return 2

    # Load thresholds
    thresholds = _load_thresholds(repo_path)

    # Resolve project name
    try:
        manifest = get_cached_manifest(repo_path)
        project_name = manifest.name or repo_path.name
    except Exception:
        project_name = repo_path.name

    # Run analysis
    try:
        health_data = analyze_architecture_health(repo_path, project_name)
    except Exception as exc:
        console.print(f"[red]Analysis failed: {exc}[/red]")
        return 2

    # Save snapshot (non-critical)
    wiki_path = repo_path / ".deepwiki"
    try:
        save_snapshot(wiki_path, health_data)
    except Exception:
        pass

    # Check thresholds
    violations = _check_thresholds(health_data, thresholds)
    overall = health_data.get("overall", {})

    if json_output:
        _format_json_output(overall, thresholds, violations, console)
    else:
        _format_rich_table(overall, thresholds, violations, project_name, console)

    return 1 if violations else 0
```

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/test_check_cli.py -x -q`
Expected: All 11 tests pass. No test modifications needed.

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/cli/check_cli.py
git commit -m "refactor: extract formatters from run_check (CC 32 -> ~8)"
```

---

## Task 2: Extract import resolver from `_build_module_graph`

The `_build_module_graph` function (CC=22, 73 lines) in `generators/analysis/module_dependencies.py` has complex nested conditionals for classifying imports. Extracting import resolution drops it to CC ~10.

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/module_dependencies.py`

- [ ] **Step 1: Extract `_resolve_import_target` helper**

Add this function above `_build_module_graph` in `module_dependencies.py`:

```python
def _resolve_import_target(
    dotted: str,
    project_tops: set[str],
    src_module: str,
    module_filter: str | None,
    include_external: bool,
) -> str | None:
    """Classify a dotted import and return the target module label.

    Returns the target module label string, or ``None`` if the import
    should be skipped (e.g. self-import, filtered out, or unwanted external).
    """
    top = _top_level(dotted)
    is_internal = top in project_tops

    if not include_external and not is_internal:
        return None

    if is_internal:
        parts = dotted.split(".")
        if parts[0] in project_tops:
            parts = parts[1:]
        if not parts:
            return None
        tgt_module = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
    else:
        tgt_module = top

    if tgt_module == src_module:
        return None

    if module_filter and not tgt_module.startswith(module_filter):
        if not include_external:
            return None

    return tgt_module
```

- [ ] **Step 2: Rewrite the inner loop of `_build_module_graph`**

Replace the `for dotted in _extract_full_imports(source):` block (lines 134-161) with:

```python
        for dotted in _extract_full_imports(source):
            tgt_module = _resolve_import_target(
                dotted, project_tops, src_module, module_filter, include_external
            )
            if tgt_module is None:
                continue

            edge = (src_module, tgt_module)
            edge_counts[edge] += 1
            if dotted not in edge_imports[edge]:
                edge_imports[edge].append(dotted)
```

- [ ] **Step 3: Run targeted tests**

Run: `uv run pytest tests/test_module_dependencies.py -x -q`
Expected: All tests pass. No test modifications needed.

- [ ] **Step 4: Commit**

```bash
git add src/local_deepwiki/generators/analysis/module_dependencies.py
git commit -m "refactor: extract _resolve_import_target from _build_module_graph (CC 22 -> ~10)"
```

---

## Task 3: Extract helpers from `generate_module_docs`

The `generate_module_docs` function (CC=25, 139 lines) in `generators/wiki/modules.py` mixes module collection, concurrent generation, and index page creation. Extracting the collection and index phases drops it to CC ~10.

**Files:**
- Modify: `src/local_deepwiki/generators/wiki/modules.py`

- [ ] **Step 1: Extract `_collect_modules_to_generate` helper**

Add this function above `generate_module_docs`:

```python
async def _collect_modules_to_generate(
    directories: dict[str, list[str]],
    status_manager: Any,
    full_rebuild: bool,
    pages: list[WikiPage],
) -> tuple[list[tuple[str, list[str]]], int]:
    """Filter directories and return modules that need (re)generation.

    Args:
        directories: Mapping of directory name to file paths.
        status_manager: Wiki status manager for checking page freshness.
        full_rebuild: Whether to force regeneration of all pages.
        pages: Accumulator list — cached pages are appended in place.

    Returns:
        Tuple of (modules_to_generate, pages_skipped).
    """
    modules_to_generate: list[tuple[str, list[str]]] = []
    pages_skipped = 0

    for dir_name, files in directories.items():
        if len(files) < 2:
            continue
        if is_test_file(dir_name + "/dummy", check_filename=False):
            continue

        page_path = f"modules/{dir_name}.md"

        if not full_rebuild and not status_manager.needs_regeneration(page_path, files):
            existing_page = await status_manager.load_existing_page(page_path)
            if existing_page is not None:
                pages.append(existing_page)
                status_manager.record_page_status(existing_page, files)
                pages_skipped += 1
                continue

        modules_to_generate.append((dir_name, files))

    return modules_to_generate, pages_skipped
```

- [ ] **Step 2: Extract `_create_modules_index_page` helper**

Add this function below `_collect_modules_to_generate`:

```python
async def _create_modules_index_page(
    pages: list[WikiPage],
    directories: dict[str, list[str]],
    index_status: Any,
    status_manager: Any,
    full_rebuild: bool,
) -> tuple[WikiPage, bool]:
    """Create or load the modules index page.

    Args:
        pages: Module pages to list in the index.
        directories: All directory groupings (for dependency tracking).
        index_status: Index status for structural fingerprinting.
        status_manager: Wiki status manager for cache checking.
        full_rebuild: Whether to force regeneration.

    Returns:
        Tuple of (index_page, was_generated). ``was_generated`` is True if the
        page was freshly created, False if loaded from cache.
    """
    index_path = "modules/index.md"
    all_module_files = [f for files in directories.values() for f in files]

    if not full_rebuild and not status_manager.needs_regeneration_structural(
        index_path, index_status
    ):
        existing = await status_manager.load_existing_page(index_path)
        if existing is not None:
            status_manager.record_summary_page_status(
                existing, all_module_files, index_status
            )
            return existing, False

    modules_index = WikiPage(
        path=index_path,
        title="Modules",
        content=_generate_modules_index(pages),
        generated_at=time.time(),
    )
    status_manager.record_summary_page_status(
        modules_index, all_module_files, index_status
    )
    return modules_index, True
```

- [ ] **Step 3: Rewrite `generate_module_docs` to use the helpers**

Replace the entire `generate_module_docs` function body with:

```python
async def generate_module_docs(
    ctx: WikiPipelineContext,
    *,
    max_concurrent: int = 8,
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[list[WikiPage], int, int]:
    """Generate documentation for each module/directory.

    Args:
        ctx: Immutable pipeline context bundling shared parameters.
        max_concurrent: Maximum concurrent LLM calls (ignored if semaphore provided).
        semaphore: Optional shared semaphore for concurrency control.

    Returns:
        Tuple of (pages list, generated count, skipped count).
    """
    index_status = ctx.index_status
    vector_store = ctx.vector_store
    llm = ctx.llm
    system_prompt = ctx.system_prompt
    status_manager = ctx.status_manager
    full_rebuild = ctx.full_rebuild
    max_chunk_content_chars = ctx.max_chunk_content_chars

    pages: list[WikiPage] = []
    pages_generated = 0

    # Group files by top-level directory
    directories: dict[str, list[str]] = {}
    for file_info in index_status.files:
        parts = Path(file_info.path).parts
        if len(parts) > 1:
            dir_name = parts[0]
        else:
            dir_name = "root"
        directories.setdefault(dir_name, []).append(file_info.path)

    # Collect modules needing generation
    modules_to_generate, pages_skipped = await _collect_modules_to_generate(
        directories, status_manager, full_rebuild, pages
    )

    # Generate module docs concurrently
    if modules_to_generate:
        sem = semaphore or asyncio.Semaphore(max_concurrent)
        logger.info(
            "Generating module docs for %d modules (max %d concurrent)",
            len(modules_to_generate),
            max_concurrent,
        )

        async def _gen_with_semaphore(
            dir_name: str, files: list[str]
        ) -> tuple[str, list[str], WikiPage | None]:
            async with sem:
                page = await generate_single_module_doc(
                    dir_name=dir_name,
                    files=files,
                    vector_store=vector_store,
                    llm=llm,
                    system_prompt=system_prompt,
                    repo_path=Path(index_status.repo_path),
                    max_chunk_content_chars=max_chunk_content_chars,
                )
                return dir_name, files, page

        tasks = [
            asyncio.create_task(_gen_with_semaphore(dn, fs))
            for dn, fs in modules_to_generate
        ]

        for coro in asyncio.as_completed(tasks):
            try:
                dir_name, files, page = await coro
                if page is not None:
                    pages.append(page)
                    status_manager.record_page_status(page, files)
                    pages_generated += 1
            except Exception:  # noqa: BLE001 — module failure must not abort wiki build
                logger.exception("Error generating module doc")

    # Create modules index
    if pages:
        index_page, was_generated = await _create_modules_index_page(
            pages, directories, index_status, status_manager, full_rebuild
        )
        pages.insert(0, index_page)
        if was_generated:
            pages_generated += 1
        else:
            pages_skipped += 1

    return pages, pages_generated, pages_skipped
```

- [ ] **Step 4: Add `Any` import if not already present**

Check whether `from typing import Any` is already imported. If not, add it to the imports at the top of the file.

- [ ] **Step 5: Run targeted tests**

Run: `uv run pytest tests/test_wiki_modules_coverage.py -x -q`
Expected: All tests pass. No test modifications needed.

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/generators/wiki/modules.py
git commit -m "refactor: extract collection and index helpers from generate_module_docs (CC 25 -> ~10)"
```

---

## Task 4: Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -q`
Expected: 5,976+ tests pass, 0 failures.

- [ ] **Step 2: Run architecture quality gate**

Run: `uv run deepwiki check --json`
Expected: `"grade": "B"`, `"score"` >= 75, `"passed": true` (assuming pyproject.toml thresholds are met).

- [ ] **Step 3: Commit spec and plan**

```bash
git add docs/superpowers/specs/2026-03-27-restore-b-grade-design.md docs/superpowers/plans/2026-03-27-restore-b-grade.md
git commit -m "docs: add restore B grade spec and plan"
```

---

## Execution Notes

**Parallelization:** Tasks 1-3 touch non-overlapping files:
- Task 1: `cli/check_cli.py`
- Task 2: `generators/analysis/module_dependencies.py`
- Task 3: `generators/wiki/modules.py`

All 3 can run in parallel. Task 4 runs after all complete.

**Risk:** Low. These are pure extractions — moving code into helpers in the same file with identical signatures. The existing tests cover the public behavior and will catch any mistakes in the extraction.
