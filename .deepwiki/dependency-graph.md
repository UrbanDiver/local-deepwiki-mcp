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
        M97[__init__]
        M98[__init__]
        M99[api_docs]
        M100[architecture_compare]
        M101[architecture_composite]
        M102[architecture_health]
        M103[architecture_report]
        M104[callgraph]
        M105[complexity]
        M106[coupling]
        M107[coupling_page]
        M108[coverage]
        M109[dependency_graph]
        M110[dependency_graph_data]
        M111[design_smells]
        M112[glossary]
        M113[health_page]
        M114[health_scoring]
        M115[hotspots]
        M116[hotspots_page]
        M117[inheritance]
        M118[layer_analysis]
        M119[module_dependencies]
        M120[module_health]
        M121[onboarding]
        M122[recommendations]
        M123[smells_page]
        M124[source_filter]
        M125[stale_detection]
        M126[tours]
        M127[changelog]
        M128[__init__]
        M129[cache]
        M130[generator]
        M131[graph]
        M132[models]
        M133[overview]
        M134[params]
        M135[viz]
        M136[context_builder]
        M137[crosslinks]
        M138[__init__]
        M139[_utils]
        M140[class_diagram]
        M141[dependency_diagram]
        M142[language_pie]
        M143[module_diagram]
        M144[sequence_diagram]
        M145[dir_tree]
        M146[__init__]
        M147[discovery]
        M148[docstring]
        M149[extractor]
        M150[orchestrator]
        M151[plugin]
        M152[lazy_cache]
        M153[lazy_generator]
        M154[lazy_resources]
        M155[llms_txt]
        M156[manifest]
        M157[manifest_parsers]
        M158[prefetch]
        M159[progress_tracker]
        M160[protocols]
        M161[search]
        M162[see_also]
        M163[source_refs]
        M164[toc]
        M165[__init__]
        M166[codemap_pages]
        M167[context]
        M168[files]
        M169[generator]
        M170[modules]
        M171[pages]
        M172[phases]
        M173[pipeline]
        M174[pipeline_params]
        M175[plugin_runner]
        M176[postprocessing]
        M177[source_formatter]
        M178[status]
        M179[term_validator]
        M180[utils]
        M181[__init__]
        M182[_error_handling]
        M183[_export_validation]
        M184[_index_helpers]
        M185[_progress]
        M186[_response]
        M187[agentic]
        M188[agentic_data]
        M189[agentic_workflows]
        M190[analysis_architecture]
        M191[analysis_diff]
        M192[analysis_entity]
        M193[analysis_metadata]
        M194[analysis_search]
        M195[codemap]
        M196[core]
        M197[generators]
        M198[indexing]
        M199[prompts]
        M200[research]
        M201[resources]
        M202[session_state]
        M203[types]
        M204[web_server]
        M205[logging]
        M206[__init__]
        M207[chunks]
        M208[foundation]
        M209[provider_types]
        M210[research]
        M211[tool_args]
        M212[wiki]
        M213[__init__]
        M214[base]
        M215[registry]
        M216[progress]
        M217[prompts]
        M218[__init__]
        M219[base]
        M220[credentials]
        M221[__init__]
        M222[cache]
        M223[local]
        M224[openai]
        M225[errors]
        M226[__init__]
        M227[anthropic]
        M228[cached]
        M229[ollama]
        M230[openai]
        M231[retry]
        M232[__init__]
        M233[access_control]
        M234[repository_access]
        M235[role_config]
        M236[server]
        M237[__init__]
        M238[analysis_service]
        M239[generator_service]
        M240[graph_expansion]
        M241[indexing_service]
        M242[models]
        M243[protocols]
        M244[provider_factory]
        M245[query_service]
        M246[wiki_service]
        M247[__init__]
        M248[analysis]
        M249[annotations]
        M250[core]
        M251[generators]
        M252[workflow]
        M253[validation]
        M254[watcher]
        M255[__init__]
        M256[app]
        M257[rate_limit]
        M258[routes_architecture]
        M259[routes_chat]
        M260[routes_codemap]
        M261[routes_research]
        M262[utils]
    end
    subgraph external[External Dependencies]
        E263([argparse]):::external
        E264([asyncio]):::external
        E265([collections]):::external
        E266([contextlib]):::external
        E267([contextvars]):::external
        E268([dataclasses]):::external
        E269([enum]):::external
        E270([functools]):::external
        E271([importlib]):::external
        E272([json]):::external
    end
    M0 -.-> E271
    M6 -.-> E263
    M6 -.-> E265
    M6 -.-> E268
    M6 --> M16
    M6 --> M32
    M8 -.-> E271
    M15 -.-> E266
    M15 -.-> E267
    M15 -.-> E268
    M15 --> M16
    M15 --> M209
    M75 -.-> E268
    M75 --> M77
    M101 --> M102
    M101 --> M103
    M101 --> M119
    M101 --> M122
    M123 -.-> E265
    M124 --> M57
    M133 -.-> E265
    M133 -.-> E268
    M133 -.-> E272
    M133 --> M59
    M133 --> M205
    M180 --> M59
    M209 -.-> E269
    M233 -.-> E264
    M233 -.-> E265
    M233 -.-> E267
    M233 -.-> E268
    M233 -.-> E269
    M233 -.-> E270
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
    click M97 "files/files/src/local_deepwiki/generators/__init__.md"
    click M98 "files/files/src/local_deepwiki/generators/analysis/__init__.md"
    click M99 "files/files/src/local_deepwiki/generators/analysis/api_docs.md"
    click M100 "files/files/src/local_deepwiki/generators/analysis/architecture_compare.md"
    click M101 "files/files/src/local_deepwiki/generators/analysis/architecture_composite.md"
    click M102 "files/files/src/local_deepwiki/generators/analysis/architecture_health.md"
    click M103 "files/files/src/local_deepwiki/generators/analysis/architecture_report.md"
    click M104 "files/files/src/local_deepwiki/generators/analysis/callgraph.md"
    click M105 "files/files/src/local_deepwiki/generators/analysis/complexity.md"
    click M106 "files/files/src/local_deepwiki/generators/analysis/coupling.md"
    click M107 "files/files/src/local_deepwiki/generators/analysis/coupling_page.md"
    click M108 "files/files/src/local_deepwiki/generators/analysis/coverage.md"
    click M109 "files/files/src/local_deepwiki/generators/analysis/dependency_graph.md"
    click M110 "files/files/src/local_deepwiki/generators/analysis/dependency_graph_data.md"
    click M111 "files/files/src/local_deepwiki/generators/analysis/design_smells.md"
    click M112 "files/files/src/local_deepwiki/generators/analysis/glossary.md"
    click M113 "files/files/src/local_deepwiki/generators/analysis/health_page.md"
    click M114 "files/files/src/local_deepwiki/generators/analysis/health_scoring.md"
    click M115 "files/files/src/local_deepwiki/generators/analysis/hotspots.md"
    click M116 "files/files/src/local_deepwiki/generators/analysis/hotspots_page.md"
    click M117 "files/files/src/local_deepwiki/generators/analysis/inheritance.md"
    click M118 "files/files/src/local_deepwiki/generators/analysis/layer_analysis.md"
    click M119 "files/files/src/local_deepwiki/generators/analysis/module_dependencies.md"
    click M120 "files/files/src/local_deepwiki/generators/analysis/module_health.md"
    click M121 "files/files/src/local_deepwiki/generators/analysis/onboarding.md"
    click M122 "files/files/src/local_deepwiki/generators/analysis/recommendations.md"
    click M123 "files/files/src/local_deepwiki/generators/analysis/smells_page.md"
    click M124 "files/files/src/local_deepwiki/generators/analysis/source_filter.md"
    click M125 "files/files/src/local_deepwiki/generators/analysis/stale_detection.md"
    click M126 "files/files/src/local_deepwiki/generators/analysis/tours.md"
    click M127 "files/files/src/local_deepwiki/generators/changelog.md"
    click M128 "files/files/src/local_deepwiki/generators/codemap/__init__.md"
    click M129 "files/files/src/local_deepwiki/generators/codemap/cache.md"
    click M130 "files/files/src/local_deepwiki/generators/codemap/generator.md"
    click M131 "files/files/src/local_deepwiki/generators/codemap/graph.md"
    click M132 "files/files/src/local_deepwiki/generators/codemap/models.md"
    click M133 "files/files/src/local_deepwiki/generators/codemap/overview.md"
    click M134 "files/files/src/local_deepwiki/generators/codemap/params.md"
    click M135 "files/files/src/local_deepwiki/generators/codemap/viz.md"
    click M136 "files/files/src/local_deepwiki/generators/context_builder.md"
    click M137 "files/files/src/local_deepwiki/generators/crosslinks.md"
    click M138 "files/files/src/local_deepwiki/generators/diagrams/__init__.md"
    click M139 "files/files/src/local_deepwiki/generators/diagrams/_utils.md"
    click M140 "files/files/src/local_deepwiki/generators/diagrams/class_diagram.md"
    click M141 "files/files/src/local_deepwiki/generators/diagrams/dependency_diagram.md"
    click M142 "files/files/src/local_deepwiki/generators/diagrams/language_pie.md"
    click M143 "files/files/src/local_deepwiki/generators/diagrams/module_diagram.md"
    click M144 "files/files/src/local_deepwiki/generators/diagrams/sequence_diagram.md"
    click M145 "files/files/src/local_deepwiki/generators/dir_tree.md"
    click M146 "files/files/src/local_deepwiki/generators/examples/__init__.md"
    click M147 "files/files/src/local_deepwiki/generators/examples/discovery.md"
    click M148 "files/files/src/local_deepwiki/generators/examples/docstring.md"
    click M149 "files/files/src/local_deepwiki/generators/examples/extractor.md"
    click M150 "files/files/src/local_deepwiki/generators/examples/orchestrator.md"
    click M151 "files/files/src/local_deepwiki/generators/examples/plugin.md"
    click M152 "files/files/src/local_deepwiki/generators/lazy_cache.md"
    click M153 "files/files/src/local_deepwiki/generators/lazy_generator.md"
    click M154 "files/files/src/local_deepwiki/generators/lazy_resources.md"
    click M155 "files/files/src/local_deepwiki/generators/llms_txt.md"
    click M156 "files/files/src/local_deepwiki/generators/manifest.md"
    click M157 "files/files/src/local_deepwiki/generators/manifest_parsers.md"
    click M158 "files/files/src/local_deepwiki/generators/prefetch.md"
    click M159 "files/files/src/local_deepwiki/generators/progress_tracker.md"
    click M160 "files/files/src/local_deepwiki/generators/protocols.md"
    click M161 "files/files/src/local_deepwiki/generators/search.md"
    click M162 "files/files/src/local_deepwiki/generators/see_also.md"
    click M163 "files/files/src/local_deepwiki/generators/source_refs.md"
    click M164 "files/files/src/local_deepwiki/generators/toc.md"
    click M165 "files/files/src/local_deepwiki/generators/wiki/__init__.md"
    click M166 "files/files/src/local_deepwiki/generators/wiki/codemap_pages.md"
    click M167 "files/files/src/local_deepwiki/generators/wiki/context.md"
    click M168 "files/files/src/local_deepwiki/generators/wiki/files.md"
    click M169 "files/files/src/local_deepwiki/generators/wiki/generator.md"
    click M170 "files/files/src/local_deepwiki/generators/wiki/modules.md"
    click M171 "files/files/src/local_deepwiki/generators/wiki/pages.md"
    click M172 "files/files/src/local_deepwiki/generators/wiki/phases.md"
    click M173 "files/files/src/local_deepwiki/generators/wiki/pipeline.md"
    click M174 "files/files/src/local_deepwiki/generators/wiki/pipeline_params.md"
    click M175 "files/files/src/local_deepwiki/generators/wiki/plugin_runner.md"
    click M176 "files/files/src/local_deepwiki/generators/wiki/postprocessing.md"
    click M177 "files/files/src/local_deepwiki/generators/wiki/source_formatter.md"
    click M178 "files/files/src/local_deepwiki/generators/wiki/status.md"
    click M179 "files/files/src/local_deepwiki/generators/wiki/term_validator.md"
    click M180 "files/files/src/local_deepwiki/generators/wiki/utils.md"
    click M181 "files/files/src/local_deepwiki/handlers/__init__.md"
    click M182 "files/files/src/local_deepwiki/handlers/_error_handling.md"
    click M183 "files/files/src/local_deepwiki/handlers/_export_validation.md"
    click M184 "files/files/src/local_deepwiki/handlers/_index_helpers.md"
    click M185 "files/files/src/local_deepwiki/handlers/_progress.md"
    click M186 "files/files/src/local_deepwiki/handlers/_response.md"
    click M187 "files/files/src/local_deepwiki/handlers/agentic.md"
    click M188 "files/files/src/local_deepwiki/handlers/agentic_data.md"
    click M189 "files/files/src/local_deepwiki/handlers/agentic_workflows.md"
    click M190 "files/files/src/local_deepwiki/handlers/analysis_architecture.md"
    click M191 "files/files/src/local_deepwiki/handlers/analysis_diff.md"
    click M192 "files/files/src/local_deepwiki/handlers/analysis_entity.md"
    click M193 "files/files/src/local_deepwiki/handlers/analysis_metadata.md"
    click M194 "files/files/src/local_deepwiki/handlers/analysis_search.md"
    click M195 "files/files/src/local_deepwiki/handlers/codemap.md"
    click M196 "files/files/src/local_deepwiki/handlers/core.md"
    click M197 "files/files/src/local_deepwiki/handlers/generators.md"
    click M198 "files/files/src/local_deepwiki/handlers/indexing.md"
    click M199 "files/files/src/local_deepwiki/handlers/prompts.md"
    click M200 "files/files/src/local_deepwiki/handlers/research.md"
    click M201 "files/files/src/local_deepwiki/handlers/resources.md"
    click M202 "files/files/src/local_deepwiki/handlers/session_state.md"
    click M203 "files/files/src/local_deepwiki/handlers/types.md"
    click M204 "files/files/src/local_deepwiki/handlers/web_server.md"
    click M205 "files/files/src/local_deepwiki/logging.md"
    click M206 "files/files/src/local_deepwiki/models/__init__.md"
    click M207 "files/files/src/local_deepwiki/models/chunks.md"
    click M208 "files/files/src/local_deepwiki/models/foundation.md"
    click M209 "files/files/src/local_deepwiki/models/provider_types.md"
    click M210 "files/files/src/local_deepwiki/models/research.md"
    click M211 "files/files/src/local_deepwiki/models/tool_args.md"
    click M212 "files/files/src/local_deepwiki/models/wiki.md"
    click M213 "files/files/src/local_deepwiki/plugins/__init__.md"
    click M214 "files/files/src/local_deepwiki/plugins/base.md"
    click M215 "files/files/src/local_deepwiki/plugins/registry.md"
    click M216 "files/files/src/local_deepwiki/progress.md"
    click M217 "files/files/src/local_deepwiki/prompts.md"
    click M218 "files/files/src/local_deepwiki/providers/__init__.md"
    click M219 "files/files/src/local_deepwiki/providers/base.md"
    click M220 "files/files/src/local_deepwiki/providers/credentials.md"
    click M221 "files/files/src/local_deepwiki/providers/embeddings/__init__.md"
    click M222 "files/files/src/local_deepwiki/providers/embeddings/cache.md"
    click M223 "files/files/src/local_deepwiki/providers/embeddings/local.md"
    click M224 "files/files/src/local_deepwiki/providers/embeddings/openai.md"
    click M225 "files/files/src/local_deepwiki/providers/errors.md"
    click M226 "files/files/src/local_deepwiki/providers/llm/__init__.md"
    click M227 "files/files/src/local_deepwiki/providers/llm/anthropic.md"
    click M228 "files/files/src/local_deepwiki/providers/llm/cached.md"
    click M229 "files/files/src/local_deepwiki/providers/llm/ollama.md"
    click M230 "files/files/src/local_deepwiki/providers/llm/openai.md"
    click M231 "files/files/src/local_deepwiki/providers/retry.md"
    click M232 "files/files/src/local_deepwiki/security/__init__.md"
    click M233 "files/files/src/local_deepwiki/security/access_control.md"
    click M234 "files/files/src/local_deepwiki/security/repository_access.md"
    click M235 "files/files/src/local_deepwiki/security/role_config.md"
    click M236 "files/files/src/local_deepwiki/server.md"
    click M237 "files/files/src/local_deepwiki/services/__init__.md"
    click M238 "files/files/src/local_deepwiki/services/analysis_service.md"
    click M239 "files/files/src/local_deepwiki/services/generator_service.md"
    click M240 "files/files/src/local_deepwiki/services/graph_expansion.md"
    click M241 "files/files/src/local_deepwiki/services/indexing_service.md"
    click M242 "files/files/src/local_deepwiki/services/models.md"
    click M243 "files/files/src/local_deepwiki/services/protocols.md"
    click M244 "files/files/src/local_deepwiki/services/provider_factory.md"
    click M245 "files/files/src/local_deepwiki/services/query_service.md"
    click M246 "files/files/src/local_deepwiki/services/wiki_service.md"
    click M247 "files/files/src/local_deepwiki/tool_defs/__init__.md"
    click M248 "files/files/src/local_deepwiki/tool_defs/analysis.md"
    click M249 "files/files/src/local_deepwiki/tool_defs/annotations.md"
    click M250 "files/files/src/local_deepwiki/tool_defs/core.md"
    click M251 "files/files/src/local_deepwiki/tool_defs/generators.md"
    click M252 "files/files/src/local_deepwiki/tool_defs/workflow.md"
    click M253 "files/files/src/local_deepwiki/validation.md"
    click M254 "files/files/src/local_deepwiki/watcher.md"
    click M255 "files/files/src/local_deepwiki/web/__init__.md"
    click M256 "files/files/src/local_deepwiki/web/app.md"
    click M257 "files/files/src/local_deepwiki/web/rate_limit.md"
    click M258 "files/files/src/local_deepwiki/web/routes_architecture.md"
    click M259 "files/files/src/local_deepwiki/web/routes_chat.md"
    click M260 "files/files/src/local_deepwiki/web/routes_codemap.md"
    click M261 "files/files/src/local_deepwiki/web/routes_research.md"
    click M262 "files/files/src/local_deepwiki/web/utils.md"
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
