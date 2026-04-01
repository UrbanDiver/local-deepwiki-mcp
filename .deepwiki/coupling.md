# Coupling Metrics

Robert C. Martin's package coupling metrics measure the stability and abstractness of each module:

- **Ca** (afferent coupling): number of modules that depend on this module
- **Ce** (efferent coupling): number of modules this module depends on
- **I** (instability): Ce / (Ca + Ce) -- 0 = maximally stable, 1 = maximally unstable
- **A** (abstractness): fraction of abstract classes in the module
- **D** (distance from main sequence): |A + I - 1| -- 0 = on the main sequence, 1 = maximally far

## Summary

- **Total modules:** 407
- **Average distance from main sequence:** 0.399
- **Average instability:** 0.587
- **Average abstractness:** 0.017

## Metrics by Module

| Module | Ca | Ce | I | A | D |
|--------|----|----|---|---|---|
| `cli.cache_cli` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.check_cli` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.config_cli` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.config_validator` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.init_cli` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.interactive_search` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.main` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.profile_cli` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.search_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.status_cli` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli.update_cli` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `cli_progress` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `config` | 39 | 0 | 0.000 | 0.000 | 1.000 |
| `config.loader` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models` | 10 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_embedding` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_llm` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_search` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.models_wiki` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.processing_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.prompts` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `config.provider_models` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.agentic_rag` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.audit` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.chunk_builders` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.chunk_extractors` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `core.chunker` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `core.deep_research` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `core.fuzzy_search` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `core.git_blame` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `core.git_utils` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `core.graph_rag` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `core.health_history` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `core.index_manager` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `core.indexer_files` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.indexer_graph` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `core.indexer_status` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.llm_cache` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.parsing_pipeline` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.path_utils` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `core.query_utils` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `core.rate_limiter` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `core.secret_detector` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `core.tracing` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `error_factories` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `errors` | 12 | 0 | 0.000 | 0.000 | 1.000 |
| `events` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `export` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `export.html` | 8 | 0 | 0.000 | 0.000 | 1.000 |
| `export.html_template` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.mermaid_renderer` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf` | 9 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf_styles` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.pdf_sync` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `export.shared` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.analysis` | 36 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.changelog` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.codemap` | 15 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.context_builder` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.crosslinks` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.diagrams` | 8 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.dir_tree` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.examples` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.lazy_cache` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.lazy_generator` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.lazy_resources` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.llms_txt` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.manifest` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.manifest_parsers` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.prefetch` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.progress_tracker` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.search` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.see_also` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.source_refs` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `generators.toc` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers` | 21 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._error_handling` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._export_validation` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._index_helpers` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._progress` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers._response` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic_data` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.agentic_workflows` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_architecture` | 10 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_diff` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_entity` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_metadata` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.analysis_search` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.codemap` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.core` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.generators` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.indexing` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.prompts` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.research` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.resources` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.session_state` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.types` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `handlers.web_server` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `local_deepwiki.__init__` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `local_deepwiki.cli_progress` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `local_deepwiki.logging` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `logging` | 17 | 0 | 0.000 | 0.000 | 1.000 |
| `models` | 97 | 0 | 0.000 | 0.000 | 1.000 |
| `models.chunks` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `models.provider_types` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `models.research` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `models.tool_args` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `models.wiki` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `plugins` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `plugins.registry` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `progress` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `prompts` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `providers` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.credentials` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.embeddings` | 14 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.errors` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.llm` | 13 | 0 | 0.000 | 0.000 | 1.000 |
| `providers.retry` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `security` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `security.access_control` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `security.repository_access` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `security.role_config` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `server` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `services` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `services.analysis_service` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `services.generator_service` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `services.graph_expansion` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `services.indexing_service` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `services.models` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `services.provider_factory` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `services.query_service` | 7 | 0 | 0.000 | 0.000 | 1.000 |
| `services.wiki_service` | 3 | 0 | 0.000 | 0.000 | 1.000 |
| `tests.__init__` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `tests.fixtures` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `tests.test_cli_health_check` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `tests.test_github_action` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `tests.test_wiki_output_quality` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `tests.test_wiki_structural_integrity` | 0 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.analysis` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.annotations` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.core` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.generators` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `tool_defs.workflow` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `validation` | 6 | 0 | 0.000 | 0.000 | 1.000 |
| `watcher` | 4 | 0 | 0.000 | 0.000 | 1.000 |
| `web` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `web.app` | 5 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_architecture` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_chat` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_codemap` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `web.routes_research` | 1 | 0 | 0.000 | 0.000 | 1.000 |
| `web.utils` | 2 | 0 | 0.000 | 0.000 | 1.000 |
| `core.vectorstore` | 23 | 0 | 0.000 | 0.036 | 0.964 |
| `generators.wiki` | 26 | 0 | 0.000 | 0.100 | 0.900 |
| `export.streaming` | 6 | 0 | 0.000 | 0.167 | 0.833 |
| `core.parser` | 19 | 0 | 0.000 | 0.200 | 0.800 |
| `core.indexer` | 12 | 0 | 0.000 | 0.500 | 0.500 |
| `core.reranker` | 2 | 0 | 0.000 | 0.500 | 0.500 |
| `providers.base` | 30 | 0 | 0.000 | 0.500 | 0.500 |
| `plugins.base` | 5 | 0 | 0.000 | 0.667 | 0.333 |
| `models.foundation` | 4 | 0 | 0.000 | 0.750 | 0.250 |
| `tests.test_wiki_quality_improvements` | 0 | 3 | 1.000 | 0.167 | 0.167 |
| `tests.test_inheritance` | 0 | 2 | 1.000 | 0.143 | 0.143 |
| `tests.test_chunker` | 0 | 5 | 1.000 | 0.111 | 0.111 |
| `tests.test_export_init` | 0 | 1 | 1.000 | 0.111 | 0.111 |
| `tests.test_diagrams_class` | 0 | 2 | 1.000 | 0.105 | 0.105 |
| `core.protocols` | 2 | 0 | 0.000 | 1.000 | 0.000 |
| `generators.protocols` | 2 | 0 | 0.000 | 1.000 | 0.000 |
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
| `services.protocols` | 2 | 0 | 0.000 | 1.000 | 0.000 |
| `tests.conftest` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_access_control` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_agentic_rag` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_analysis_architecture` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_analyze_diff` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_anthropic_provider` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_api_docs` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_architecture_compare` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_architecture_composite` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_architecture_health` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_architecture_report` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_architecture_trends` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_ask_about_diff` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_audit` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_base_provider` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_callgraph` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_changelog` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_chat_code_refs` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_check_cli` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_cache` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_init` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_main` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_params` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_profiles` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_progress` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_status` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_cli_update` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_code_examples` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_cache` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_diagram_params` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_entry_points` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_graph` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_overview` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_suggestions` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_codemap_viz` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_collect_reverse_calls` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_complexity` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_complexity_metrics` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_config` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_config_cli` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_config_loader` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_context_builder` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_context_builder_warnings` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_coupling_metrics` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_coupling_page` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_coverage` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_credentials` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_crosslinks` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_deep_research_checkpoints` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_deep_research_pipeline` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_deep_research_progress` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_diagram` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_graph_basics` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_graph_circular` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_graph_core` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_graph_edge_cases` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_graph_imports` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_dependency_graph_rendering` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_design_smells` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_diagrams_dependency` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_diagrams_misc` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_embedding_cache` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_errors` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_events` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_examples_plugin` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_explain_entity` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_export_progress` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_export_shared` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_file_context_detail` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_fuzzy_search` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_git_utils` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_glossary` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_graph_rag_extractor` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_graph_rag_indexer_integration` | 0 | 6 | 1.000 | 0.000 | 0.000 |
| `tests.test_graph_rag_models` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_graph_rag_query_integration` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_graph_rag_retriever` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_graph_rag_store` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_handlers_agentic` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_handlers_index_qa` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_handlers_research_export` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_handlers_shared` | 0 | 9 | 1.000 | 0.000 | 0.000 |
| `tests.test_handlers_web_server` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_handlers_wiki_ops` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_health_history` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_health_page` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_health_scoring` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_hotspots` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_hotspots_page` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_html_export` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_hybrid_search` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_impact_analysis` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_incremental_wiki` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_index_manager` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_indexer_config` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_indexer_core` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_indexer_files` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_indexer_graph` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_indexing_service` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_integration_agentic` | 0 | 7 | 1.000 | 0.000 | 0.000 |
| `tests.test_integration_analysis` | 0 | 10 | 1.000 | 0.000 | 0.000 |
| `tests.test_integration_pipeline` | 0 | 8 | 1.000 | 0.000 | 0.000 |
| `tests.test_interactive_search_cli` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_interactive_search_core` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_interactive_search_models` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_interactive_search_ui` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_layer_analysis` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_lazy_generator` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_llm_cache` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_llm_providers` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_llms_txt` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_local_embedding_provider` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_logging_config` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_logging_coverage` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_manifest` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_models` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_module_dependencies` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_module_health` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_new_tools` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_ollama_health` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_onboarding` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_openai_embedding_provider` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_openai_embeddings` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_openai_provider` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_output_sizes` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_p1_fixes` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_parser_core` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_parser_docstrings` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_parser_node_utils` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_parser_performance` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_parsing_pipeline_params` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_pdf_generation` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_pdf_mermaid` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_pdf_rendering` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_pdf_streaming` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_plugin_registry` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_plugins` | 0 | 10 | 1.000 | 0.000 | 0.000 |
| `tests.test_prefetch` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_progress` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_progress_tracker` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_prompts` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_protocols` | 0 | 10 | 1.000 | 0.000 | 0.000 |
| `tests.test_provider_errors` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_provider_factories` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_providers` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_query_service` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_query_utils` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_rag_tracing` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_rate_limiter` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_recommendations` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_repository_access` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_reranker` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_resource_limits` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_resources` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_retry` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_retry_handler_params` | 0 | 7 | 1.000 | 0.000 | 0.000 |
| `tests.test_role_config` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_routes_architecture` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_search` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_search_decomposition` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_search_params` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_secret_detector` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_see_also` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_server` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_server_handlers` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_server_validation` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_services_params` | 0 | 9 | 1.000 | 0.000 | 0.000 |
| `tests.test_smells_page` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_source_filter` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_source_refs` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_stale_detection` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_streaming_export` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_structured_output` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_test_examples` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_toc` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_tools_v2` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_tour_handler` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_tours` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_type_annotations` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_batching` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_cache` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_core` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_indexes` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_lifecycle` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_pagination` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_search` | 0 | 5 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_submodules` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_vectorstore_utils` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_watcher_debounce` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_watcher_models` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_watcher_reindex` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_watcher_repository` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_web` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_web_codemap` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_web_onboarding` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_web_utils` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_codemaps` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_content_guards` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_context` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_file_callbacks` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_file_enrichment` | 0 | 4 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_file_generation` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_generation_warnings` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_generator` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_incremental` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_modules_coverage` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_pages_coverage` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_pages_gen` | 0 | 2 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_pipeline_params` | 0 | 1 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_service` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.test_wiki_status` | 0 | 3 | 1.000 | 0.000 | 0.000 |
| `tests.wiki_output_helpers` | 0 | 1 | 1.000 | 0.000 | 0.000 |

## Far from Main Sequence

The following 160 module(s) have D > 0.7, indicating they may be either too concrete and stable (zone of pain) or too abstract and unstable (zone of uselessness):

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
- **`tests.__init__`** -- D=1.000 (I=0.000, A=0.000)
- **`tests.fixtures`** -- D=1.000 (I=0.000, A=0.000)
- **`tests.test_cli_health_check`** -- D=1.000 (I=0.000, A=0.000)
- **`tests.test_github_action`** -- D=1.000 (I=0.000, A=0.000)
- **`tests.test_wiki_output_quality`** -- D=1.000 (I=0.000, A=0.000)
- **`tests.test_wiki_structural_integrity`** -- D=1.000 (I=0.000, A=0.000)
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

- [`src/local_deepwiki/core/git_utils.py:28-31`](files/src/local_deepwiki/core/git_utils.md)
- [`src/local_deepwiki/core/chunker.py:50-63`](files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/server.py:92-94`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/core/vectorstore/embedding.py:20-30`](files/src/local_deepwiki/core/vectorstore/embedding.md)
- [`src/local_deepwiki/core/graph_rag/store.py:44-411`](files/src/local_deepwiki/core/graph_rag/store.md)
- [`src/local_deepwiki/config/provider_models.py:10-20`](files/src/local_deepwiki/config/provider_models.md)
- [`src/local_deepwiki/core/indexer.py:233-263`](files/src/local_deepwiki/core/indexer.md)
- `src/local_deepwiki/providers/llm/__init__.py:16-19`
- [`src/local_deepwiki/cli/init_cli.py:30-43`](files/src/local_deepwiki/cli/init_cli.md)
- [`src/local_deepwiki/web/app.py:87-96`](files/src/local_deepwiki/web/app.md)


*Showing 10 of 263 source files.*
