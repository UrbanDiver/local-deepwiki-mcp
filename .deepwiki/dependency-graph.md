# Dependency Graph

This page shows the module dependencies within the codebase.

## Module Dependencies

The following diagram shows how modules depend on each other. Click on a module to view its documentation.

```mermaid
flowchart TD
    subgraph local_deepwiki[Local Deepwiki]
        M0[__init__]
        M1[__init__]
        M2[cache_cli]
        M3[check_cli]
        M4[config_cli]
        M5[config_validator]
        M6[init_cli]
        M7[interactive_search]
        M8[main]
        M9[profile_cli]
        M10[search_models]
        M11[status_cli]
        M12[update_cli]
        M13[cli_progress]
        M14[__init__]
        M15[loader]
        M16[models]
        M17[models_embedding]
        M18[models_llm]
        M19[models_search]
        M20[models_wiki]
        M21[processing_models]
        M22[prompts]
        M23[provider_models]
        M24[__init__]
        M25[agentic_rag]
        M26[audit]
        M27[chunk_builders]
        M28[chunk_extractors]
        M29[chunker]
        M30[__init__]
        M31[checkpoints]
        M32[config]
        M33[pipeline]
        M34[reasoning]
        M35[serialization]
        M36[steps]
        M37[fuzzy_search]
        M38[git_blame]
        M39[git_utils]
        M40[__init__]
        M41[extractor]
        M42[models]
        M43[retriever]
        M44[store]
        M45[health_history]
        M46[index_manager]
        M47[indexer]
        M48[indexer_files]
        M49[indexer_graph]
        M50[indexer_status]
        M51[llm_cache]
        M52[__init__]
        M53[ast_cache]
        M54[ast_utils]
        M55[code_parser]
        M56[docstrings]
        M57[languages]
        M58[parsing_pipeline]
        M59[path_utils]
        M60[protocols]
        M61[query_utils]
        M62[rate_limiter]
        M63[reranker]
        M64[secret_detector]
        M65[tracing]
        M66[__init__]
        M67[cache]
        M68[embedding]
        M69[indexes]
        M70[iterators]
        M71[maintenance]
        M72[__init__]
        M73[lazy_index]
        M74[search]
        M75[search_types]
        M76[stats]
        M77[schema]
        M78[search_config_resolver]
        M79[search_engine]
        M80[search_params]
        M81[search_pipeline]
        M82[search_postprocess]
        M83[store]
        M84[utils]
        M85[error_factories]
        M86[errors]
        M87[events]
        M88[__init__]
        M89[html]
        M90[html_template]
        M91[mermaid_renderer]
        M92[pdf]
        M93[pdf_styles]
        M94[pdf_sync]
        M95[shared]
        M96[streaming]
        M97[toc_renderer]
        M98[__init__]
        M99[__init__]
        M100[api_docs]
        M101[architecture_compare]
        M102[architecture_composite]
        M103[architecture_health]
        M104[architecture_report]
        M105[callgraph]
        M106[churn]
        M107[cohesion]
        M108[complexity]
        M109[coupling]
        M110[coupling_page]
        M111[coverage]
        M112[dependency_graph]
        M113[dependency_graph_data]
        M114[design_smells]
        M115[duplication]
        M116[glossary]
        M117[health_page]
        M118[health_scoring]
        M119[hotspots]
        M120[hotspots_page]
        M121[inheritance]
        M122[layer_analysis]
        M123[maintainability]
        M124[module_dependencies]
        M125[module_health]
        M126[onboarding]
        M127[recommendations]
        M128[smells_page]
        M129[source_filter]
        M130[stale_detection]
        M131[testability]
        M132[tours]
        M133[changelog]
        M134[__init__]
        M135[cache]
        M136[generator]
        M137[graph]
        M138[models]
        M139[overview]
        M140[params]
        M141[viz]
        M142[context_builder]
        M143[crosslinks]
        M144[__init__]
        M145[_utils]
        M146[class_diagram]
        M147[dependency_diagram]
        M148[language_pie]
        M149[module_diagram]
        M150[sequence_diagram]
        M151[dir_tree]
        M152[__init__]
        M153[discovery]
        M154[docstring]
        M155[extractor]
        M156[orchestrator]
        M157[plugin]
        M158[lazy_cache]
        M159[lazy_generator]
        M160[lazy_resources]
        M161[llms_txt]
        M162[manifest]
        M163[manifest_parsers]
        M164[prefetch]
        M165[progress_tracker]
        M166[protocols]
        M167[search]
        M168[see_also]
        M169[source_refs]
        M170[toc]
        M171[__init__]
        M172[codemap_pages]
        M173[context]
        M174[files]
        M175[generator]
        M176[modules]
        M177[pages]
        M178[phases]
        M179[pipeline]
        M180[pipeline_params]
        M181[plugin_runner]
        M182[postprocessing]
        M183[source_formatter]
        M184[status]
        M185[term_validator]
        M186[utils]
        M187[__init__]
        M188[_error_handling]
        M189[_export_validation]
        M190[_index_helpers]
        M191[_progress]
        M192[_response]
        M193[agentic]
        M194[agentic_data]
        M195[agentic_workflows]
        M196[analysis_architecture]
        M197[analysis_diff]
        M198[analysis_entity]
        M199[analysis_metadata]
        M200[analysis_search]
        M201[codemap]
        M202[core]
        M203[generators]
        M204[indexing]
        M205[prompts]
        M206[research]
        M207[resources]
        M208[session_state]
        M209[types]
        M210[web_server]
        M211[logging]
        M212[__init__]
        M213[chunks]
        M214[foundation]
        M215[provider_types]
        M216[research]
        M217[tool_args]
        M218[wiki]
        M219[__init__]
        M220[base]
        M221[registry]
        M222[progress]
        M223[prompts]
        M224[__init__]
        M225[base]
        M226[credentials]
        M227[__init__]
        M228[cache]
        M229[local]
        M230[openai]
        M231[errors]
        M232[__init__]
        M233[anthropic]
        M234[cached]
        M235[ollama]
        M236[openai]
        M237[retry]
        M238[__init__]
        M239[access_control]
        M240[repository_access]
        M241[role_config]
        M242[server]
        M243[__init__]
        M244[analysis_service]
        M245[generator_service]
        M246[graph_expansion]
        M247[indexing_service]
        M248[models]
        M249[protocols]
        M250[provider_factory]
        M251[query_service]
        M252[wiki_service]
        M253[__init__]
        M254[analysis]
        M255[annotations]
        M256[core]
        M257[generators]
        M258[workflow]
        M259[validation]
        M260[watcher]
        M261[__init__]
        M262[app]
        M263[rate_limit]
        M264[routes_architecture]
        M265[routes_chat]
        M266[routes_codemap]
        M267[routes_research]
        M268[utils]
    end
    subgraph external[External Dependencies]
        E269([argparse]):::external
        E270([asyncio]):::external
        E271([collections]):::external
        E272([contextlib]):::external
        E273([contextvars]):::external
        E274([dataclasses]):::external
        E275([enum]):::external
        E276([functools]):::external
        E277([importlib]):::external
        E278([json]):::external
    end
    M0 -.-> E277
    M6 -.-> E269
    M6 -.-> E271
    M6 -.-> E274
    M6 --> M16
    M6 --> M32
    M8 -.-> E277
    M15 -.-> E272
    M15 -.-> E273
    M15 -.-> E274
    M15 --> M42
    M15 --> M215
    M75 -.-> E274
    M75 --> M77
    M102 --> M103
    M102 --> M104
    M102 --> M124
    M102 --> M127
    M128 -.-> E271
    M129 --> M57
    M139 -.-> E271
    M139 -.-> E274
    M139 -.-> E278
    M139 --> M59
    M139 --> M211
    M186 --> M59
    M215 -.-> E275
    M239 -.-> E270
    M239 -.-> E271
    M239 -.-> E273
    M239 -.-> E274
    M239 -.-> E275
    M239 -.-> E276
    click M0 "files/files/src/local_deepwiki/__init__.md"
    click M1 "files/files/src/local_deepwiki/cli/__init__.md"
    click M2 "files/files/src/local_deepwiki/cli/cache_cli.md"
    click M3 "files/files/src/local_deepwiki/cli/check_cli.md"
    click M4 "files/files/src/local_deepwiki/cli/config_cli.md"
    click M5 "files/files/src/local_deepwiki/cli/config_validator.md"
    click M6 "files/files/src/local_deepwiki/cli/init_cli.md"
    click M7 "files/files/src/local_deepwiki/cli/interactive_search.md"
    click M8 "files/files/src/local_deepwiki/cli/main.md"
    click M9 "files/files/src/local_deepwiki/cli/profile_cli.md"
    click M10 "files/files/src/local_deepwiki/cli/search_models.md"
    click M11 "files/files/src/local_deepwiki/cli/status_cli.md"
    click M12 "files/files/src/local_deepwiki/cli/update_cli.md"
    click M13 "files/files/src/local_deepwiki/cli_progress.md"
    click M14 "files/files/src/local_deepwiki/config/__init__.md"
    click M15 "files/files/src/local_deepwiki/config/loader.md"
    click M16 "files/files/src/local_deepwiki/config/models.md"
    click M17 "files/files/src/local_deepwiki/config/models_embedding.md"
    click M18 "files/files/src/local_deepwiki/config/models_llm.md"
    click M19 "files/files/src/local_deepwiki/config/models_search.md"
    click M20 "files/files/src/local_deepwiki/config/models_wiki.md"
    click M21 "files/files/src/local_deepwiki/config/processing_models.md"
    click M22 "files/files/src/local_deepwiki/config/prompts.md"
    click M23 "files/files/src/local_deepwiki/config/provider_models.md"
    click M24 "files/files/src/local_deepwiki/core/__init__.md"
    click M25 "files/files/src/local_deepwiki/core/agentic_rag.md"
    click M26 "files/files/src/local_deepwiki/core/audit.md"
    click M27 "files/files/src/local_deepwiki/core/chunk_builders.md"
    click M28 "files/files/src/local_deepwiki/core/chunk_extractors.md"
    click M29 "files/files/src/local_deepwiki/core/chunker.md"
    click M30 "files/files/src/local_deepwiki/core/deep_research/__init__.md"
    click M31 "files/files/src/local_deepwiki/core/deep_research/checkpoints.md"
    click M32 "files/files/src/local_deepwiki/core/deep_research/config.md"
    click M33 "files/files/src/local_deepwiki/core/deep_research/pipeline.md"
    click M34 "files/files/src/local_deepwiki/core/deep_research/reasoning.md"
    click M35 "files/files/src/local_deepwiki/core/deep_research/serialization.md"
    click M36 "files/files/src/local_deepwiki/core/deep_research/steps.md"
    click M37 "files/files/src/local_deepwiki/core/fuzzy_search.md"
    click M38 "files/files/src/local_deepwiki/core/git_blame.md"
    click M39 "files/files/src/local_deepwiki/core/git_utils.md"
    click M40 "files/files/src/local_deepwiki/core/graph_rag/__init__.md"
    click M41 "files/files/src/local_deepwiki/core/graph_rag/extractor.md"
    click M42 "files/files/src/local_deepwiki/core/graph_rag/models.md"
    click M43 "files/files/src/local_deepwiki/core/graph_rag/retriever.md"
    click M44 "files/files/src/local_deepwiki/core/graph_rag/store.md"
    click M45 "files/files/src/local_deepwiki/core/health_history.md"
    click M46 "files/files/src/local_deepwiki/core/index_manager.md"
    click M47 "files/files/src/local_deepwiki/core/indexer.md"
    click M48 "files/files/src/local_deepwiki/core/indexer_files.md"
    click M49 "files/files/src/local_deepwiki/core/indexer_graph.md"
    click M50 "files/files/src/local_deepwiki/core/indexer_status.md"
    click M51 "files/files/src/local_deepwiki/core/llm_cache.md"
    click M52 "files/files/src/local_deepwiki/core/parser/__init__.md"
    click M53 "files/files/src/local_deepwiki/core/parser/ast_cache.md"
    click M54 "files/files/src/local_deepwiki/core/parser/ast_utils.md"
    click M55 "files/files/src/local_deepwiki/core/parser/code_parser.md"
    click M56 "files/files/src/local_deepwiki/core/parser/docstrings.md"
    click M57 "files/files/src/local_deepwiki/core/parser/languages.md"
    click M58 "files/files/src/local_deepwiki/core/parsing_pipeline.md"
    click M59 "files/files/src/local_deepwiki/core/path_utils.md"
    click M60 "files/files/src/local_deepwiki/core/protocols.md"
    click M61 "files/files/src/local_deepwiki/core/query_utils.md"
    click M62 "files/files/src/local_deepwiki/core/rate_limiter.md"
    click M63 "files/files/src/local_deepwiki/core/reranker.md"
    click M64 "files/files/src/local_deepwiki/core/secret_detector.md"
    click M65 "files/files/src/local_deepwiki/core/tracing.md"
    click M66 "files/files/src/local_deepwiki/core/vectorstore/__init__.md"
    click M67 "files/files/src/local_deepwiki/core/vectorstore/cache.md"
    click M68 "files/files/src/local_deepwiki/core/vectorstore/embedding.md"
    click M69 "files/files/src/local_deepwiki/core/vectorstore/indexes.md"
    click M70 "files/files/src/local_deepwiki/core/vectorstore/iterators.md"
    click M71 "files/files/src/local_deepwiki/core/vectorstore/maintenance.md"
    click M72 "files/files/src/local_deepwiki/core/vectorstore/mixins/__init__.md"
    click M73 "files/files/src/local_deepwiki/core/vectorstore/mixins/lazy_index.md"
    click M74 "files/files/src/local_deepwiki/core/vectorstore/mixins/search.md"
    click M75 "files/files/src/local_deepwiki/core/vectorstore/mixins/search_types.md"
    click M76 "files/files/src/local_deepwiki/core/vectorstore/mixins/stats.md"
    click M77 "files/files/src/local_deepwiki/core/vectorstore/schema.md"
    click M78 "files/files/src/local_deepwiki/core/vectorstore/search_config_resolver.md"
    click M79 "files/files/src/local_deepwiki/core/vectorstore/search_engine.md"
    click M80 "files/files/src/local_deepwiki/core/vectorstore/search_params.md"
    click M81 "files/files/src/local_deepwiki/core/vectorstore/search_pipeline.md"
    click M82 "files/files/src/local_deepwiki/core/vectorstore/search_postprocess.md"
    click M83 "files/files/src/local_deepwiki/core/vectorstore/store.md"
    click M84 "files/files/src/local_deepwiki/core/vectorstore/utils.md"
    click M85 "files/files/src/local_deepwiki/error_factories.md"
    click M86 "files/files/src/local_deepwiki/errors.md"
    click M87 "files/files/src/local_deepwiki/events.md"
    click M88 "files/files/src/local_deepwiki/export/__init__.md"
    click M89 "files/files/src/local_deepwiki/export/html.md"
    click M90 "files/files/src/local_deepwiki/export/html_template.md"
    click M91 "files/files/src/local_deepwiki/export/mermaid_renderer.md"
    click M92 "files/files/src/local_deepwiki/export/pdf.md"
    click M93 "files/files/src/local_deepwiki/export/pdf_styles.md"
    click M94 "files/files/src/local_deepwiki/export/pdf_sync.md"
    click M95 "files/files/src/local_deepwiki/export/shared.md"
    click M96 "files/files/src/local_deepwiki/export/streaming.md"
    click M97 "files/files/src/local_deepwiki/export/toc_renderer.md"
    click M98 "files/files/src/local_deepwiki/generators/__init__.md"
    click M99 "files/files/src/local_deepwiki/generators/analysis/__init__.md"
    click M100 "files/files/src/local_deepwiki/generators/analysis/api_docs.md"
    click M101 "files/files/src/local_deepwiki/generators/analysis/architecture_compare.md"
    click M102 "files/files/src/local_deepwiki/generators/analysis/architecture_composite.md"
    click M103 "files/files/src/local_deepwiki/generators/analysis/architecture_health.md"
    click M104 "files/files/src/local_deepwiki/generators/analysis/architecture_report.md"
    click M105 "files/files/src/local_deepwiki/generators/analysis/callgraph.md"
    click M106 "files/files/src/local_deepwiki/generators/analysis/churn.md"
    click M107 "files/files/src/local_deepwiki/generators/analysis/cohesion.md"
    click M108 "files/files/src/local_deepwiki/generators/analysis/complexity.md"
    click M109 "files/files/src/local_deepwiki/generators/analysis/coupling.md"
    click M110 "files/files/src/local_deepwiki/generators/analysis/coupling_page.md"
    click M111 "files/files/src/local_deepwiki/generators/analysis/coverage.md"
    click M112 "files/files/src/local_deepwiki/generators/analysis/dependency_graph.md"
    click M113 "files/files/src/local_deepwiki/generators/analysis/dependency_graph_data.md"
    click M114 "files/files/src/local_deepwiki/generators/analysis/design_smells.md"
    click M115 "files/files/src/local_deepwiki/generators/analysis/duplication.md"
    click M116 "files/files/src/local_deepwiki/generators/analysis/glossary.md"
    click M117 "files/files/src/local_deepwiki/generators/analysis/health_page.md"
    click M118 "files/files/src/local_deepwiki/generators/analysis/health_scoring.md"
    click M119 "files/files/src/local_deepwiki/generators/analysis/hotspots.md"
    click M120 "files/files/src/local_deepwiki/generators/analysis/hotspots_page.md"
    click M121 "files/files/src/local_deepwiki/generators/analysis/inheritance.md"
    click M122 "files/files/src/local_deepwiki/generators/analysis/layer_analysis.md"
    click M123 "files/files/src/local_deepwiki/generators/analysis/maintainability.md"
    click M124 "files/files/src/local_deepwiki/generators/analysis/module_dependencies.md"
    click M125 "files/files/src/local_deepwiki/generators/analysis/module_health.md"
    click M126 "files/files/src/local_deepwiki/generators/analysis/onboarding.md"
    click M127 "files/files/src/local_deepwiki/generators/analysis/recommendations.md"
    click M128 "files/files/src/local_deepwiki/generators/analysis/smells_page.md"
    click M129 "files/files/src/local_deepwiki/generators/analysis/source_filter.md"
    click M130 "files/files/src/local_deepwiki/generators/analysis/stale_detection.md"
    click M131 "files/files/src/local_deepwiki/generators/analysis/testability.md"
    click M132 "files/files/src/local_deepwiki/generators/analysis/tours.md"
    click M133 "files/files/src/local_deepwiki/generators/changelog.md"
    click M134 "files/files/src/local_deepwiki/generators/codemap/__init__.md"
    click M135 "files/files/src/local_deepwiki/generators/codemap/cache.md"
    click M136 "files/files/src/local_deepwiki/generators/codemap/generator.md"
    click M137 "files/files/src/local_deepwiki/generators/codemap/graph.md"
    click M138 "files/files/src/local_deepwiki/generators/codemap/models.md"
    click M139 "files/files/src/local_deepwiki/generators/codemap/overview.md"
    click M140 "files/files/src/local_deepwiki/generators/codemap/params.md"
    click M141 "files/files/src/local_deepwiki/generators/codemap/viz.md"
    click M142 "files/files/src/local_deepwiki/generators/context_builder.md"
    click M143 "files/files/src/local_deepwiki/generators/crosslinks.md"
    click M144 "files/files/src/local_deepwiki/generators/diagrams/__init__.md"
    click M145 "files/files/src/local_deepwiki/generators/diagrams/_utils.md"
    click M146 "files/files/src/local_deepwiki/generators/diagrams/class_diagram.md"
    click M147 "files/files/src/local_deepwiki/generators/diagrams/dependency_diagram.md"
    click M148 "files/files/src/local_deepwiki/generators/diagrams/language_pie.md"
    click M149 "files/files/src/local_deepwiki/generators/diagrams/module_diagram.md"
    click M150 "files/files/src/local_deepwiki/generators/diagrams/sequence_diagram.md"
    click M151 "files/files/src/local_deepwiki/generators/dir_tree.md"
    click M152 "files/files/src/local_deepwiki/generators/examples/__init__.md"
    click M153 "files/files/src/local_deepwiki/generators/examples/discovery.md"
    click M154 "files/files/src/local_deepwiki/generators/examples/docstring.md"
    click M155 "files/files/src/local_deepwiki/generators/examples/extractor.md"
    click M156 "files/files/src/local_deepwiki/generators/examples/orchestrator.md"
    click M157 "files/files/src/local_deepwiki/generators/examples/plugin.md"
    click M158 "files/files/src/local_deepwiki/generators/lazy_cache.md"
    click M159 "files/files/src/local_deepwiki/generators/lazy_generator.md"
    click M160 "files/files/src/local_deepwiki/generators/lazy_resources.md"
    click M161 "files/files/src/local_deepwiki/generators/llms_txt.md"
    click M162 "files/files/src/local_deepwiki/generators/manifest.md"
    click M163 "files/files/src/local_deepwiki/generators/manifest_parsers.md"
    click M164 "files/files/src/local_deepwiki/generators/prefetch.md"
    click M165 "files/files/src/local_deepwiki/generators/progress_tracker.md"
    click M166 "files/files/src/local_deepwiki/generators/protocols.md"
    click M167 "files/files/src/local_deepwiki/generators/search.md"
    click M168 "files/files/src/local_deepwiki/generators/see_also.md"
    click M169 "files/files/src/local_deepwiki/generators/source_refs.md"
    click M170 "files/files/src/local_deepwiki/generators/toc.md"
    click M171 "files/files/src/local_deepwiki/generators/wiki/__init__.md"
    click M172 "files/files/src/local_deepwiki/generators/wiki/codemap_pages.md"
    click M173 "files/files/src/local_deepwiki/generators/wiki/context.md"
    click M174 "files/files/src/local_deepwiki/generators/wiki/files.md"
    click M175 "files/files/src/local_deepwiki/generators/wiki/generator.md"
    click M176 "files/files/src/local_deepwiki/generators/wiki/modules.md"
    click M177 "files/files/src/local_deepwiki/generators/wiki/pages.md"
    click M178 "files/files/src/local_deepwiki/generators/wiki/phases.md"
    click M179 "files/files/src/local_deepwiki/generators/wiki/pipeline.md"
    click M180 "files/files/src/local_deepwiki/generators/wiki/pipeline_params.md"
    click M181 "files/files/src/local_deepwiki/generators/wiki/plugin_runner.md"
    click M182 "files/files/src/local_deepwiki/generators/wiki/postprocessing.md"
    click M183 "files/files/src/local_deepwiki/generators/wiki/source_formatter.md"
    click M184 "files/files/src/local_deepwiki/generators/wiki/status.md"
    click M185 "files/files/src/local_deepwiki/generators/wiki/term_validator.md"
    click M186 "files/files/src/local_deepwiki/generators/wiki/utils.md"
    click M187 "files/files/src/local_deepwiki/handlers/__init__.md"
    click M188 "files/files/src/local_deepwiki/handlers/_error_handling.md"
    click M189 "files/files/src/local_deepwiki/handlers/_export_validation.md"
    click M190 "files/files/src/local_deepwiki/handlers/_index_helpers.md"
    click M191 "files/files/src/local_deepwiki/handlers/_progress.md"
    click M192 "files/files/src/local_deepwiki/handlers/_response.md"
    click M193 "files/files/src/local_deepwiki/handlers/agentic.md"
    click M194 "files/files/src/local_deepwiki/handlers/agentic_data.md"
    click M195 "files/files/src/local_deepwiki/handlers/agentic_workflows.md"
    click M196 "files/files/src/local_deepwiki/handlers/analysis_architecture.md"
    click M197 "files/files/src/local_deepwiki/handlers/analysis_diff.md"
    click M198 "files/files/src/local_deepwiki/handlers/analysis_entity.md"
    click M199 "files/files/src/local_deepwiki/handlers/analysis_metadata.md"
    click M200 "files/files/src/local_deepwiki/handlers/analysis_search.md"
    click M201 "files/files/src/local_deepwiki/handlers/codemap.md"
    click M202 "files/files/src/local_deepwiki/handlers/core.md"
    click M203 "files/files/src/local_deepwiki/handlers/generators.md"
    click M204 "files/files/src/local_deepwiki/handlers/indexing.md"
    click M205 "files/files/src/local_deepwiki/handlers/prompts.md"
    click M206 "files/files/src/local_deepwiki/handlers/research.md"
    click M207 "files/files/src/local_deepwiki/handlers/resources.md"
    click M208 "files/files/src/local_deepwiki/handlers/session_state.md"
    click M209 "files/files/src/local_deepwiki/handlers/types.md"
    click M210 "files/files/src/local_deepwiki/handlers/web_server.md"
    click M211 "files/files/src/local_deepwiki/logging.md"
    click M212 "files/files/src/local_deepwiki/models/__init__.md"
    click M213 "files/files/src/local_deepwiki/models/chunks.md"
    click M214 "files/files/src/local_deepwiki/models/foundation.md"
    click M215 "files/files/src/local_deepwiki/models/provider_types.md"
    click M216 "files/files/src/local_deepwiki/models/research.md"
    click M217 "files/files/src/local_deepwiki/models/tool_args.md"
    click M218 "files/files/src/local_deepwiki/models/wiki.md"
    click M219 "files/files/src/local_deepwiki/plugins/__init__.md"
    click M220 "files/files/src/local_deepwiki/plugins/base.md"
    click M221 "files/files/src/local_deepwiki/plugins/registry.md"
    click M222 "files/files/src/local_deepwiki/progress.md"
    click M223 "files/files/src/local_deepwiki/prompts.md"
    click M224 "files/files/src/local_deepwiki/providers/__init__.md"
    click M225 "files/files/src/local_deepwiki/providers/base.md"
    click M226 "files/files/src/local_deepwiki/providers/credentials.md"
    click M227 "files/files/src/local_deepwiki/providers/embeddings/__init__.md"
    click M228 "files/files/src/local_deepwiki/providers/embeddings/cache.md"
    click M229 "files/files/src/local_deepwiki/providers/embeddings/local.md"
    click M230 "files/files/src/local_deepwiki/providers/embeddings/openai.md"
    click M231 "files/files/src/local_deepwiki/providers/errors.md"
    click M232 "files/files/src/local_deepwiki/providers/llm/__init__.md"
    click M233 "files/files/src/local_deepwiki/providers/llm/anthropic.md"
    click M234 "files/files/src/local_deepwiki/providers/llm/cached.md"
    click M235 "files/files/src/local_deepwiki/providers/llm/ollama.md"
    click M236 "files/files/src/local_deepwiki/providers/llm/openai.md"
    click M237 "files/files/src/local_deepwiki/providers/retry.md"
    click M238 "files/files/src/local_deepwiki/security/__init__.md"
    click M239 "files/files/src/local_deepwiki/security/access_control.md"
    click M240 "files/files/src/local_deepwiki/security/repository_access.md"
    click M241 "files/files/src/local_deepwiki/security/role_config.md"
    click M242 "files/files/src/local_deepwiki/server.md"
    click M243 "files/files/src/local_deepwiki/services/__init__.md"
    click M244 "files/files/src/local_deepwiki/services/analysis_service.md"
    click M245 "files/files/src/local_deepwiki/services/generator_service.md"
    click M246 "files/files/src/local_deepwiki/services/graph_expansion.md"
    click M247 "files/files/src/local_deepwiki/services/indexing_service.md"
    click M248 "files/files/src/local_deepwiki/services/models.md"
    click M249 "files/files/src/local_deepwiki/services/protocols.md"
    click M250 "files/files/src/local_deepwiki/services/provider_factory.md"
    click M251 "files/files/src/local_deepwiki/services/query_service.md"
    click M252 "files/files/src/local_deepwiki/services/wiki_service.md"
    click M253 "files/files/src/local_deepwiki/tool_defs/__init__.md"
    click M254 "files/files/src/local_deepwiki/tool_defs/analysis.md"
    click M255 "files/files/src/local_deepwiki/tool_defs/annotations.md"
    click M256 "files/files/src/local_deepwiki/tool_defs/core.md"
    click M257 "files/files/src/local_deepwiki/tool_defs/generators.md"
    click M258 "files/files/src/local_deepwiki/tool_defs/workflow.md"
    click M259 "files/files/src/local_deepwiki/validation.md"
    click M260 "files/files/src/local_deepwiki/watcher.md"
    click M261 "files/files/src/local_deepwiki/web/__init__.md"
    click M262 "files/files/src/local_deepwiki/web/app.md"
    click M263 "files/files/src/local_deepwiki/web/rate_limit.md"
    click M264 "files/files/src/local_deepwiki/web/routes_architecture.md"
    click M265 "files/files/src/local_deepwiki/web/routes_chat.md"
    click M266 "files/files/src/local_deepwiki/web/routes_codemap.md"
    click M267 "files/files/src/local_deepwiki/web/routes_research.md"
    click M268 "files/files/src/local_deepwiki/web/utils.md"
    classDef external fill:#2d2d3d,stroke:#666,stroke-dasharray: 5 5
    classDef circular fill:#ff6b6b,stroke:#c92a2a
```

## Legend

- **Solid arrows**: Internal module dependencies
- **Dashed arrows**: External dependencies
- **Red dashed arrows**: Circular dependencies (should be addressed)
- **Numbers on arrows**: Number of import statements

## Best Practices

- Avoid circular dependencies as they can lead to import errors and make the codebase harder to understand
- Consider using dependency injection or interfaces to break cycles
- External dependencies are grouped separately for clarity

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:98-100`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](files/src/local_deepwiki/error_factories.md)
- [`src/local_deepwiki/errors.py:53-118`](files/src/local_deepwiki/errors.md)
- [`src/local_deepwiki/watcher.py:40-46`](files/src/local_deepwiki/watcher.md)


*Showing 10 of 269 source files.*
