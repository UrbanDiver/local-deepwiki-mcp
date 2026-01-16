# Wiki Enhancement Ideas

Future improvements for the generated DeepWiki documentation.

## Content Quality

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **Richer LLM context** | Pass related files, imports, and callers to LLM for better understanding | Medium |
| **Usage examples from tests** | Expand test_examples.py to find more real usage patterns | Low |
| **Exception documentation** | Document what exceptions each function can raise | Medium |
| **Type annotations** | Extract and display full type signatures including generics | Low |

## Visual & Diagrams

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **Sequence diagrams** | Show typical call flows (e.g., indexing pipeline, query flow) | Medium |
| **Module dependency graph** | Visual graph of which modules import which | Medium |
| **Data flow diagrams** | Show how data transforms through the system | High |
| **Inheritance trees** | Show class hierarchies across files | Low |

## Navigation & Discovery

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **"Used by" sections** | Show which files/functions call each function | Medium |
| **Better search** | Fuzzy search, filter by type (class/function/module) | Medium |
| **Glossary/Index** | Alphabetical index of all entities | Low |
| **Quick links** | Jump to related concepts mentioned in docs | Low |

## Integration

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **GitHub source links** | Link "View Source" to actual GitHub file+line | Low |
| **Git blame integration** | Show who last modified each function | Medium |
| **Changelog per function** | Show when each function was added/modified | High |

## Quality Assurance

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **Doc coverage report** | Show % of functions with descriptions | Low |
| **Stale doc detection** | Flag docs that might be outdated | Medium |
| **Example validation** | Verify code examples actually work | High |

## Priority Implementation

1. **GitHub source links** - Low effort, high value
2. **"Used by" sections** - Leverages existing call graph
3. **Module dependency graph** - Visual impact
