"""Backward-compatibility re-export shim.

All symbols that were previously defined here have been moved to focused modules:

- ``_error_handling`` — ``handle_tool_errors``, ``ToolHandler``
- ``_export_validation`` — ``FORBIDDEN_EXPORT_DIRS``, ``FORBIDDEN_VAR_SUBDIRS``,
  ``_check_forbidden_dirs``, ``_validate_export_path``
- ``_index_helpers`` — ``_load_index_status``, ``_create_vector_store``,
  ``_format_research_results``, ``_is_test_file``
- ``_progress`` — ``ProgressNotifier``, ``create_progress_notifier``
- ``_response`` — ``wrap_tool_response``, ``make_tool_text_content``,
  ``build_wiki_resource_uri``

Import directly from those modules or from the original source packages instead.
This shim exists only for backward compatibility with external consumers and will
be removed in a future release.
"""

from __future__ import annotations

# Re-export everything for backward compatibility.  New code should import
# from the focused handler sub-modules or from their canonical source packages.

from local_deepwiki.config import get_config as get_config
from local_deepwiki.core.audit import get_audit_logger as get_audit_logger
from local_deepwiki.core.path_utils import is_test_file as is_test_file
from local_deepwiki.core.rate_limiter import (
    RateLimitExceeded as RateLimitExceeded,
    get_rate_limiter as get_rate_limiter,
)
from local_deepwiki.core.vectorstore import VectorStore as VectorStore
from local_deepwiki.errors import (
    DeepWikiError as DeepWikiError,
    ExportError as ExportError,
    IndexingError as IndexingError,
    ResearchError as ResearchError,
    ValidationError as ValidationError,
    format_error_response as format_error_response,
    indexing_error as indexing_error,
    map_exception_to_deepwiki_error as map_exception_to_deepwiki_error,
    not_indexed_error as not_indexed_error,
    path_not_found_error as path_not_found_error,
    provider_error as provider_error,
    sanitize_error_message as sanitize_error_message,
)
from local_deepwiki.generators.wiki import generate_wiki as generate_wiki
from local_deepwiki.handlers._error_handling import (
    ToolHandler as ToolHandler,
    handle_tool_errors as handle_tool_errors,
)
from local_deepwiki.handlers._export_validation import (
    FORBIDDEN_EXPORT_DIRS as FORBIDDEN_EXPORT_DIRS,
    FORBIDDEN_VAR_SUBDIRS as FORBIDDEN_VAR_SUBDIRS,
    _check_forbidden_dirs as _check_forbidden_dirs,
    _validate_export_path as _validate_export_path,
)
from local_deepwiki.handlers._index_helpers import (
    _create_vector_store as _create_vector_store,
    _format_research_results as _format_research_results,
    _is_test_file as _is_test_file,
    _load_index_status as _load_index_status,
)
from local_deepwiki.handlers._progress import (
    ProgressNotifier as ProgressNotifier,
    create_progress_notifier as create_progress_notifier,
)
from local_deepwiki.handlers._response import (
    build_wiki_resource_uri as build_wiki_resource_uri,
    make_tool_text_content as make_tool_text_content,
    wrap_tool_response as wrap_tool_response,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    AnalyzeDiffArgs as AnalyzeDiffArgs,
    AskAboutDiffArgs as AskAboutDiffArgs,
    AskQuestionArgs as AskQuestionArgs,
    BatchExplainEntitiesArgs as BatchExplainEntitiesArgs,
    CancelResearchArgs as CancelResearchArgs,
    DeepResearchArgs as DeepResearchArgs,
    DetectSecretsArgs as DetectSecretsArgs,
    DetectStaleDocsArgs as DetectStaleDocsArgs,
    ExplainEntityArgs as ExplainEntityArgs,
    ExportWikiHtmlArgs as ExportWikiHtmlArgs,
    ExportWikiPdfArgs as ExportWikiPdfArgs,
    FuzzySearchArgs as FuzzySearchArgs,
    GenerateCodemapArgs as GenerateCodemapArgs,
    GetApiDocsArgs as GetApiDocsArgs,
    GetCallGraphArgs as GetCallGraphArgs,
    GetChangelogArgs as GetChangelogArgs,
    GetComplexityMetricsArgs as GetComplexityMetricsArgs,
    GetCoverageArgs as GetCoverageArgs,
    GetDiagramsArgs as GetDiagramsArgs,
    GetFileContextArgs as GetFileContextArgs,
    GetGlossaryArgs as GetGlossaryArgs,
    GetIndexStatusArgs as GetIndexStatusArgs,
    GetInheritanceArgs as GetInheritanceArgs,
    GetProjectManifestArgs as GetProjectManifestArgs,
    GetTestExamplesArgs as GetTestExamplesArgs,
    GetWikiStatsArgs as GetWikiStatsArgs,
    ImpactAnalysisArgs as ImpactAnalysisArgs,
    IndexingProgress as IndexingProgress,
    IndexingProgressType as IndexingProgressType,
    IndexRepositoryArgs as IndexRepositoryArgs,
    ListIndexedReposArgs as ListIndexedReposArgs,
    ListResearchCheckpointsArgs as ListResearchCheckpointsArgs,
    QueryCodebaseArgs as QueryCodebaseArgs,
    ReadWikiPageArgs as ReadWikiPageArgs,
    ReadWikiStructureArgs as ReadWikiStructureArgs,
    ResearchCheckpoint as ResearchCheckpoint,
    ResumeResearchArgs as ResumeResearchArgs,
    RunWorkflowArgs as RunWorkflowArgs,
    SearchCodeArgs as SearchCodeArgs,
    SearchWikiArgs as SearchWikiArgs,
    ServeWikiArgs as ServeWikiArgs,
    StopWikiServerArgs as StopWikiServerArgs,
    SuggestCodemapTopicsArgs as SuggestCodemapTopicsArgs,
    SuggestNextActionsArgs as SuggestNextActionsArgs,
)
from local_deepwiki.progress import (
    GetOperationProgressArgs as GetOperationProgressArgs,
    OperationType as OperationType,
    ProgressBuffer as ProgressBuffer,
    ProgressManager as ProgressManager,
    ProgressPhase as ProgressPhase,
    ProgressUpdate as ProgressUpdate,
    get_progress_registry as get_progress_registry,
)
from local_deepwiki.providers.embeddings import (
    get_embedding_provider as get_embedding_provider,
)
from local_deepwiki.security import (
    AccessDeniedException as AccessDeniedException,
    AuthenticationException as AuthenticationException,
    Permission as Permission,
    get_access_controller as get_access_controller,
    get_repository_access_controller as get_repository_access_controller,
)
from local_deepwiki.validation import (
    MAX_WIKI_PAGE_SIZE as MAX_WIKI_PAGE_SIZE,
    validate_chunk_type as validate_chunk_type,
    validate_deep_research_parameters as validate_deep_research_parameters,
    validate_index_parameters as validate_index_parameters,
    validate_language as validate_language,
    validate_languages_list as validate_languages_list,
    validate_path_pattern as validate_path_pattern,
    validate_query_parameters as validate_query_parameters,
)

logger = get_logger(__name__)
