# Rich Onboarding Guide Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the onboarding guide generator with an LLM-powered version that produces execution-flow diagrams, narrative prose, and wiki links — auto-generated on every `deepwiki update`.

**Architecture:** New async function `generate_rich_onboarding()` in `onboarding.py` orchestrates 4 phases: gather basics, LLM flow selection, codemap generation, LLM synthesis. Hooks into wiki generation pipeline via `phases.py`. Handler updated to call the rich version.

**Tech Stack:** Python, asyncio, LLM providers, codemap generator, VectorStore

---

## Task 1: Add `generate_rich_onboarding` core function

The main orchestrator that produces the rich onboarding guide.

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/onboarding.py`
- Test: `tests/test_onboarding.py`

- [ ] **Step 1: Write the test for the full orchestration**

Add to `tests/test_onboarding.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestGenerateRichOnboarding:
    """Tests for generate_rich_onboarding."""

    @pytest.fixture
    def mock_vector_store(self):
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        mock.get_chunks_by_file = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_llm(self):
        mock = MagicMock()
        # Flow selection returns valid JSON
        mock.generate = AsyncMock(
            side_effect=[
                # Call 1: flow selection
                json.dumps([
                    {"entry_point": "main", "query": "How does the CLI work?", "title": "CLI Pipeline"},
                    {"entry_point": "server", "query": "How does the server work?", "title": "Server Lifecycle"},
                    {"entry_point": "index", "query": "How does indexing work?", "title": "Indexing Pipeline"},
                ]),
                # Call 2: synthesis
                "# Developer Onboarding Guide\n\n## What This Project Does\n\nA test project.\n",
            ]
        )
        return mock

    @pytest.fixture
    def mock_codemap_result(self):
        from local_deepwiki.generators.codemap.models import CodemapResult
        return CodemapResult(
            query="How does the CLI work?",
            focus="execution_flow",
            entry_point="main",
            mermaid_diagram="flowchart TD\n    A[main] --> B[run]",
            narrative="## Summary\nThe CLI dispatches commands.\n",
            nodes=[],
            edges=[],
            files_involved=["src/cli.py"],
            total_nodes=2,
            total_edges=1,
            cross_file_edges=0,
        )

    @patch("local_deepwiki.generators.analysis.onboarding.generate_codemap")
    async def test_rich_onboarding_produces_markdown(
        self, mock_gen_codemap, synthetic_repo, mock_vector_store, mock_llm, mock_codemap_result
    ):
        from local_deepwiki.generators.analysis.onboarding import generate_rich_onboarding

        mock_gen_codemap.return_value = mock_codemap_result

        result = await generate_rich_onboarding(
            repo_path=synthetic_repo,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        assert result["status"] == "success"
        assert "guide" in result
        assert isinstance(result["guide"], str)
        assert "Onboarding" in result["guide"]
        # LLM was called twice: flow selection + synthesis
        assert mock_llm.generate.call_count == 2
        # Codemap was called 3 times (one per flow)
        assert mock_gen_codemap.call_count == 3

    @patch("local_deepwiki.generators.analysis.onboarding.generate_codemap")
    async def test_rich_onboarding_handles_bad_flow_json(
        self, mock_gen_codemap, synthetic_repo, mock_vector_store, mock_llm, mock_codemap_result
    ):
        from local_deepwiki.generators.analysis.onboarding import generate_rich_onboarding

        # LLM returns invalid JSON for flow selection
        mock_llm.generate = AsyncMock(
            side_effect=[
                "not valid json at all",
                "# Developer Onboarding Guide\n\nFallback guide.\n",
            ]
        )
        mock_gen_codemap.return_value = mock_codemap_result

        result = await generate_rich_onboarding(
            repo_path=synthetic_repo,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        assert result["status"] == "success"
        # Still produced a guide via fallback
        assert "guide" in result

    @patch("local_deepwiki.generators.analysis.onboarding.generate_codemap")
    async def test_rich_onboarding_handles_codemap_failure(
        self, mock_gen_codemap, synthetic_repo, mock_vector_store, mock_llm
    ):
        from local_deepwiki.generators.analysis.onboarding import generate_rich_onboarding

        mock_gen_codemap.side_effect = RuntimeError("codemap failed")
        mock_llm.generate = AsyncMock(
            side_effect=[
                json.dumps([
                    {"entry_point": "main", "query": "How?", "title": "Flow 1"},
                ]),
                "# Developer Onboarding Guide\n\nGuide without codemaps.\n",
            ]
        )

        result = await generate_rich_onboarding(
            repo_path=synthetic_repo,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        assert result["status"] == "success"
        assert "guide" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_onboarding.py::TestGenerateRichOnboarding -x -q`
Expected: FAIL — `generate_rich_onboarding` does not exist yet.

- [ ] **Step 3: Implement `generate_rich_onboarding`**

Add to `src/local_deepwiki/generators/analysis/onboarding.py`, below the existing functions:

```python
async def _select_flows_with_llm(
    llm: Any,
    manifest: ProjectManifest,
    entry_points: list[Path],
    directory_tree: str,
) -> list[dict[str, str]]:
    """Ask the LLM to pick the 3 most important flows for newcomers.

    Returns a list of dicts with keys: entry_point, query, title.
    Falls back to entry point heuristics if LLM output is unparseable.
    """
    entry_list = "\n".join(f"- {ep}" for ep in entry_points) or "- (none detected)"
    tech_stack = manifest.get_tech_stack_summary() or "Unknown"

    prompt = (
        "You are helping a developer who is new to this codebase. "
        "Given the project structure below, pick the 3 most important "
        "execution flows a newcomer should understand first.\n\n"
        f"Project: {manifest.name or 'Unknown'}\n"
        f"Description: {manifest.description or 'No description'}\n"
        f"Tech stack: {tech_stack}\n\n"
        f"Entry points:\n{entry_list}\n\n"
        f"Directory structure:\n{directory_tree[:3000]}\n\n"
        "Return ONLY a JSON array of exactly 3 objects, each with:\n"
        '- "entry_point": function or filename to start tracing from\n'
        '- "query": a "How does X work?" question for the codemap\n'
        '- "title": short title for this flow (2-5 words)\n\n'
        "Return ONLY the JSON array, no other text."
    )

    import json as _json

    try:
        raw = await llm.generate(prompt, system_prompt="You are a code architecture expert.")
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        flows = _json.loads(cleaned)
        if isinstance(flows, list) and len(flows) > 0:
            return [
                {
                    "entry_point": f.get("entry_point", ""),
                    "query": f.get("query", ""),
                    "title": f.get("title", ""),
                }
                for f in flows[:3]
            ]
    except Exception:
        logger.warning("LLM flow selection failed, falling back to entry point heuristics")

    # Fallback: use first 3 entry points
    fallback = []
    for ep in entry_points[:3]:
        name = ep.stem
        fallback.append({
            "entry_point": name,
            "query": f"How does {name} work?",
            "title": f"{name.replace('_', ' ').title()} Flow",
        })
    return fallback


async def _generate_codemaps_for_flows(
    flows: list[dict[str, str]],
    vector_store: Any,
    repo_path: Path,
    llm: Any,
) -> list[dict[str, Any]]:
    """Generate codemaps for each selected flow.

    Returns a list of dicts with keys: title, query, mermaid_diagram,
    narrative, files_involved. Failed codemaps are skipped.
    """
    from local_deepwiki.generators.codemap.generator import generate_codemap

    results = []
    for flow in flows:
        try:
            codemap = await generate_codemap(
                query=flow["query"],
                vector_store=vector_store,
                repo_path=repo_path,
                llm=llm,
                entry_point=flow["entry_point"] or None,
                max_depth=5,
                max_nodes=30,
            )
            if codemap.total_nodes > 0:
                results.append({
                    "title": flow["title"],
                    "query": flow["query"],
                    "mermaid_diagram": codemap.mermaid_diagram,
                    "narrative": codemap.narrative,
                    "files_involved": codemap.files_involved,
                })
        except Exception:
            logger.warning("Codemap generation failed for %r", flow.get("query"))
    return results


async def _synthesize_onboarding_guide(
    llm: Any,
    manifest: ProjectManifest,
    directory_tree: str,
    entry_points: list[Path],
    codemaps: list[dict[str, Any]],
    wiki_pages: list[str],
    test_layout: list[Path],
    config_files: list[Path],
) -> str:
    """Ask the LLM to synthesize the full onboarding guide.

    Returns the complete markdown string.
    """
    # Build codemap section for the prompt
    codemap_sections = []
    for cm in codemaps:
        codemap_sections.append(
            f"### Flow: {cm['title']}\n"
            f"Question: {cm['query']}\n"
            f"Files: {', '.join(cm['files_involved'][:10])}\n\n"
            f"Mermaid diagram:\n{cm['mermaid_diagram']}\n\n"
            f"Narrative:\n{cm['narrative']}\n"
        )
    codemap_text = "\n---\n".join(codemap_sections) if codemap_sections else "(no codemaps generated)"

    entry_list = "\n".join(f"- `{ep}`" for ep in entry_points) or "- (none detected)"
    test_list = "\n".join(f"- `{td}`" for td in test_layout) or "- (none detected)"
    config_list = "\n".join(f"- `{cf}`" for cf in config_files) or "- (none detected)"
    wiki_links = "\n".join(f"- `{wp}`" for wp in wiki_pages[:30]) or "- (none available)"
    tech_stack = manifest.get_tech_stack_summary() or "Unknown"

    prompt = f"""Generate a comprehensive Developer Onboarding Guide for the project below.

PROJECT METADATA:
- Name: {manifest.name or 'Unknown'}
- Description: {manifest.description or 'No description'}
- Tech stack: {tech_stack}

ENTRY POINTS:
{entry_list}

DIRECTORY STRUCTURE:
{directory_tree[:3000]}

EXECUTION FLOW DIAGRAMS (include these verbatim):
{codemap_text}

AVAILABLE WIKI PAGES (use for linking):
{wiki_links}

TEST LAYOUT:
{test_list}

CONFIGURATION FILES:
{config_list}

INSTRUCTIONS:
Produce a single markdown document with these sections:

1. **What This Project Does** — 2-3 paragraphs explaining the purpose, who it's for, and what problem it solves. Write narrative prose, not bullet lists.

2. **Architecture at a Glance** — A Mermaid component diagram showing how the main subsystems connect. Below the diagram, briefly describe each layer and link to wiki pages where available using relative links like `[ComponentName](files/path/to/file.md)`.

3. **How It Works** — For each execution flow diagram provided above, create a subsection with:
   - The flow title as an H3 heading
   - The Mermaid diagram inlined VERBATIM (do not modify it)
   - A narrative walkthrough that references wiki pages with links like `[FileName](files/path/to/file.md)`

4. **Getting Started** — Prerequisites, install commands, how to run. Based on the tech stack and config files.

5. **Key Concepts** — A markdown table of important terms/concepts a newcomer needs to know, derived from the code entities visible in the execution flows.

6. **Development Workflow** — How to run tests, lint, and do common development tasks. Based on the test layout and config files.

7. **Further Reading** — Links to Architecture, Dependencies, Glossary, and Changelog wiki pages using relative links: `[Architecture](architecture.md)`, `[Dependencies](dependencies.md)`, `[Glossary](glossary.md)`, `[Changelog](changelog.md)`.

CRITICAL RULES:
- Use relative wiki links for file references: `[Name](files/path/to/file.md)`
- Inline Mermaid diagrams from the execution flows VERBATIM — do not regenerate them
- Write narrative prose, not bullet lists, for descriptive sections
- The Key Concepts table should have columns: Concept | What It Means
- Start the document with `# Developer Onboarding Guide`
"""

    guide = await llm.generate(prompt, system_prompt="You are a technical writer creating developer documentation.")
    return guide


async def generate_rich_onboarding(
    repo_path: Path,
    vector_store: Any,
    llm: Any,
    *,
    detail_level: str = "full",
) -> dict[str, Any]:
    """Generate a rich onboarding guide with diagrams, narrative, and wiki links.

    Requires prior indexing — uses vector store for codemap generation
    and LLM for flow selection and synthesis.

    Args:
        repo_path: Path to the indexed repository.
        vector_store: Initialized VectorStore instance.
        llm: LLM provider for flow selection and synthesis.
        detail_level: Detail level (currently always produces full output).

    Returns:
        Dict with ``status``, ``guide`` (markdown string), and ``codemaps``
        (list of codemap dicts).
    """
    # Phase 1: Gather basics
    basics = generate_onboarding_guide(repo_path, detail_level=detail_level)
    manifest: ProjectManifest = basics["manifest"]
    entry_points: list[Path] = basics["entry_points"]
    directory_tree: str = basics["directory_tree"]
    test_layout: list[Path] = basics["test_layout"]
    config_files: list[Path] = basics["config_files"]

    # Phase 2: LLM flow selection
    flows = await _select_flows_with_llm(
        llm, manifest, entry_points, directory_tree
    )

    # Phase 3: Codemap generation
    codemaps = await _generate_codemaps_for_flows(
        flows, vector_store, repo_path, llm
    )

    # Collect wiki page paths for linking
    wiki_path = repo_path / ".deepwiki"
    wiki_pages: list[str] = []
    if wiki_path.exists():
        for md_file in sorted(wiki_path.rglob("*.md")):
            try:
                wiki_pages.append(str(md_file.relative_to(wiki_path)))
            except ValueError:
                continue

    # Phase 4: LLM synthesis
    guide = await _synthesize_onboarding_guide(
        llm,
        manifest,
        directory_tree,
        entry_points,
        codemaps,
        wiki_pages,
        test_layout,
        config_files,
    )

    return {
        "status": "success",
        "guide": guide,
        "codemaps": codemaps,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_onboarding.py::TestGenerateRichOnboarding -x -q`
Expected: 3 passed.

- [ ] **Step 5: Run existing onboarding tests to verify no regression**

Run: `uv run pytest tests/test_onboarding.py -x -q`
Expected: All tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/generators/analysis/onboarding.py tests/test_onboarding.py
git commit -m "feat: add generate_rich_onboarding with LLM flow selection and codemap diagrams"
```

---

## Task 2: Update the MCP handler

Change `handle_get_onboarding_guide` to call `generate_rich_onboarding` and save the result to `.deepwiki/onboarding.md`.

**Files:**
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:546-578`
- Test: `tests/test_onboarding.py`

- [ ] **Step 1: Write the test for the updated handler**

Add to `tests/test_onboarding.py`:

```python
class TestHandleGetOnboardingGuide:
    """Tests for the updated MCP handler."""

    @patch("local_deepwiki.handlers.analysis_architecture.generate_rich_onboarding")
    @patch("local_deepwiki.handlers.analysis_architecture.get_access_controller")
    async def test_handler_calls_rich_onboarding(
        self, mock_acl, mock_rich, tmp_path
    ):
        from local_deepwiki.handlers.analysis_architecture import handle_get_onboarding_guide

        mock_acl.return_value = MagicMock()
        mock_rich.return_value = {
            "status": "success",
            "guide": "# Developer Onboarding Guide\n\nTest guide.",
            "codemaps": [],
        }

        # Create repo dir and .deepwiki dir
        (tmp_path / ".deepwiki").mkdir()

        result = await handle_get_onboarding_guide(
            {"repo_path": str(tmp_path), "detail_level": "full"}
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "Onboarding" in data["guide"]
        # Verify it was saved to disk
        onboarding_path = tmp_path / ".deepwiki" / "onboarding.md"
        assert onboarding_path.exists()
        assert "Onboarding" in onboarding_path.read_text()

    @patch("local_deepwiki.handlers.analysis_architecture.generate_rich_onboarding")
    @patch("local_deepwiki.handlers.analysis_architecture.get_access_controller")
    async def test_handler_falls_back_on_missing_index(
        self, mock_acl, mock_rich, tmp_path
    ):
        from local_deepwiki.handlers.analysis_architecture import handle_get_onboarding_guide

        mock_acl.return_value = MagicMock()
        mock_rich.side_effect = Exception("No vector store")

        # Fallback should use the basic generator
        result = await handle_get_onboarding_guide(
            {"repo_path": str(tmp_path), "detail_level": "standard"}
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "guide" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_onboarding.py::TestHandleGetOnboardingGuide -x -q`
Expected: FAIL — handler still calls old function.

- [ ] **Step 3: Update the handler**

Replace the body of `handle_get_onboarding_guide` in `src/local_deepwiki/handlers/analysis_architecture.py` (lines 546-578):

```python
async def handle_get_onboarding_guide(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_onboarding_guide tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetOnboardingGuideArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    wiki_path = repo_path / ".deepwiki"

    # Try rich onboarding (requires index + vector store + LLM)
    try:
        from local_deepwiki.generators.analysis.onboarding import generate_rich_onboarding
        from local_deepwiki.handlers._index_helpers import _create_vector_store
        from local_deepwiki.services.provider_factory import create_llm_provider

        vector_store = await _create_vector_store(repo_path)
        llm = create_llm_provider()

        result = await generate_rich_onboarding(
            repo_path=repo_path,
            vector_store=vector_store,
            llm=llm,
            detail_level=validated.detail_level,
        )
        guide = result["guide"]

        # Save to wiki
        if wiki_path.exists():
            (wiki_path / "onboarding.md").write_text(guide)
            _ensure_toc_entry(wiki_path)

        logger.info("Rich onboarding guide generated for %s", repo_path)
        return make_tool_text_content(
            "get_onboarding_guide",
            {
                "status": "success",
                "guide": guide,
                "tool": "get_onboarding_guide",
            },
        )
    except Exception:
        logger.info("Rich onboarding unavailable, falling back to basic for %s", repo_path)

    # Fallback to basic onboarding
    from local_deepwiki.generators.analysis.onboarding import (
        format_onboarding_guide,
        generate_onboarding_guide,
    )

    result = generate_onboarding_guide(repo_path, detail_level=validated.detail_level)
    guide = format_onboarding_guide(result, detail_level=validated.detail_level)

    logger.info("Basic onboarding guide generated for %s", repo_path)
    return make_tool_text_content(
        "get_onboarding_guide",
        {
            "status": "success",
            "guide": guide,
            "tool": "get_onboarding_guide",
        },
    )
```

- [ ] **Step 4: Add the `_ensure_toc_entry` helper**

Add above `handle_get_onboarding_guide` in the same file:

```python
def _ensure_toc_entry(wiki_path: Path) -> None:
    """Insert an Onboarding Guide entry into toc.json if not already present."""
    from local_deepwiki.generators.toc import TocEntry, read_toc, write_toc

    toc = read_toc(wiki_path)
    if toc is None:
        return

    # Check if already present
    for entry in toc.entries:
        if entry.path == "onboarding.md":
            return

    # Insert at position 1 (after Overview which is position 0)
    new_entry = TocEntry(number="", title="Onboarding Guide", path="onboarding.md")
    insert_pos = min(1, len(toc.entries))
    toc.entries.insert(insert_pos, new_entry)

    # Renumber all entries
    for i, entry in enumerate(toc.entries):
        entry.number = str(i + 1)

    write_toc(toc, wiki_path)
```

- [ ] **Step 5: Add the `create_llm_provider` import check**

Verify `create_llm_provider` exists:

Run: `uv run python -c "from local_deepwiki.services.provider_factory import create_llm_provider; print('OK')"`

If it doesn't exist, check the actual factory function name:

Run: `grep -n 'def create_llm' src/local_deepwiki/services/provider_factory.py`

Adjust the import in the handler to match the actual function name.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_onboarding.py::TestHandleGetOnboardingGuide -x -q`
Expected: 2 passed.

- [ ] **Step 7: Run all onboarding tests**

Run: `uv run pytest tests/test_onboarding.py -x -q`
Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/local_deepwiki/handlers/analysis_architecture.py tests/test_onboarding.py
git commit -m "feat: update onboarding handler to use rich generator with wiki save and TOC entry"
```

---

## Task 3: Hook into wiki generation pipeline

Call `generate_rich_onboarding` during `deepwiki update` after wiki pages are generated.

**Files:**
- Modify: `src/local_deepwiki/generators/wiki/phases.py`
- Test: `tests/test_onboarding.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_onboarding.py`:

```python
class TestOnboardingInPipeline:
    """Tests for onboarding generation during wiki pipeline."""

    @patch("local_deepwiki.generators.wiki.phases.generate_rich_onboarding")
    async def test_generate_onboarding_page_called(self, mock_rich, tmp_path):
        from local_deepwiki.generators.wiki.phases import generate_onboarding_page

        mock_rich.return_value = {
            "status": "success",
            "guide": "# Developer Onboarding Guide\n\nGenerated.",
            "codemaps": [],
        }

        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        mock_generator = MagicMock()
        mock_generator.wiki_path = wiki_path
        mock_generator.vector_store = MagicMock()
        mock_generator.llm = MagicMock()

        result = await generate_onboarding_page(
            repo_path=tmp_path,
            wiki_path=wiki_path,
            vector_store=mock_generator.vector_store,
            llm=mock_generator.llm,
        )

        assert result is not None
        assert result.path == "onboarding.md"
        assert "Onboarding" in result.content
        mock_rich.assert_called_once()

    @patch("local_deepwiki.generators.wiki.phases.generate_rich_onboarding")
    async def test_generate_onboarding_page_failure_returns_none(self, mock_rich, tmp_path):
        from local_deepwiki.generators.wiki.phases import generate_onboarding_page

        mock_rich.side_effect = RuntimeError("LLM unavailable")

        result = await generate_onboarding_page(
            repo_path=tmp_path,
            wiki_path=tmp_path / ".deepwiki",
            vector_store=MagicMock(),
            llm=MagicMock(),
        )

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_onboarding.py::TestOnboardingInPipeline -x -q`
Expected: FAIL — `generate_onboarding_page` does not exist.

- [ ] **Step 3: Add `generate_onboarding_page` to phases.py**

Add at the end of `src/local_deepwiki/generators/wiki/phases.py`:

```python
async def generate_onboarding_page(
    repo_path: Path,
    wiki_path: Path,
    vector_store: Any,
    llm: Any,
    index_status: IndexStatus | None = None,
    status_manager: Any | None = None,
    full_rebuild: bool = False,
) -> WikiPage | None:
    """Generate the rich onboarding page for the wiki.

    Returns a WikiPage if successful, None if generation fails.
    This is called during the auxiliary pages phase of wiki generation.
    Skips regeneration if the structural fingerprint is unchanged.
    """
    from local_deepwiki.generators.analysis.onboarding import generate_rich_onboarding

    page_path = "onboarding.md"

    # Check if regeneration is needed (structural fingerprint)
    if (
        not full_rebuild
        and status_manager is not None
        and index_status is not None
        and not status_manager.needs_regeneration_structural(page_path, index_status)
    ):
        existing = await status_manager.load_existing_page(page_path)
        if existing is not None:
            logger.info("Onboarding guide unchanged, using cached version")
            return existing

    try:
        result = await generate_rich_onboarding(
            repo_path=repo_path,
            vector_store=vector_store,
            llm=llm,
        )
        guide = result.get("guide", "")
        if not guide:
            return None

        import time

        return WikiPage(
            path=page_path,
            title="Developer Onboarding Guide",
            content=guide,
            generated_at=time.time(),
        )
    except Exception:
        logger.warning("Rich onboarding generation failed, skipping")
        return None
```

- [ ] **Step 4: Wire `generate_onboarding_page` into `generate_auxiliary_pages`**

In `src/local_deepwiki/generators/wiki/phases.py`, add the onboarding call at the end of `generate_auxiliary_pages` (after line 575, before the function ends):

```python
    # Generate onboarding guide (requires vector store + LLM)
    onboarding_page = await generate_onboarding_page(
        repo_path=Path(index_status.repo_path),
        wiki_path=generator.wiki_path,
        vector_store=generator.vector_store,
        llm=generator.llm,
        index_status=index_status,
        status_manager=status_manager,
        full_rebuild=ctx.full_rebuild,
    )
    if onboarding_page is not None:
        ctx.pages.append(onboarding_page)
        await generator._write_page(onboarding_page)
        ctx.pages_generated += 1
```

- [ ] **Step 5: Add `Path` import if not already present**

Check if `Path` is imported at the top of `phases.py`. It's used in `generate_onboarding_page` and the new call in `generate_auxiliary_pages`. The file already imports `from pathlib import Path` indirectly via TYPE_CHECKING — verify it's available at runtime. If not, add `from pathlib import Path` to the runtime imports.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_onboarding.py::TestOnboardingInPipeline -x -q`
Expected: 2 passed.

- [ ] **Step 7: Run all onboarding tests + phases tests**

Run: `uv run pytest tests/test_onboarding.py tests/test_wiki_pages_gen.py -x -q`
Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add src/local_deepwiki/generators/wiki/phases.py tests/test_onboarding.py
git commit -m "feat: hook rich onboarding into wiki generation pipeline"
```

---

## Task 4: Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -q`
Expected: 6,037+ tests pass, 0 failures related to onboarding changes.

- [ ] **Step 2: Test end-to-end with the MCP tool**

Run: Use the `get_onboarding_guide` MCP tool on this repo to verify it produces a rich guide with diagrams and wiki links.

- [ ] **Step 3: Verify wiki integration**

Check that `.deepwiki/onboarding.md` was created and that `toc.json` has the Onboarding Guide entry.

- [ ] **Step 4: Commit spec and plan**

```bash
git add docs/superpowers/specs/2026-03-27-rich-onboarding-guide-design.md docs/superpowers/plans/2026-03-27-rich-onboarding-guide.md
git commit -m "docs: add rich onboarding guide spec and plan"
```

---

## Execution Notes

**Task dependencies:** Tasks 1 → 2 → 3 → 4 (sequential — each builds on the previous).

**Risk areas:**
- **LLM provider creation in the handler** (Task 2, Step 5): The factory function name may differ from `create_llm_provider`. The step includes a verification check.
- **Wiki generator attributes** (Task 3, Step 4): The `generator.llm` attribute must exist on `WikiGenerator`. If it doesn't, the LLM will need to be created via the provider factory instead.
- **TOC renumbering** (Task 2, Step 4): The `TocEntry.number` field is a string. After inserting, all entries are renumbered sequentially.

**What we're NOT building:**
- No changes to `generate_codemap()` — used as-is
- No new MCP tools — enhancing the existing `get_onboarding_guide`
- No changes to the web UI — it already renders any wiki page with Mermaid support
