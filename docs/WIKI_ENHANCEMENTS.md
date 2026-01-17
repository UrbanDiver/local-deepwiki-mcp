# Wiki Enhancement Ideas

Future improvements for the generated DeepWiki documentation.

## Content Quality

| Improvement | Description | Status |
|-------------|-------------|--------|
| **Richer LLM context** | Pass related files, imports, and callers to LLM for better understanding | ✅ Done |
| **Usage examples from tests** | Expand test_examples.py to find more real usage patterns | ✅ Done |
| **Exception documentation** | Document what exceptions each function can raise | ✅ Done |
| **Type annotations** | Extract and display full type signatures including generics | ✅ Done |

## Visual & Diagrams

| Improvement | Description | Status |
|-------------|-------------|--------|
| **Sequence diagrams** | Show typical call flows (e.g., indexing pipeline, query flow) | ✅ Done |
| **Module dependency graph** | Visual graph of which modules import which | ✅ Done (in architecture.md) |
| **Data flow diagrams** | Show how data transforms through the system | ❌ Not done |
| **Inheritance trees** | Show class hierarchies across files | ✅ Done (inheritance.md) |

## Navigation & Discovery

| Improvement | Description | Status |
|-------------|-------------|--------|
| **"Used by" sections** | Show which files/functions call each function | ✅ Done (via context_builder) |
| **Better search** | Fuzzy search, filter by type (class/function/module) | ✅ Done |
| **Glossary/Index** | Alphabetical index of all entities | ✅ Done (glossary.md) |
| **Quick links** | Jump to related concepts mentioned in docs | ✅ Done (crosslinks.py) |
| **Collapsible sidebar** | Expandable/collapsible TOC navigation | ✅ Done |

## Integration

| Improvement | Description | Status |
|-------------|-------------|--------|
| **GitHub source links** | Link "View Source" to actual GitHub file+line | ✅ Done |
| **Git blame integration** | Show who last modified each function | ✅ Done |
| **Changelog per function** | Show when each function was added/modified | ❌ Not done |

## Quality Assurance

| Improvement | Description | Status |
|-------------|-------------|--------|
| **Doc coverage report** | Show % of functions with descriptions | ✅ Done (coverage.md) |
| **Stale doc detection** | Flag docs that might be outdated | ✅ Done (freshness.md) |
| **Example validation** | Verify code examples actually work | ❌ Not done |

## Summary

**Completed: 17/20 (85%)**

### Remaining Items
1. **Data flow diagrams** - Show how data transforms through the system (High effort)
2. **Changelog per function** - Show when each function was added/modified (High effort)
3. **Example validation** - Verify code examples actually work (High effort)
