# Rich Onboarding Guide Generator

## Problem

The current `get_onboarding_guide` tool produces shallow output: it lists entry points by filename pattern, ranks "key modules" by line count, and dumps a directory tree. It has no semantic understanding of the codebase — no diagrams, no narrative, no wiki links. The result is not useful for a developer trying to understand a new project.

Meanwhile, the codemap generator and wiki system already produce rich execution-flow diagrams, LLM narratives, and interlinked wiki pages — but they're separate tools that aren't composed into a coherent onboarding experience.

## Goal

Replace the onboarding generator with an enhanced version that produces a single-page, LLM-synthesized onboarding guide with:

1. **Execution-flow diagrams** — Mermaid codemaps tracing 3 key flows selected by the LLM
2. **Narrative prose** — LLM-written explanations of what the project does, how components relate, and why they exist
3. **Wiki links** — Every file/module/function reference links to its generated wiki page

The guide is auto-generated on every `deepwiki update` and saved to `.deepwiki/onboarding.md` with a TOC entry.

## Requirements

- Requires prior indexing (vector store + wiki pages must exist)
- Produces a single markdown page
- Auto-generated during `deepwiki update` / `index_repository` (after wiki pages are generated so links are valid)
- Also returned as tool output when `get_onboarding_guide` is called
- Saved to `.deepwiki/onboarding.md` with TOC entry at position 2 (after Overview)
- Uses incremental status checking — skips regeneration if structure unchanged
- ~5 LLM calls per generation (2 direct + 3 via codemap), cached by LLM cache

## Architecture

A new async function `generate_rich_onboarding()` in `generators/analysis/onboarding.py` orchestrates 4 phases:

### Phase 1: Gather Basics

Call existing `generate_onboarding_guide()` for manifest, entry points, config files, directory tree, test layout, key modules.

### Phase 2: LLM Flow Selection

Feed the LLM a structured prompt with:
- Manifest summary (name, description, tech stack)
- Entry point list
- Directory tree (truncated)
- Top-10 entities by import count from vector store

Prompt: "You are helping a developer new to this codebase. Given the project structure below, pick the 3 most important execution flows to understand. Return JSON: `[{"entry_point": "function_name", "query": "How does X work?", "title": "short title"}]`"

Parse as JSON. Fallback: use first 3 discovered entry points with generic queries if parsing fails.

### Phase 3: Codemap Generation

For each of the 3 selected flows, call `generate_codemap()` with the entry point and query. Each codemap call produces:
- A Mermaid execution-flow diagram
- A narrative trace with file:line references
- A list of files involved

### Phase 4: LLM Synthesis

Assemble all context into a synthesis prompt:
- Project manifest
- Directory tree
- Entry points with descriptions
- 3 codemap results (diagrams + narratives)
- List of wiki page paths (for linking)
- Config files and test layout

Prompt instructs the LLM to produce the full onboarding guide following this output template:

```
# Developer Onboarding Guide

## What This Project Does
  LLM narrative: purpose, who it's for, what problem it solves

## Architecture at a Glance
  Mermaid diagram: high-level component graph
  Layer descriptions with wiki links

## How It Works
  ### [Flow 1 Title]
    Mermaid execution-flow diagram (inlined verbatim from codemap)
    Narrative trace with wiki page links
  ### [Flow 2 Title]
    ...
  ### [Flow 3 Title]
    ...

## Getting Started
  Prerequisites, setup commands, configuration (from manifest)

## Key Concepts
  Table of terms and what they mean (LLM-generated from entity names)

## Development Workflow
  Testing commands, linting, common tasks (from manifest + test layout)

## Further Reading
  Links to Architecture, Dependencies, Glossary wiki pages
```

LLM instructions:
- Use relative wiki links for every file/module/function reference (e.g., `[CodeParser](files/src/.../code_parser.md)`)
- Inline Mermaid diagrams from codemaps verbatim — do not regenerate them
- Write narrative prose, not bullet lists
- Include a Key Concepts table derived from codebase entities

## Integration Points

### `deepwiki update` / `index_repository`

In `generators/wiki/phases.py`, call `generate_rich_onboarding()` during the auxiliary pages phase, after file docs and module docs are complete (so wiki page links are valid). Save output to `.deepwiki/onboarding.md`.

### `get_onboarding_guide` MCP tool

Update `handle_get_onboarding_guide` in `handlers/analysis_search.py` to call `generate_rich_onboarding()` instead of the basic version. Return the markdown and save to disk.

### TOC management

On first generation, insert `{"title": "Onboarding Guide", "path": "onboarding.md"}` into `toc.json` at position 2 (after Overview, before Architecture). On subsequent runs, leave the existing entry in place.

### Incremental updates

Use the wiki status manager's `needs_regeneration_structural` method to check if `onboarding.md` needs regeneration. This triggers when the set of indexed files changes (files added/removed), which implies entry points or modules may have changed. Skip if the structural fingerprint is unchanged.

## Files Modified

| File | Change |
|------|--------|
| `generators/analysis/onboarding.py` | Add `generate_rich_onboarding()` async function. Keep existing sync functions for backward compat. |
| `generators/wiki/phases.py` | Call onboarding generation in auxiliary pages phase |
| `handlers/analysis_search.py` | Update `handle_get_onboarding_guide` to use rich version |

No new files. Extends existing onboarding module and hooks into existing phases.

## LLM Cost

- Flow selection: 1 LLM call (~small context)
- Codemap narratives: 3 LLM calls (1 per flow, via `generate_codemap()`)
- Synthesis: 1 LLM call (~large context with all codemaps assembled)
- Total: ~5 LLM calls per generation
- All calls go through the LLM cache, so identical re-runs are free

## Constraints

- No new files — extend existing `onboarding.py`
- No new MCP tools — enhance the existing `get_onboarding_guide`
- No changes to `generate_codemap()` — use it as-is
- Wiki links must use relative paths that work in the web UI
- Mermaid diagrams must be inlined verbatim from codemap output (not LLM-regenerated)
- Fallback gracefully if LLM flow selection fails (use entry point heuristics)
- Fallback gracefully if any individual codemap generation fails (include the flows that succeeded)
