# Local DeepWiki Improvement Roadmap

*Generated 2026-01-11 based on comparison with Cognition's DeepWiki*

## High Priority (Close the gap with Cognition)

- [x] **Hierarchical numbered TOC** - Add "1, 1.1, 1.2" structure like Cognition's wiki instead of flat lists *(completed 2026-01-12)*
- [x] **"Relevant source files" section** - Each wiki page should cite which source files informed it with direct links *(completed 2026-01-12)*
- [x] **Line-number references** - Use `parser.py:42-150` format instead of just `parser.py` for precision *(completed 2026-01-12)*

## Medium Priority (UX improvements)

- [x] **Search bar in web UI** - Add search functionality to the Flask web interface *(completed 2026-01-12)*
- [x] **Better web UI styling** - Theme toggle, collapsible sidebar, syntax highlighting *(completed 2026-01-12)*

## Lower Priority (Nice to have)

- [x] **Deep Research mode** - Multi-step reasoning for complex architectural questions *(completed 2026-01-13)*
- [x] **More languages** - Added support for Ruby, PHP, Kotlin, C# *(completed)*
- [x] **Static HTML export** - Generate deployable static site for GitHub Pages or internal hosting *(completed)*

## Context

These priorities were determined by comparing local-deepwiki output against Cognition's DeepWiki (deepwiki.com). Key differences:

- Cognition has a polished hierarchical navigation structure
- Cognition pages cite "Relevant source files" with GitHub links
- Cognition has an in-browser conversational Q&A and "Deep Research" mode

Our advantages to preserve:
- Privacy (fully local, code never leaves machine)
- Works on private repos without subscription
- MCP integration for Claude Code workflows
- Customizable LLM/embedding providers
