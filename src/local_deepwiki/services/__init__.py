"""Service layer: business logic extracted from handlers.

Services encapsulate core operations (querying, wiki management, indexing)
with explicit dependency injection, leaving RBAC, audit logging, and MCP
response formatting in the handler layer.
"""

from local_deepwiki.services.indexing_service import IndexingService
from local_deepwiki.services.models import (
    ExportResult,
    IndexPipelineResult,
    QueryResult,
    SourceEntry,
)
from local_deepwiki.services.query_service import QueryService
from local_deepwiki.services.wiki_service import WikiService

__all__ = [
    "ExportResult",
    "IndexPipelineResult",
    "IndexingService",
    "QueryResult",
    "QueryService",
    "SourceEntry",
    "WikiService",
]
