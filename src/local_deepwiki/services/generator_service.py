"""Generator service: business logic for diagram, glossary, coverage, and other generators.

Extracted from handlers/generators.py. Each method encapsulates the common
generator pattern (load chunks, call generator, return result dict) while
the handler layer retains RBAC, arg validation, and MCP response formatting.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import ValidationError
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


class GeneratorService:
    """Encapsulates generator tool business logic.

    Depends on a VectorStore and Config; does not interact with MCP
    types or RBAC. Each method returns a plain dict suitable for
    JSON serialization by the handler layer.
    """

    __slots__ = ("_vector_store", "_config")

    def __init__(self, vector_store: VectorStore, config: Config) -> None:
        self._vector_store = vector_store
        self._config = config

    async def generate_glossary(
        self,
        index_status: Any,
        *,
        search: str | None = None,
        file_path: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Collect code entity glossary with optional filtering.

        Args:
            index_status: Loaded IndexStatus for the repository.
            search: Optional text filter on entity name/docstring.
            file_path: Optional file path suffix filter.
            offset: Pagination offset.
            limit: Maximum entities to return.

        Returns:
            Dict with entities list and pagination metadata.
        """
        from local_deepwiki.generators.analysis.glossary import collect_all_entities

        entities = await collect_all_entities(index_status, self._vector_store)

        if search:
            search_lower = search.lower()
            entities = [
                e
                for e in entities
                if search_lower in e.name.lower()
                or (e.docstring and search_lower in e.docstring.lower())
            ]

        if file_path:
            entities = [e for e in entities if e.file_path.endswith(file_path)]

        total_entities = len(entities)
        entities = entities[offset : offset + limit]

        return {
            "status": "success",
            "total_entities": total_entities,
            "returned": len(entities),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total_entities,
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "file_path": e.file_path,
                    "docstring": e.docstring,
                }
                for e in entities
            ],
        }

    async def generate_diagrams(
        self,
        index_status: Any,
        repo_path: Path,
        diagram_type: str,
        *,
        entry_point: str | None = None,
    ) -> dict[str, Any]:
        """Generate a Mermaid diagram of the requested type.

        Args:
            index_status: Loaded IndexStatus for the repository.
            repo_path: Resolved repository path.
            diagram_type: One of class, dependency, module, language_pie, sequence.
            entry_point: Required for sequence diagrams.

        Returns:
            Dict with diagram_type and mermaid string, or a message if empty.

        Raises:
            ValidationError: If entry_point is missing for sequence diagrams.
        """
        from local_deepwiki.generators.analysis.callgraph import CallGraphExtractor
        from local_deepwiki.generators.diagrams import (
            generate_class_diagram,
            generate_dependency_graph,
            generate_language_pie_chart,
            generate_module_overview,
            generate_sequence_diagram,
        )

        all_chunks = list(self._vector_store.get_all_chunks())
        project_name = repo_path.name.lower().replace("-", "_")

        simple_generators: dict[str, Callable[[], str | None]] = {
            "class": lambda: generate_class_diagram(all_chunks),
            "dependency": lambda: generate_dependency_graph(
                all_chunks,
                project_name=project_name,
                detect_circular=True,
                exclude_tests=True,
            ),
            "module": lambda: generate_module_overview(index_status),
            "language_pie": lambda: generate_language_pie_chart(index_status),
        }

        generator = simple_generators.get(diagram_type)
        if generator is not None:
            diagram = generator()
        elif diagram_type == "sequence":
            if not entry_point:
                raise ValidationError(
                    message="entry_point is required for sequence diagrams",
                    hint="Provide the name of the function to use as the sequence diagram entry point.",
                    field="entry_point",
                )
            extractor = CallGraphExtractor()
            combined_graph: dict[str, list[str]] = {}
            for file_info in index_status.files:
                fp = repo_path / file_info.path
                if fp.exists():
                    graph = extractor.extract_from_file(fp, repo_path)
                    for k, v in graph.items():
                        combined_graph.setdefault(k, []).extend(v)
            diagram = generate_sequence_diagram(combined_graph, entry_point=entry_point)
        else:
            diagram = None

        if diagram is None:
            return {
                "message": f"No {diagram_type} diagram could be generated (no relevant data found)",
            }

        return {
            "status": "success",
            "diagram_type": diagram_type,
            "mermaid": diagram,
        }

    async def generate_inheritance(
        self,
        index_status: Any,
        *,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Collect class inheritance hierarchy.

        Args:
            index_status: Loaded IndexStatus for the repository.
            search: Optional text filter on class name.
            offset: Pagination offset.
            limit: Maximum classes to return.

        Returns:
            Dict with classes list, pagination metadata, and mermaid diagram.
        """
        from local_deepwiki.generators.analysis.inheritance import (
            collect_class_hierarchy,
            generate_inheritance_diagram,
        )

        classes = await collect_class_hierarchy(index_status, self._vector_store)

        if not classes:
            return {
                "message": "No class hierarchies found in the codebase",
                "classes": [],
            }

        diagram = generate_inheritance_diagram(classes)
        class_list = list(classes.values())

        if search:
            search_lower = search.lower()
            class_list = [c for c in class_list if search_lower in c.name.lower()]

        total_classes = len(class_list)
        class_list = class_list[offset : offset + limit]

        return {
            "status": "success",
            "total_classes": total_classes,
            "returned": len(class_list),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total_classes,
            "classes": [
                {
                    "name": node.name,
                    "file_path": node.file_path,
                    "parents": node.parents,
                    "children": node.children,
                    "is_abstract": node.is_abstract,
                    "docstring": node.docstring,
                }
                for node in class_list
            ],
            "mermaid_diagram": diagram,
        }

    async def generate_call_graph(
        self,
        repo_path: Path,
        *,
        file_path: str | None = None,
        index_status: Any = None,
    ) -> dict[str, Any]:
        """Generate a call graph diagram.

        Args:
            repo_path: Resolved repository path.
            file_path: Optional file to scope the call graph to.
            index_status: Required when file_path is None (full repo scan).

        Returns:
            Dict with mermaid diagram and scope.
        """
        from local_deepwiki.core.path_utils import validate_file_in_repo
        from local_deepwiki.generators.analysis.callgraph import (
            CallGraphExtractor,
            generate_call_graph_diagram,
        )

        extractor = CallGraphExtractor()

        if file_path:
            target = validate_file_in_repo(repo_path, file_path)
            graph = extractor.extract_from_file(target, repo_path)
            diagram = generate_call_graph_diagram(graph, title=file_path)
        else:
            combined_graph: dict[str, list[str]] = {}
            if index_status is not None:
                for file_info in index_status.files:
                    fp = repo_path / file_info.path
                    if fp.exists():
                        graph = extractor.extract_from_file(fp, repo_path)
                        for k, v in graph.items():
                            combined_graph.setdefault(k, []).extend(v)
            diagram = generate_call_graph_diagram(combined_graph)

        if diagram is None:
            return {"message": "No call relationships found"}

        return {
            "status": "success",
            "mermaid": diagram,
            "scope": file_path or "full_repository",
        }

    async def generate_coverage(
        self,
        index_status: Any,
    ) -> dict[str, Any]:
        """Analyze documentation coverage.

        Args:
            index_status: Loaded IndexStatus for the repository.

        Returns:
            Dict with overall coverage stats and per-file gaps.
        """
        from local_deepwiki.generators.analysis.coverage import analyze_project_coverage

        stats, file_coverages = await analyze_project_coverage(
            index_status, self._vector_store
        )

        return {
            "status": "success",
            "overall": {
                "total_entities": stats.total_entities,
                "documented": stats.documented_entities,
                "undocumented": stats.total_entities - stats.documented_entities,
                "coverage_percent": round(stats.coverage_percent, 1),
            },
            "files": [
                {
                    "file_path": fc.file_path,
                    "coverage_percent": round(fc.stats.coverage_percent, 1),
                    "undocumented": fc.undocumented,
                }
                for fc in file_coverages
                if fc.undocumented  # Only include files with gaps
            ],
        }

    async def detect_stale_docs(
        self,
        repo_path: Path,
        wiki_path: Path,
        *,
        threshold_days: int = 30,
    ) -> dict[str, Any]:
        """Detect wiki pages that are stale relative to source files.

        Args:
            repo_path: Resolved repository path.
            wiki_path: Path to the wiki directory.
            threshold_days: Number of days before a page is considered stale.

        Returns:
            Dict with stale page list and counts.
        """
        from local_deepwiki.generators.analysis.stale_detection import analyze_staleness
        from local_deepwiki.generators.wiki.status import WikiStatusManager

        manager = WikiStatusManager(wiki_path)
        wiki_status = await manager.load_status()

        if wiki_status is None:
            return {
                "message": "No wiki generation status found. Run index_repository first.",
                "stale_pages": [],
            }

        report = analyze_staleness(repo_path, wiki_status, threshold_days)

        return {
            "status": "success",
            "total_pages": report.total_pages,
            "stale_count": report.stale_pages,
            "stale_pages": [
                {
                    "page_path": info.page_path,
                    "days_stale": info.days_stale,
                    "source_files": info.source_files,
                    "newest_source_date": info.newest_source_date.isoformat(),
                    "generated_at": info.generated_at.isoformat(),
                }
                for info in report.stale_info
            ],
        }

    async def generate_changelog(
        self,
        repo_path: Path,
        *,
        max_commits: int = 50,
    ) -> dict[str, Any]:
        """Generate a git changelog.

        Args:
            repo_path: Resolved repository path.
            max_commits: Maximum number of commits to include.

        Returns:
            Dict with changelog content or a message if no history.
        """
        from local_deepwiki.generators.changelog import generate_changelog_content

        content = await asyncio.to_thread(
            generate_changelog_content, repo_path, max_commits
        )

        if content is None:
            return {"message": "No git history found. Is this a git repository?"}

        return {
            "status": "success",
            "changelog": content,
        }

    async def detect_secrets(
        self,
        repo_path: Path,
        *,
        exclude_tests: bool = True,
    ) -> dict[str, Any]:
        """Scan repository for hardcoded secrets.

        Args:
            repo_path: Resolved repository path.
            exclude_tests: Whether to exclude test files from results.

        Returns:
            Dict with findings list and counts.
        """
        from local_deepwiki.core.path_utils import is_test_file
        from local_deepwiki.core.secret_detector import scan_repository_for_secrets

        findings_by_file = await asyncio.to_thread(
            scan_repository_for_secrets, repo_path
        )

        if exclude_tests:
            findings_by_file = {
                path: findings
                for path, findings in findings_by_file.items()
                if not is_test_file(path, check_filename=True)
            }

        total_findings = sum(len(findings) for findings in findings_by_file.values())

        return {
            "status": "success",
            "files_with_secrets": len(findings_by_file),
            "total_findings": total_findings,
            "exclude_tests": exclude_tests,
            "findings": [
                {
                    "file_path": file_path,
                    "is_test_file": is_test_file(file_path, check_filename=True),
                    "secrets": [
                        {
                            "type": f.secret_type.value,
                            "line": f.line_number,
                            "confidence": round(f.confidence, 2),
                            "recommendation": f.recommendation,
                        }
                        for f in findings
                    ],
                }
                for file_path, findings in findings_by_file.items()
            ],
        }

    async def generate_test_examples(
        self,
        repo_path: Path,
        entity_name: str,
        *,
        max_examples: int = 5,
    ) -> dict[str, Any]:
        """Extract test examples for a named entity.

        Args:
            repo_path: Resolved repository path.
            entity_name: Name of the function/class to find examples for.
            max_examples: Maximum number of examples to return.

        Returns:
            Dict with examples list.
        """
        from local_deepwiki.generators.examples.extractor import CodeExampleExtractor

        extractor = CodeExampleExtractor(self._vector_store, repo_path=repo_path)

        # Try function first, then class
        examples = await extractor.extract_examples_for_function(
            entity_name, max_examples=max_examples
        )
        if not examples:
            examples = await extractor.extract_examples_for_class(
                entity_name, max_examples=max_examples
            )

        if not examples:
            return {
                "message": f"No test examples found for '{entity_name}'",
                "examples": [],
            }

        return {
            "status": "success",
            "entity_name": entity_name,
            "total_examples": len(examples),
            "examples": [
                {
                    "source": e.source,
                    "code": e.code,
                    "description": e.description,
                    "test_file": e.test_file,
                    "language": e.language,
                }
                for e in examples
            ],
        }

    async def get_api_docs(
        self,
        repo_path: Path,
        file_path: str,
    ) -> dict[str, Any]:
        """Extract API documentation for a file.

        Args:
            repo_path: Resolved repository path.
            file_path: Relative path to the source file.

        Returns:
            Dict with API documentation or a message if none found.
        """
        from local_deepwiki.core.path_utils import validate_file_in_repo
        from local_deepwiki.generators.analysis.api_docs import get_file_api_docs

        target = validate_file_in_repo(repo_path, file_path)
        api_docs = await asyncio.to_thread(get_file_api_docs, target)

        if api_docs is None:
            return {
                "message": f"No API documentation could be extracted from '{file_path}'",
            }

        return {
            "status": "success",
            "file_path": file_path,
            "api_docs": api_docs,
        }

    async def list_indexed_repos(
        self,
        base_path: Path,
    ) -> dict[str, Any]:
        """List all indexed repositories under a base path.

        Args:
            base_path: Resolved base directory to scan.

        Returns:
            Dict with repos list.
        """
        from local_deepwiki.core.index_manager import IndexStatusManager
        from local_deepwiki.core.path_utils import find_deepwiki_dirs

        manager = IndexStatusManager()
        repos: list[dict[str, Any]] = []

        for deepwiki_dir in find_deepwiki_dirs(base_path):
            status = manager.load(deepwiki_dir)
            if status is not None:
                repos.append(
                    {
                        "repo_path": status.repo_path,
                        "wiki_path": str(deepwiki_dir),
                        "total_files": status.total_files,
                        "total_chunks": status.total_chunks,
                        "languages": status.languages,
                        "indexed_at": status.indexed_at,
                    }
                )

        return {
            "status": "success",
            "total_repos": len(repos),
            "repos": repos,
        }

    async def get_index_status(
        self,
        index_status: Any,
        wiki_path: Path,
    ) -> dict[str, Any]:
        """Get index status information.

        Args:
            index_status: Loaded IndexStatus for the repository.
            wiki_path: Path to the wiki directory.

        Returns:
            Dict with index metadata.
        """
        from datetime import datetime, timezone

        return {
            "status": "success",
            "repo_path": index_status.repo_path,
            "wiki_path": str(wiki_path),
            "indexed_at": index_status.indexed_at,
            "indexed_at_human": datetime.fromtimestamp(
                index_status.indexed_at, tz=timezone.utc
            ).isoformat(),
            "total_files": index_status.total_files,
            "total_chunks": index_status.total_chunks,
            "languages": index_status.languages,
            "schema_version": index_status.schema_version,
        }
