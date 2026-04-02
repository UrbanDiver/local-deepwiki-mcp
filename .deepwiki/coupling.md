# Coupling Metrics

Robert C. Martin's package coupling metrics measure the stability and abstractness of each module:

- **Ca** (afferent coupling): number of modules that depend on this module
- **Ce** (efferent coupling): number of modules this module depends on
- **I** (instability): Ce / (Ca + Ce) -- 0 = maximally stable, 1 = maximally unstable
- **A** (abstractness): fraction of abstract classes in the module
- **D** (distance from main sequence): |A + I - 1| -- 0 = on the main sequence, 1 = maximally far

## Summary

- **Total modules:** 183
- **Average distance from main sequence:** 0.850
- **Average instability:** 0.115
- **Average abstractness:** 0.035

## Metrics by Module

| Module | Ca | Ce | I | A | D |
|--------|----|----|---|---|---|
| `cli.cache_cli` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.check_cli` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.config_cli` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.config_validator` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.init_cli` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.interactive_search` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.main` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.profile_cli` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.search_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.status_cli` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.update_cli` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `cli_progress` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `config` | 10 | 0 | 0.000 | 0.000 | 1.000 |
| `config.loader` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_embedding` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_llm` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_search` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_wiki` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.processing_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.prompts` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.provider_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `core.agentic_rag` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.audit` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.chunk_builders` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.chunk_extractors` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.chunker` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.deep_research` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.fuzzy_search` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.git_blame` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.git_utils` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.graph_rag` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.health_history` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `core.index_manager` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `core.indexer_files` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.indexer_graph` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.indexer_status` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.llm_cache` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.parsing_pipeline` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.path_utils` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `core.query_utils` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.rate_limiter` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `core.secret_detector` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.tracing` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `error_factories` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `errors` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `events` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `export` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.html` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `export.html_template` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.mermaid_renderer` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf_styles` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf_sync` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.shared` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.analysis` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.changelog` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.codemap` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.context_builder` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.crosslinks` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.diagrams` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.dir_tree` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.examples` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.lazy_cache` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.lazy_generator` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.lazy_resources` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.llms_txt` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.manifest` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.manifest_parsers` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.prefetch` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.progress_tracker` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.search` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.see_also` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.source_refs` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.toc` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._error_handling` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._export_validation` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._index_helpers` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._progress` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._response` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic_data` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic_workflows` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_architecture` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_diff` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_entity` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_metadata` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_search` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.codemap` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.core` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.generators` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.indexing` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.prompts` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.research` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.resources` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.session_state` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.types` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.web_server` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `local_deepwiki.__init__` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `local_deepwiki.cli_progress` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `local_deepwiki.logging` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `logging` | 15 | 0 | 0.000 | 0.000 | 1.000 |
| `models` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `models.chunks` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `models.provider_types` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `models.research` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `models.tool_args` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `models.wiki` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `plugins` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `plugins.registry` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `progress` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `prompts` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `providers` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.credentials` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.embeddings` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.errors` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.llm` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.retry` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `security` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `security.access_control` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `security.repository_access` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `security.role_config` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `server` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `services` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `services.analysis_service` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `services.generator_service` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `services.graph_expansion` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `services.indexing_service` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `services.models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `services.provider_factory` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `services.query_service` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `services.wiki_service` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.analysis` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.annotations` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.core` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.generators` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.workflow` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `validation` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `watcher` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `web` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.app` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_architecture` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_chat` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_codemap` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_research` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.utils` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.vectorstore` | 6 | 0 | 0.000 | 0.036 | 0.964 |
| `generators.wiki` | 5 | 0 | 0.000 | 0.100 | 0.900 |
| `export.streaming` | 3 | 0 | 0.000 | 0.167 | 0.833 |
| `core.parser` | 6 | 0 | 0.000 | 0.200 | 0.800 |
| `core.indexer` | 4 | 0 | 0.000 | 0.500 | 0.500 |
| `core.reranker` | 1 | 0 | 0.000 | 0.500 | 0.500 |
| `providers.base` | 5 | 0 | 0.000 | 0.500 | 0.500 |
| `plugins.base` | 3 | 0 | 0.000 | 0.667 | 0.333 |
| `models.foundation` | 3 | 0 | 0.000 | 0.750 | 0.250 |
| `core.protocols` | 1 | 0 | 0.000 | 1.000 | 0.000 |
| `generators.protocols` | 1 | 0 | 0.000 | 1.000 | 0.000 |
| `local_deepwiki.cli` | 0 | 24 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.config` | 0 | 10 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.core` | 0 | 30 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.error_factories` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.errors` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.events` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.export` | 0 | 10 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.generators` | 0 | 41 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.handlers` | 0 | 59 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.models` | 0 | 6 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.plugins` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.progress` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.prompts` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.providers` | 0 | 12 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.security` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.server` | 0 | 7 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.services` | 0 | 45 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.tool_defs` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.validation` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.watcher` | 0 | 6 | 1.000 | 0.000 | 0.000 |
| `local_deepwiki.web` | 0 | 20 | 1.000 | 0.000 | 0.000 |
| `services.protocols` | 1 | 0 | 0.000 | 1.000 | 0.000 |

## Far from Main Sequence

The following 154 module(s) have D > 0.7, indicating they may be either too concrete and stable (zone of pain) or too abstract and unstable (zone of uselessness):

- **`cli.cache_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.check_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.config_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.config_validator`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.init_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.interactive_search`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.main`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.profile_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.search_models`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.status_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli.update_cli`** -- D=1.000 (I=0.000, A=0.000)
- **`cli_progress`** -- D=1.000 (I=0.000, A=0.000)
- **`config`** -- D=1.000 (I=0.000, A=0.000)
- **`config.loader`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_embedding`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_llm`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_search`** -- D=1.000 (I=0.000, A=0.000)
- **`config.models_wiki`** -- D=1.000 (I=0.000, A=0.000)
- **`config.processing_models`** -- D=1.000 (I=0.000, A=0.000)
- **`config.prompts`** -- D=1.000 (I=0.000, A=0.000)
- **`config.provider_models`** -- D=1.000 (I=0.000, A=0.000)
- **`core`** -- D=1.000 (I=0.000, A=0.000)
- **`core.agentic_rag`** -- D=1.000 (I=0.000, A=0.000)
- **`core.audit`** -- D=1.000 (I=0.000, A=0.000)
- **`core.chunk_builders`** -- D=1.000 (I=0.000, A=0.000)
- **`core.chunk_extractors`** -- D=1.000 (I=0.000, A=0.000)
- **`core.chunker`** -- D=1.000 (I=0.000, A=0.000)
- **`core.deep_research`** -- D=1.000 (I=0.000, A=0.000)
- **`core.fuzzy_search`** -- D=1.000 (I=0.000, A=0.000)
- **`core.git_blame`** -- D=1.000 (I=0.000, A=0.000)
- **`core.git_utils`** -- D=1.000 (I=0.000, A=0.000)
- **`core.graph_rag`** -- D=1.000 (I=0.000, A=0.000)
- **`core.health_history`** -- D=1.000 (I=0.000, A=0.000)
- **`core.index_manager`** -- D=1.000 (I=0.000, A=0.000)
- **`core.indexer_files`** -- D=1.000 (I=0.000, A=0.000)
- **`core.indexer_graph`** -- D=1.000 (I=0.000, A=0.000)
- **`core.indexer_status`** -- D=1.000 (I=0.000, A=0.000)
- **`core.llm_cache`** -- D=1.000 (I=0.000, A=0.000)
- **`core.parsing_pipeline`** -- D=1.000 (I=0.000, A=0.000)
- **`core.path_utils`** -- D=1.000 (I=0.000, A=0.000)
- **`core.query_utils`** -- D=1.000 (I=0.000, A=0.000)
- **`core.rate_limiter`** -- D=1.000 (I=0.000, A=0.000)
- **`core.secret_detector`** -- D=1.000 (I=0.000, A=0.000)
- **`core.tracing`** -- D=1.000 (I=0.000, A=0.000)
- **`error_factories`** -- D=1.000 (I=0.000, A=0.000)
- **`errors`** -- D=1.000 (I=0.000, A=0.000)
- **`events`** -- D=1.000 (I=0.000, A=0.000)
- **`export`** -- D=1.000 (I=0.000, A=0.000)
- **`export.html`** -- D=1.000 (I=0.000, A=0.000)
- **`export.html_template`** -- D=1.000 (I=0.000, A=0.000)
- **`export.mermaid_renderer`** -- D=1.000 (I=0.000, A=0.000)
- **`export.pdf`** -- D=1.000 (I=0.000, A=0.000)
- **`export.pdf_styles`** -- D=1.000 (I=0.000, A=0.000)
- **`export.pdf_sync`** -- D=1.000 (I=0.000, A=0.000)
- **`export.shared`** -- D=1.000 (I=0.000, A=0.000)
- **`generators`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.analysis`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.changelog`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.codemap`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.context_builder`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.crosslinks`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.diagrams`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.dir_tree`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.examples`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.lazy_cache`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.lazy_generator`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.lazy_resources`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.llms_txt`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.manifest`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.manifest_parsers`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.prefetch`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.progress_tracker`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.search`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.see_also`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.source_refs`** -- D=1.000 (I=0.000, A=0.000)
- **`generators.toc`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers._error_handling`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers._export_validation`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers._index_helpers`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers._progress`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers._response`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.agentic`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.agentic_data`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.agentic_workflows`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.analysis_architecture`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.analysis_diff`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.analysis_entity`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.analysis_metadata`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.analysis_search`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.codemap`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.core`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.generators`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.indexing`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.prompts`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.research`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.resources`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.session_state`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.types`** -- D=1.000 (I=0.000, A=0.000)
- **`handlers.web_server`** -- D=1.000 (I=0.000, A=0.000)
- **`local_deepwiki.__init__`** -- D=1.000 (I=0.000, A=0.000)
- **`local_deepwiki.cli_progress`** -- D=1.000 (I=0.000, A=0.000)
- **`local_deepwiki.logging`** -- D=1.000 (I=0.000, A=0.000)
- **`logging`** -- D=1.000 (I=0.000, A=0.000)
- **`models`** -- D=1.000 (I=0.000, A=0.000)
- **`models.chunks`** -- D=1.000 (I=0.000, A=0.000)
- **`models.provider_types`** -- D=1.000 (I=0.000, A=0.000)
- **`models.research`** -- D=1.000 (I=0.000, A=0.000)
- **`models.tool_args`** -- D=1.000 (I=0.000, A=0.000)
- **`models.wiki`** -- D=1.000 (I=0.000, A=0.000)
- **`plugins`** -- D=1.000 (I=0.000, A=0.000)
- **`plugins.registry`** -- D=1.000 (I=0.000, A=0.000)
- **`progress`** -- D=1.000 (I=0.000, A=0.000)
- **`prompts`** -- D=1.000 (I=0.000, A=0.000)
- **`providers`** -- D=1.000 (I=0.000, A=0.000)
- **`providers.credentials`** -- D=1.000 (I=0.000, A=0.000)
- **`providers.embeddings`** -- D=1.000 (I=0.000, A=0.000)
- **`providers.errors`** -- D=1.000 (I=0.000, A=0.000)
- **`providers.llm`** -- D=1.000 (I=0.000, A=0.000)
- **`providers.retry`** -- D=1.000 (I=0.000, A=0.000)
- **`security`** -- D=1.000 (I=0.000, A=0.000)
- **`security.access_control`** -- D=1.000 (I=0.000, A=0.000)
- **`security.repository_access`** -- D=1.000 (I=0.000, A=0.000)
- **`security.role_config`** -- D=1.000 (I=0.000, A=0.000)
- **`server`** -- D=1.000 (I=0.000, A=0.000)
- **`services`** -- D=1.000 (I=0.000, A=0.000)
- **`services.analysis_service`** -- D=1.000 (I=0.000, A=0.000)
- **`services.generator_service`** -- D=1.000 (I=0.000, A=0.000)
- **`services.graph_expansion`** -- D=1.000 (I=0.000, A=0.000)
- **`services.indexing_service`** -- D=1.000 (I=0.000, A=0.000)
- **`services.models`** -- D=1.000 (I=0.000, A=0.000)
- **`services.provider_factory`** -- D=1.000 (I=0.000, A=0.000)
- **`services.query_service`** -- D=1.000 (I=0.000, A=0.000)
- **`services.wiki_service`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs.analysis`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs.annotations`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs.core`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs.generators`** -- D=1.000 (I=0.000, A=0.000)
- **`tool_defs.workflow`** -- D=1.000 (I=0.000, A=0.000)
- **`validation`** -- D=1.000 (I=0.000, A=0.000)
- **`watcher`** -- D=1.000 (I=0.000, A=0.000)
- **`web`** -- D=1.000 (I=0.000, A=0.000)
- **`web.app`** -- D=1.000 (I=0.000, A=0.000)
- **`web.routes_architecture`** -- D=1.000 (I=0.000, A=0.000)
- **`web.routes_chat`** -- D=1.000 (I=0.000, A=0.000)
- **`web.routes_codemap`** -- D=1.000 (I=0.000, A=0.000)
- **`web.routes_research`** -- D=1.000 (I=0.000, A=0.000)
- **`web.utils`** -- D=1.000 (I=0.000, A=0.000)
- **`core.vectorstore`** -- D=0.964 (I=0.000, A=0.036)
- **`generators.wiki`** -- D=0.900 (I=0.000, A=0.100)
- **`export.streaming`** -- D=0.833 (I=0.000, A=0.167)
- **`core.parser`** -- D=0.800 (I=0.000, A=0.200)

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/tool_defs/analysis.py`](files/src/local_deepwiki/tool_defs/analysis.md)
- [`src/local_deepwiki/generators/analysis/coupling.py:48-90`](files/src/local_deepwiki/generators/analysis/coupling.md)
- [`src/local_deepwiki/handlers/analysis_architecture.py:43-94`](files/src/local_deepwiki/handlers/analysis_architecture.md)
- [`src/local_deepwiki/models/tool_args.py:15-49`](files/src/local_deepwiki/models/tool_args.md)
- [`src/local_deepwiki/generators/analysis/design_smells.py:162-163`](files/src/local_deepwiki/generators/analysis/design_smells.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:92-94`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`


*Showing 10 of 263 source files.*
