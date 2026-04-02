# Design Smells

## Summary by Type

| Type | Count |
|------|-------|
| Long Parameter List | 18 |
| Feature Envy | 12 |
| Large File | 7 |

## Severity Summary

- **Total smells:** 37
- **Medium:** 37

## Long Parameter List

| Entity | File | Severity | Description | Suggestion |
|--------|------|----------|-------------|------------|
| `run_wizard` | `src/local_deepwiki/cli/init_cli.py:426` | medium | Function has 8 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `run_search` | `src/local_deepwiki/cli/interactive_search.py:615` | medium | Function has 11 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `run_update` | `src/local_deepwiki/cli/update_cli.py:257` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `batch_embed` | `src/local_deepwiki/core/vectorstore/embedding.py:361` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `_record_and_cache` | `src/local_deepwiki/core/vectorstore/mixins/search.py:167` | medium | Function has 8 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `search` | `src/local_deepwiki/core/vectorstore/mixins/search.py:277` | medium | Function has 13 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `search_paginated` | `src/local_deepwiki/core/vectorstore/mixins/search.py:346` | medium | Function has 13 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `_execute_paginated_search` | `src/local_deepwiki/core/vectorstore/search_engine.py:303` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `__init__` | `src/local_deepwiki/core/vectorstore/search_engine.py:361` | medium | Function has 9 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `__init__` | `src/local_deepwiki/core/vectorstore/store.py:114` | medium | Function has 11 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `build_cross_file_graph` | `src/local_deepwiki/generators/codemap/graph.py:552` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `generate_file_docs` | `src/local_deepwiki/generators/wiki/files.py:703` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `__init__` | `src/local_deepwiki/generators/wiki/generator.py:109` | medium | Function has 8 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `generate_wiki` | `src/local_deepwiki/generators/wiki/generator.py:384` | medium | Function has 11 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `_safe_executor_page` | `src/local_deepwiki/generators/wiki/phases.py:414` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `generate_onboarding_page` | `src/local_deepwiki/generators/wiki/phases.py:629` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `_generate_onboarding_core` | `src/local_deepwiki/generators/wiki/phases.py:656` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |
| `generate_codemap_pages_phase` | `src/local_deepwiki/generators/wiki/postprocessing.py:43` | medium | Function has 7 parameters (threshold: 6) | Introduce a parameter object or configuration dataclass. |

## Feature Envy

| Entity | File | Severity | Description | Suggestion |
|--------|------|----------|-------------|------------|
| `_format_llm_section` | `src/local_deepwiki/cli/config_cli.py:26` | medium | Function calls 'llm_branch' methods 7 times — it may belong there (threshold: 5) | Consider moving this function to the 'llm_branch' class. |
| `_format_cache_section` | `src/local_deepwiki/cli/config_cli.py:95` | medium | Function calls 'cache_branch' methods 6 times — it may belong there (threshold: 5) | Consider moving this function to the 'cache_branch' class. |
| `cmd_health_check` | `src/local_deepwiki/cli/config_cli.py:541` | medium | Function calls 'checks' methods 7 times — it may belong there (threshold: 5) | Consider moving this function to the 'checks' class. |
| `_format_dependency_structure` | `src/local_deepwiki/generators/analysis/architecture_report.py:127` | medium | Function calls 'e' methods 6 times — it may belong there (threshold: 5) | Consider moving this function to the 'e' class. |
| `_recommendations_from_smells` | `src/local_deepwiki/generators/analysis/recommendations.py:106` | medium | Function calls 'smell' methods 6 times — it may belong there (threshold: 5) | Consider moving this function to the 'smell' class. |
| `get_virtual_structure` | `src/local_deepwiki/generators/lazy_generator.py:430` | medium | Function calls 'pages' methods 6 times — it may belong there (threshold: 5) | Consider moving this function to the 'pages' class. |
| `_populate_pyproject_standard` | `src/local_deepwiki/generators/manifest_parsers.py:26` | medium | Function calls 'project' methods 8 times — it may belong there (threshold: 5) | Consider moving this function to the 'project' class. |
| `_build_keywords` | `src/local_deepwiki/generators/search.py:215` | medium | Function calls 'keywords' methods 7 times — it may belong there (threshold: 5) | Consider moving this function to the 'keywords' class. |
| `handle_get_cross_module_dependencies` | `src/local_deepwiki/handlers/analysis_architecture.py:236` | medium | Function calls 'result' methods 7 times — it may belong there (threshold: 5) | Consider moving this function to the 'result' class. |
| `handle_get_coupling_metrics` | `src/local_deepwiki/handlers/analysis_architecture.py:295` | medium | Function calls 'result' methods 7 times — it may belong there (threshold: 5) | Consider moving this function to the 'result' class. |
| `_compute_coverage_stats` | `src/local_deepwiki/handlers/analysis_metadata.py:142` | medium | Function calls 'coverage_data' methods 9 times — it may belong there (threshold: 5) | Consider moving this function to the 'coverage_data' class. |
| `initial_index` | `src/local_deepwiki/watcher.py:480` | medium | Function calls 'progress' methods 6 times — it may belong there (threshold: 5) | Consider moving this function to the 'progress' class. |

## Large File

| Entity | File | Severity | Description | Suggestion |
|--------|------|----------|-------------|------------|
| `api_docs.py` | `src/local_deepwiki/generators/analysis/api_docs.py:1` | medium | File has 828 lines (threshold: 800) | Split into smaller, focused modules. |
| `dependency_graph.py` | `src/local_deepwiki/generators/analysis/dependency_graph.py:1` | medium | File has 852 lines (threshold: 800) | Split into smaller, focused modules. |
| `files.py` | `src/local_deepwiki/generators/wiki/files.py:1` | medium | File has 816 lines (threshold: 800) | Split into smaller, focused modules. |
| `analysis_architecture.py` | `src/local_deepwiki/handlers/analysis_architecture.py:1` | medium | File has 830 lines (threshold: 800) | Split into smaller, focused modules. |
| `tool_args.py` | `src/local_deepwiki/models/tool_args.py:1` | medium | File has 863 lines (threshold: 800) | Split into smaller, focused modules. |
| `analysis_service.py` | `src/local_deepwiki/services/analysis_service.py:1` | medium | File has 806 lines (threshold: 800) | Split into smaller, focused modules. |
| `analysis.py` | `src/local_deepwiki/tool_defs/analysis.py:1` | medium | File has 854 lines (threshold: 800) | Split into smaller, focused modules. |

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/analysis/coupling.py:48-90`](files/src/local_deepwiki/generators/analysis/coupling.md)
- [`src/local_deepwiki/generators/analysis/module_dependencies.py:30-40`](files/src/local_deepwiki/generators/analysis/module_dependencies.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:29-34`](files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:92-94`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](files/src/local_deepwiki/error_factories.md)


*Showing 10 of 263 source files.*
