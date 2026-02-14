# Plan: AI Agent Usability Improvements

Status: **Not started**
Created: 2026-02-13

## Summary

Evaluation of 40 MCP tools, handlers, response formats, error system, agentic tools, llms.txt, MCP Resources, and validation — with prioritized improvements for AI agent consumption.

## Existing Strengths

- `suggest_next_actions` with static tool graph (zero LLM cost)
- `run_workflow` presets (onboarding, security_audit, full_analysis, quick_refresh)
- `query_codebase` with auto-escalation to `deep_research`
- `batch_explain_entities` to reduce round-trips
- Structured error hierarchy with actionable hints (`errors.py`)
- Progress tracking for long operations (`ProgressNotifier`)
- `llms.txt` generation and `deepwiki://` MCP Resources
- Agentic RAG with relevance grading + query rewriting

---

## Priority 1: Consistency & Discoverability

### 1. Inconsistent response envelopes
- [ ] Only the 4 agentic tools use `wrap_tool_response` (`{tool, status, data, hints}`). The other 36 tools return raw JSON with ad-hoc shapes.
- [ ] Migrate all handlers to the envelope format, or at minimum add `status` and `tool` keys to every response.
- Files: `handlers/core.py`, `handlers/generators.py`, `handlers/analysis*.py`, `handlers/codemap.py`, `handlers/research.py`

### 2. No MCP Prompts
- [ ] Register MCP `prompts/list` capability with templated prompts for common agent workflows.
- High-value candidates:
  - "Onboard me to this codebase" (combines index check + wiki structure + stats)
  - "Explain this code change" (wraps analyze_diff + ask_about_diff)
  - "Find and explain entity" (wraps fuzzy_search + explain_entity)
- File: `server.py` (register prompt handlers)

### 3. Missing tool annotations (MCP 2025-03-26)
- [ ] Add `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` to all 40 Tool objects.
- Examples: `index_repository` is destructive/non-idempotent; `search_code` is read-only/idempotent.
- File: `server_tool_defs.py`

### 4. No tool dependency declarations
- [ ] ~30 tools require an existing index but this isn't formalized.
- [ ] Add `"requires_index": true` to tool annotations or descriptions so agents can plan correctly.
- [ ] Consider a `check_prerequisites` meta-tool that validates before execution.
- File: `server_tool_defs.py`

---

## Priority 2: Agent Intelligence

### 5. `suggest_next_actions` ignores `context` parameter
- [ ] The `context` field is accepted in `SuggestNextActionsArgs` but never read by the handler (dead code).
- [ ] Wire it up: if context mentions "security", prioritize `detect_secrets` and `security_audit`; if "onboarding", prioritize wiki/stats tools.
- File: `handlers/agentic.py`

### 6. `query_codebase` escalation threshold is fragile
- [ ] Escalating when `len(answer) < 200` is arbitrary — some valid answers are short.
- [ ] Use agentic RAG confidence metadata (`relevant_fraction`) or LLM self-evaluation instead.
- File: `handlers/agentic.py:666`

### 7. `batch_explain_entities` is shallow
- [ ] Currently only does search index lookups (name -> file/type/signature).
- [ ] The real `explain_entity` handler composes call graph, inheritance, test examples, and API docs.
- [ ] Add a `depth` parameter (`"shallow"` vs `"full"`) to optionally support the full composite explanation.
- File: `handlers/agentic.py`, `server_tool_defs.py`

### 8. Semantic tool selection helper
- [ ] 40 tools is a large surface for agents to navigate.
- [ ] Add a `find_tools` meta-tool: takes natural language intent, returns top-3 matching tools with example args.
- [ ] Can be done via keyword matching against descriptions (zero LLM cost).
- Files: new handler + tool definition

---

## Priority 3: Output Quality for Agents

### 9. Missing `llms-full.txt`
- [ ] The llmstxt.org spec recommends both `llms.txt` (summary) and `llms-full.txt` (full concatenated content).
- [ ] Only the summary version is currently generated.
- File: `generators/llms_txt.py`

### 10. `llms.txt` not exposed as MCP Resource
- [ ] The generated file isn't discoverable via `resources/list`.
- [ ] Register it as a `deepwiki://` resource.
- File: `handlers/resources.py`

### 11. Tool descriptions lack examples
- [ ] Descriptions are good prose but agents perform better with concrete input examples.
- [ ] Append example args to descriptions, e.g.: `Example: {"repo_path": "/path", "query": "auth middleware", "language": "python"}`
- File: `server_tool_defs.py`

### 12. No structured output schemas
- [ ] Tool definitions specify `inputSchema` but no output schema.
- [ ] Add informal output schema in descriptions or formal output schema if MCP supports it.
- [ ] E.g., "Returns: `{answer, sources[{file, lines, score}], agentic_rag?}`"
- File: `server_tool_defs.py`

---

## Priority 4: Performance & Resilience

### 13. `run_workflow` steps are sequential
- [ ] Independent steps in `_run_onboarding` and `_run_full_analysis` could run concurrently via `asyncio.gather`.
- [ ] E.g., `get_wiki_stats` and `suggest_codemap_topics` have no dependency.
- File: `handlers/agentic.py`

### 14. Error responses lack retry metadata
- [ ] Rate-limit and transient errors return hints as prose.
- [ ] Add structured `retry_after_seconds` or `retryable: true` fields for agent backoff.
- File: `handlers/_shared.py` (`handle_tool_errors`), `errors.py`

### 15. No session state tracking
- [ ] `suggest_next_actions` requires agents to pass `tools_used` manually.
- [ ] If the server tracked per-session tool invocation history, suggestions could be automatic.
- Files: `server.py` (track calls), `handlers/agentic.py`

---

## Quick Wins (Low Effort, High Impact)

| Change | Effort | Impact | Item |
|--------|--------|--------|------|
| Add MCP tool annotations (`readOnlyHint`, etc.) | Low | High | #3 |
| Wire up `context` in `suggest_next_actions` | Low | Medium | #5 |
| Expose `llms.txt` as MCP Resource | Low | Medium | #10 |
| Add `requires_index` note to tool descriptions | Low | High | #4 |
| Parallelize `run_workflow` independent steps | Low | Medium | #13 |
| Generate `llms-full.txt` alongside `llms.txt` | Medium | High | #9 |
| Standardize response envelope on all 40 tools | Medium | High | #1 |
| Register 3-5 MCP Prompts | Medium | High | #2 |
