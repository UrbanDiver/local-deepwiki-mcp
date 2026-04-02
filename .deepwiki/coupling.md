# Coupling Metrics

Robert C. Martin's package coupling metrics measure the stability and abstractness of each module:

- **Ca** (afferent coupling): number of modules that depend on this module
- **Ce** (efferent coupling): number of modules this module depends on
- **I** (instability): Ce / (Ca + Ce) -- 0 = maximally stable, 1 = maximally unstable
- **A** (abstractness): fraction of abstract classes in the module
- **D** (distance from main sequence): |A + I - 1| -- 0 = on the main sequence, 1 = maximally far

## Summary

- **Total modules:** 164
- **Average distance from main sequence:** 0.493
- **Average instability:** 0.491
- **Average abstractness:** 0.039

## Metrics by Module

| Module | Ca | Ce | I | A | D |
|--------|----|----|---|---|---|
| `__init__` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.cache_cli` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.main` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli_progress` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_embedding` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_llm` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_search` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_wiki` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.processing_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.prompts` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.query_utils` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.tracing` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.html_template` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf_styles` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `fixtures.sample_repo` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.dir_tree` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.progress_tracker` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.toc` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._response` | 12 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic_data` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.session_state` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.types` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `logging` | 79 | 0 | 0.000 | 0.000 | 1.000 |
| `models.provider_types` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `models.research` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.credentials` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `security.access_control` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `services.models` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.annotations` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `web` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.rate_limit` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `errors` | 29 | 1 | 0.033 | 0.000 | 0.967 |
| `config` | 33 | 2 | 0.057 | 0.000 | 0.943 |
| `models` | 49 | 6 | 0.109 | 0.000 | 0.891 |
| `core.path_utils` | 13 | 2 | 0.133 | 0.000 | 0.867 |
| `models.chunks` | 6 | 1 | 0.143 | 0.000 | 0.857 |
| `core.rate_limiter` | 5 | 1 | 0.167 | 0.000 | 0.833 |
| `events` | 5 | 1 | 0.167 | 0.000 | 0.833 |
| `security` | 14 | 3 | 0.176 | 0.000 | 0.824 |
| `core.git_utils` | 4 | 1 | 0.200 | 0.000 | 0.800 |
| `core.health_history` | 4 | 1 | 0.200 | 0.000 | 0.800 |
| `core.index_manager` | 8 | 2 | 0.200 | 0.000 | 0.800 |
| `services.protocols` | 1 | 4 | 0.800 | 1.000 | 0.800 |
| `handlers._error_handling` | 14 | 4 | 0.222 | 0.000 | 0.778 |
| `core.vectorstore` | 23 | 6 | 0.207 | 0.036 | 0.757 |
| `generators.manifest` | 9 | 3 | 0.250 | 0.000 | 0.750 |
| `progress` | 3 | 1 | 0.250 | 0.000 | 0.750 |
| `validation` | 6 | 2 | 0.250 | 0.000 | 0.750 |
| `core.parser` | 15 | 2 | 0.118 | 0.200 | 0.682 |
| `cli.profile_cli` | 2 | 1 | 0.333 | 0.000 | 0.667 |
| `config.loader` | 2 | 1 | 0.333 | 0.000 | 0.667 |
| `core.audit` | 2 | 1 | 0.333 | 0.000 | 0.667 |
| `core.chunk_extractors` | 4 | 2 | 0.333 | 0.000 | 0.667 |
| `export.shared` | 2 | 1 | 0.333 | 0.000 | 0.667 |
| `generators.crosslinks` | 4 | 2 | 0.333 | 0.000 | 0.667 |
| `handlers._export_validation` | 2 | 1 | 0.333 | 0.000 | 0.667 |
| `models.wiki` | 2 | 1 | 0.333 | 0.000 | 0.667 |
| `plugins.registry` | 4 | 2 | 0.333 | 0.000 | 0.667 |
| `export.streaming` | 5 | 1 | 0.167 | 0.167 | 0.667 |
| `providers.embeddings` | 10 | 6 | 0.375 | 0.000 | 0.625 |
| `providers.llm` | 8 | 5 | 0.385 | 0.000 | 0.615 |
| `providers.errors` | 3 | 2 | 0.400 | 0.000 | 0.600 |
| `generators.analysis` | 16 | 13 | 0.448 | 0.000 | 0.552 |
| `handlers._index_helpers` | 10 | 9 | 0.474 | 0.000 | 0.526 |
| `cli.config_validator` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `cli.search_models` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `config.provider_models` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `core.git_blame` | 2 | 2 | 0.500 | 0.000 | 0.500 |
| `core.secret_detector` | 2 | 2 | 0.500 | 0.000 | 0.500 |
| `error_factories` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `export.mermaid_renderer` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `generators.changelog` | 2 | 2 | 0.500 | 0.000 | 0.500 |
| `generators.context_builder` | 4 | 4 | 0.500 | 0.000 | 0.500 |
| `generators.diagrams` | 4 | 4 | 0.500 | 0.000 | 0.500 |
| `generators.examples` | 5 | 5 | 0.500 | 0.000 | 0.500 |
| `generators.lazy_cache` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `generators.manifest_parsers` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `generators.protocols` | 1 | 1 | 0.500 | 1.000 | 0.500 |
| `handlers.prompts` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `models.tool_args` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `prompts` | 2 | 2 | 0.500 | 0.000 | 0.500 |
| `providers.retry` | 2 | 2 | 0.500 | 0.000 | 0.500 |
| `security.role_config` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `tool_defs.analysis` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `tool_defs.core` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `tool_defs.generators` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `tool_defs.workflow` | 1 | 1 | 0.500 | 0.000 | 0.500 |
| `web.routes_chat` | 3 | 4 | 0.571 | 0.000 | 0.429 |
| `generators.lazy_generator` | 7 | 10 | 0.588 | 0.000 | 0.412 |
| `core.fuzzy_search` | 2 | 3 | 0.600 | 0.000 | 0.400 |
| `core.indexer_files` | 2 | 3 | 0.600 | 0.000 | 0.400 |
| `handlers._progress` | 2 | 3 | 0.600 | 0.000 | 0.400 |
| `config.models` | 5 | 8 | 0.615 | 0.000 | 0.385 |
| `export.html` | 3 | 5 | 0.625 | 0.000 | 0.375 |
| `providers.base` | 14 | 2 | 0.125 | 0.500 | 0.375 |
| `export` | 1 | 2 | 0.667 | 0.000 | 0.333 |
| `generators.llms_txt` | 1 | 2 | 0.667 | 0.000 | 0.333 |
| `generators.prefetch` | 1 | 2 | 0.667 | 0.000 | 0.333 |
| `generators.search` | 1 | 2 | 0.667 | 0.000 | 0.333 |
| `generators.see_also` | 1 | 2 | 0.667 | 0.000 | 0.333 |
| `security.repository_access` | 1 | 2 | 0.667 | 0.000 | 0.333 |
| `generators.codemap` | 4 | 9 | 0.692 | 0.000 | 0.308 |
| `core.indexer` | 4 | 16 | 0.800 | 0.500 | 0.300 |
| `services.analysis_service` | 3 | 7 | 0.700 | 0.000 | 0.300 |
| `tool_defs` | 2 | 5 | 0.714 | 0.000 | 0.286 |
| `core.graph_rag` | 3 | 8 | 0.727 | 0.000 | 0.273 |
| `web.utils` | 3 | 8 | 0.727 | 0.000 | 0.273 |
| `cli.status_cli` | 1 | 3 | 0.750 | 0.000 | 0.250 |
| `core.chunk_builders` | 1 | 3 | 0.750 | 0.000 | 0.250 |
| `core.llm_cache` | 1 | 3 | 0.750 | 0.000 | 0.250 |
| `export.pdf` | 2 | 6 | 0.750 | 0.000 | 0.250 |
| `generators.source_refs` | 1 | 3 | 0.750 | 0.000 | 0.250 |
| `services.query_service` | 4 | 12 | 0.750 | 0.000 | 0.250 |
| `core.chunker` | 2 | 7 | 0.778 | 0.000 | 0.222 |
| `core.deep_research` | 2 | 7 | 0.778 | 0.000 | 0.222 |
| `services.indexing_service` | 2 | 7 | 0.778 | 0.000 | 0.222 |
| `services.provider_factory` | 2 | 7 | 0.778 | 0.000 | 0.222 |
| `handlers.generators` | 3 | 11 | 0.786 | 0.000 | 0.214 |
| `cli.config_cli` | 1 | 4 | 0.800 | 0.000 | 0.200 |
| `core.agentic_rag` | 1 | 4 | 0.800 | 0.000 | 0.200 |
| `core.indexer_graph` | 1 | 4 | 0.800 | 0.000 | 0.200 |
| `core.indexer_status` | 1 | 4 | 0.800 | 0.000 | 0.200 |
| `export.pdf_sync` | 1 | 4 | 0.800 | 0.000 | 0.200 |
| `handlers.resources` | 1 | 4 | 0.800 | 0.000 | 0.200 |
| `services.wiki_service` | 2 | 9 | 0.818 | 0.000 | 0.182 |
| `generators.wiki` | 11 | 29 | 0.725 | 0.100 | 0.175 |
| `cli.interactive_search` | 1 | 5 | 0.833 | 0.000 | 0.167 |
| `core.reranker` | 1 | 2 | 0.667 | 0.500 | 0.167 |
| `services.graph_expansion` | 1 | 5 | 0.833 | 0.000 | 0.167 |
| `web.routes_architecture` | 1 | 5 | 0.833 | 0.000 | 0.167 |
| `web.routes_codemap` | 1 | 5 | 0.833 | 0.000 | 0.167 |
| `web.routes_research` | 1 | 5 | 0.833 | 0.000 | 0.167 |
| `plugins.base` | 5 | 1 | 0.167 | 0.667 | 0.167 |
| `handlers.analysis_entity` | 2 | 11 | 0.846 | 0.000 | 0.154 |
| `handlers.codemap` | 2 | 11 | 0.846 | 0.000 | 0.154 |
| `core.parsing_pipeline` | 1 | 6 | 0.857 | 0.000 | 0.143 |
| `handlers.core` | 3 | 18 | 0.857 | 0.000 | 0.143 |
| `handlers.web_server` | 1 | 6 | 0.857 | 0.000 | 0.143 |
| `services.generator_service` | 2 | 12 | 0.857 | 0.000 | 0.143 |
| `handlers.analysis_metadata` | 2 | 14 | 0.875 | 0.000 | 0.125 |
| `handlers.research` | 2 | 14 | 0.875 | 0.000 | 0.125 |
| `models.foundation` | 5 | 3 | 0.375 | 0.750 | 0.125 |
| `handlers.analysis_search` | 1 | 9 | 0.900 | 0.000 | 0.100 |
| `generators.lazy_resources` | 1 | 10 | 0.909 | 0.000 | 0.091 |
| `handlers.agentic_workflows` | 1 | 12 | 0.923 | 0.000 | 0.077 |
| `handlers.analysis_diff` | 1 | 12 | 0.923 | 0.000 | 0.077 |
| `handlers.analysis_architecture` | 1 | 13 | 0.929 | 0.000 | 0.071 |
| `handlers.agentic` | 1 | 14 | 0.933 | 0.000 | 0.067 |
| `handlers` | 1 | 16 | 0.941 | 0.000 | 0.059 |
| `handlers.indexing` | 1 | 16 | 0.941 | 0.000 | 0.059 |
| `cli` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `cli.check_cli` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `cli.init_cli` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `cli.update_cli` | 0 | 9 | 1.000 | 0.000 | 0.000 |
| `core` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `core.protocols` | 1 | 0 | 0.000 | 1.000 | 0.000 |
| `generators` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `plugins` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `providers` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `server` | 0 | 7 | 1.000 | 0.000 | 0.000 |
| `services` | 0 | 8 | 1.000 | 0.000 | 0.000 |
| `watcher` | 0 | 6 | 1.000 | 0.000 | 0.000 |
| `web.app` | 0 | 7 | 1.000 | 0.000 | 0.000 |
| `wiki_output_helpers` | 0 | 1 | 1.000 | 0.000 | 0.000 |

## Far from Main Sequence

The following 48 module(s) have D > 0.7, indicating they may be either too concrete and stable (zone of pain) or too abstract and unstable (zone of uselessness):

- **`__init__`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.cache_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.main`** -- D=1.000 (I=0.000, A=0.000)
- **`cli_progress`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_embedding`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_llm`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_search`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_wiki`** -- D=1.000 (I=0.000, A=0.000)
- **`config.processing_models`** -- D=1.000 (I=0.000, A=0.000)
- **`config.prompts`** -- D=1.000 (I=0.000, A=0.000)
- **`core.query_utils`** -- D=1.000 (I=0.000, A=0.000)
- **`core.tracing`** -- D=1.000 (I=0.000, A=0.000)
- **`export.html_template`** -- D=1.000 (I=0.000, A=0.000)
- **`export.pdf_styles`** -- D=1.000 (I=0.000, A=0.000)
- **`fixtures.sample_repo`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.dir_tree`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.progress_tracker`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.toc`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers._response`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.agentic_data`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.session_state`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.types`** -- D=1.000 (I=0.000, A=0.000)
- **`logging`** -- D=1.000 (I=0.000, A=0.000)
- **`models.provider_types`** -- D=1.000 (I=0.000, A=0.000)
- **`models.research`** -- D=1.000 (I=0.000, A=0.000)
- **`providers.credentials`** -- D=1.000 (I=0.000, A=0.000)
- **`security.access_control`** -- D=1.000 (I=0.000, A=0.000)
- **`services.models`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs.annotations`** -- D=1.000 (I=0.000, A=0.000)
- **`web`** -- D=1.000 (I=0.000, A=0.000)
- **[`web.rate_limit`](files/src/local_deepwiki/web/rate_limit.md)** -- D=1.000 (I=0.000, A=0.000)
- **`errors`** -- D=0.967 (I=0.033, A=0.000)
- **`config`** -- D=0.943 (I=0.057, A=0.000)
- **`models`** -- D=0.891 (I=0.109, A=0.000)
- **`core.path_utils`** -- D=0.867 (I=0.133, A=0.000)
- **`models.chunks`** -- D=0.857 (I=0.143, A=0.000)
- **`core.rate_limiter`** -- D=0.833 (I=0.167, A=0.000)
- **`events`** -- D=0.833 (I=0.167, A=0.000)
- **`security`** -- D=0.824 (I=0.176, A=0.000)
- **`core.git_utils`** -- D=0.800 (I=0.200, A=0.000)
- **`core.health_history`** -- D=0.800 (I=0.200, A=0.000)
- **`core.index_manager`** -- D=0.800 (I=0.200, A=0.000)
- **`services.protocols`** -- D=0.800 (I=0.800, A=1.000)
- **`handlers._error_handling`** -- D=0.778 (I=0.222, A=0.000)
- **`core.vectorstore`** -- D=0.757 (I=0.207, A=0.036)
- **`generators.manifest`** -- D=0.750 (I=0.250, A=0.000)
- **`progress`** -- D=0.750 (I=0.250, A=0.000)
- **`validation`** -- D=0.750 (I=0.250, A=0.000)

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
