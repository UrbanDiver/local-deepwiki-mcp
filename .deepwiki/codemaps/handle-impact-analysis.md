# Codemap: How handle_impact_analysis Works

<div data-codemap-query="How does [handle_impact_analysis](../files/src/local_deepwiki/handlers/analysis_entity.md) work?" data-codemap-entry="[handle_impact_analysis](../files/src/local_deepwiki/handlers/analysis_entity.md)" data-codemap-focus="execution_flow" style="display:none"></div>

> Entry point: [`handle_impact_analysis`](../files/src/local_deepwiki/handlers/analysis_entity.md) in `src/local_deepwiki/handlers/analysis_entity.py`

## Execution Flow

```mermaid
flowchart TD
    subgraph src/local_deepwiki/config/models_py["src/local_deepwiki/config/models.py"]
        N0["get_vector_db_path\n:255-257"]
    end
    subgraph src/local_deepwiki/core/path_utils_py["src/local_deepwiki/core/path_utils.py"]
        N1["validate_file_in_repo\n:17-40"]
    end
    subgraph src/local_deepwiki/error_factories_py["src/local_deepwiki/error_factories.py"]
        N2["path_not_found_error\n:473-491"]
    end
    subgraph src/local_deepwiki/errors_py["src/local_deepwiki/errors.py"]
        N3["ValidationError\n:121-157"]
    end
    subgraph src/local_deepwiki/handlers/_index_helpers_py["src/local_deepwiki/handlers/_index_helpers.py"]
        N4["_create_vector_store\n:52-68"]
    end
    subgraph src/local_deepwiki/handlers/_response_py["src/local_deepwiki/handlers/_response.py"]
        N5["make_tool_text_content\n:40-61"]
        N6["wrap_tool_response\n:0-0"]
    end
    subgraph src/local_deepwiki/handlers/analysis_entity_py["src/local_deepwiki/handlers/analysis_entity.py"]
        N7["handle_impact_analysis\n:377-433"]
    end
    subgraph src/local_deepwiki/plugins/registry_py["src/local_deepwiki/plugins/registry.py"]
        N8["get_embedding_provider\n:192-201"]
    end
    subgraph src/local_deepwiki/security/access_control_py["src/local_deepwiki/security/access_control.py"]
        N9["get_access_controller\n:347-361"]
    end
    subgraph src/local_deepwiki/services/analysis_service_py["src/local_deepwiki/services/analysis_service.py"]
        N10["ImpactAnalysisRequest\n:41-58"]
    end
    N4 -.-> N0
    N4 -.-> N8
    N7 -.-> N10
    N7 -.-> N4
    N7 -.-> N9
    N7 -.-> N5
    N7 -.-> N2
    N7 -.-> N1
    N5 --> N6
    N2 -.-> N3
    N1 -.-> N3
    N1 -.-> N2
    classDef entry fill:#2d6a4f,color:#fff
    classDef crossfile fill:#1d3557,color:#fff
    classDef leaf fill:#6c757d,color:#fff
    class N7 entry
    class N0,N1,N10,N2,N3,N4,N5,N8,N9 crossfile
    class N6 leaf
    click N0 "../files/src/local_deepwiki/config/models.md" _blank
    click N1 "../files/src/local_deepwiki/core/path_utils.md" _blank
    click N2 "../files/src/local_deepwiki/error_factories.md" _blank
    click N3 "../files/src/local_deepwiki/errors.md" _blank
    click N4 "../files/src/local_deepwiki/handlers/_index_helpers.md" _blank
    click N5 "../files/src/local_deepwiki/handlers/_response.md" _blank
    click N6 "../files/src/local_deepwiki/handlers/_response.md" _blank
    click N7 "../files/src/local_deepwiki/handlers/analysis_entity.md" _blank
    click N8 "../files/src/local_deepwiki/plugins/registry.md" _blank
    click N9 "../files/src/local_deepwiki/security/access_control.md" _blank
    click N10 "../files/src/local_deepwiki/services/analysis_service.md" _blank
```

## Trace

## Summary
This code flow implements the impact analysis functionality that determines the blast radius of changes to a file or entity by examining multiple dependency types including reverse call graphs, inheritance relationships, file imports, and wiki documentation. The [`handle_impact_analysis`](../files/src/local_deepwiki/handlers/analysis_entity.md) function serves as the main entry point that orchestrates the analysis process by validating inputs, creating necessary components like vector stores, and coordinating various analysis services to [collect](../files/src/local_deepwiki/web/routes_chat.md) information about affected entities.

## Execution Trace
1. [`handle_impact_analysis`](../files/src/local_deepwiki/handlers/analysis_entity.md) (src/local_deepwiki/handlers/analysis_entity.py:377-433) - Main function that processes impact analysis requests by validating arguments, creating vector stores, and calling analysis services
   - Calls [`ImpactAnalysisArgs`](../files/src/local_deepwiki/models/tool_args.md) (src/local_deepwiki/models/tool_args.py:375-401) to validate and parse input arguments
   - Calls [`validate_file_in_repo`](../files/src/local_deepwiki/core/path_utils.md) (src/local_deepwiki/core/path_utils.py:17-40) to ensure the file path is valid and within repository bounds
   - Calls `_create_vector_store` (src/local_deepwiki/handlers/_index_helpers.py:52-68) to initialize the vector database for semantic analysis
   - Calls [`get_access_controller`](../files/src/local_deepwiki/security/access_control.md) (src/local_deepwiki/security/access_control.py:347-361) to verify access permissions

2. `_create_vector_store` (src/local_deepwiki/handlers/_index_helpers.py:52-68) - Creates a vector store with configured embedding provider for semantic similarity analysis
   - Calls `Config.get_vector_db_path` (src/local_deepwiki/config/models.py:255-257) to determine the vector database path
   - Calls `PluginRegistry.get_embedding_provider` (src/local_deepwiki/plugins/registry.py:192-201) to get the embedding provider plugin

3. [`ImpactAnalysisRequest`](../files/src/local_deepwiki/services/analysis_service.md) (src/local_deepwiki/services/analysis_service.py:41-58) - Creates an immutable request object containing analysis parameters
   - Calls [`CallGraphExtractor`](../files/src/local_deepwiki/generators/analysis/callgraph.md) (src/local_deepwiki/generators/analysis/callgraph.py:314-382) to initialize the call graph extraction component

4. Various analysis collection functions are called in sequence:
   - `_collect_reverse_calls` (src/local_deepwiki/services/analysis_service.py:615-678) - Extracts reverse call graph information
   - `_collect_inheritance_dependents` (src/local_deepwiki/services/analysis_service.py:681-721) - Finds inheritance-based dependents
   - `_collect_file_dependents` (src/local_deepwiki/services/analysis_service.py:724-767) - Identifies file import dependents
   - `_collect_affected_wiki_pages` (src/local_deepwiki/services/analysis_service.py:770-797) - Finds wiki documentation that references the file

5. Final processing:
   - Calls [`make_tool_text_content`](../files/src/local_deepwiki/handlers/_response.md) (src/local_deepwiki/handlers/_response.py:40-61) to format the results
   - Calls [`wrap_tool_response`](../files/src/local_deepwiki/handlers/_response.md) (src/local_deepwiki/handlers/_response.py:12-37) to wrap the response in a standard JSON envelope

## Key Observations
- The code follows a service-oriented architecture where different analysis components (call graph, inheritance, file dependencies, wiki pages) are handled by separate functions that [collect](../files/src/local_deepwiki/web/routes_chat.md) specific types of information
- Input validation is comprehensive, checking file paths against repository boundaries and using structured validation through pydantic models
- The design uses dependency injection patterns where components like vector stores and embedding providers are created through factory methods rather than direct instantiation
- Error handling is robust with specific error types like [`ValidationError`](../files/src/local_deepwiki/errors.md) and proper path validation to prevent security issues like path traversal attacks

## Statistics

| Metric | Value |
|--------|-------|
| Nodes | 11 |
| Edges | 12 |
| Cross-file edges | 11 |
| Files involved | 10 |

## Files Involved

- [`src/local_deepwiki/config/models.py`](../files/src/local_deepwiki/config/models.md)
- [`src/local_deepwiki/core/path_utils.py`](../files/src/local_deepwiki/core/path_utils.md)
- [`src/local_deepwiki/error_factories.py`](../files/src/local_deepwiki/error_factories.md)
- [`src/local_deepwiki/errors.py`](../files/src/local_deepwiki/errors.md)
- [`src/local_deepwiki/handlers/_index_helpers.py`](../files/src/local_deepwiki/handlers/_index_helpers.md)
- [`src/local_deepwiki/handlers/_response.py`](../files/src/local_deepwiki/handlers/_response.md)
- [`src/local_deepwiki/handlers/analysis_entity.py`](../files/src/local_deepwiki/handlers/analysis_entity.md)
- [`src/local_deepwiki/plugins/registry.py`](../files/src/local_deepwiki/plugins/registry.md)
- [`src/local_deepwiki/security/access_control.py`](../files/src/local_deepwiki/security/access_control.md)
- [`src/local_deepwiki/services/analysis_service.py`](../files/src/local_deepwiki/services/analysis_service.md)

## Relevant Source Files

- [`src/local_deepwiki/handlers/analysis_entity.py:46-55`](../files/src/local_deepwiki/handlers/analysis_entity.md)
