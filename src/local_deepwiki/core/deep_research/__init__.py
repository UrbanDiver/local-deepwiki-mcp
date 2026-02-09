"""Deep research pipeline for multi-step reasoning about codebases.

This package provides the DeepResearchPipeline and related utilities
for performing multi-step research on indexed code repositories.

All public names are re-exported here for backward compatibility with
code that previously imported from ``core.deep_research`` as a single
module.
"""

from .checkpoints import (
    CheckpointManager,
    cancel_research,
    delete_research_checkpoint,
    get_research_checkpoint,
    list_research_checkpoints,
)
from .pipeline import (
    CancellationCallback,
    DeepResearchPipeline,
    ProgressCallback,
    ResearchCancelledError,
)
from .reasoning import (
    DECOMPOSITION_SYSTEM_PROMPT,
    DECOMPOSITION_USER_PROMPT,
    GAP_ANALYSIS_SYSTEM_PROMPT,
    GAP_ANALYSIS_USER_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_PROMPT,
)
from .serialization import (
    dict_to_search_result,
    search_result_to_dict,
)

# Preserve original private names used by tests and internal code
_search_result_to_dict = search_result_to_dict
_dict_to_search_result = dict_to_search_result

__all__ = [
    "CancellationCallback",
    "cancel_research",
    "CheckpointManager",
    "DeepResearchPipeline",
    "DECOMPOSITION_SYSTEM_PROMPT",
    "DECOMPOSITION_USER_PROMPT",
    "delete_research_checkpoint",
    "GAP_ANALYSIS_SYSTEM_PROMPT",
    "GAP_ANALYSIS_USER_PROMPT",
    "get_research_checkpoint",
    "list_research_checkpoints",
    "ProgressCallback",
    "ResearchCancelledError",
    "SYNTHESIS_SYSTEM_PROMPT",
    "SYNTHESIS_USER_PROMPT",
    "_search_result_to_dict",
    "_dict_to_search_result",
]
