"""Protocol interfaces for generator components.

Defines structural typing contracts (``typing.Protocol``) for the
generators package so that consumers can depend on the interface rather
than the concrete generator class.  This raises the *abstractness*
metric for the ``generators`` package and improves the overall coupling
score.

All protocols are ``@runtime_checkable`` so that guards and diagnostic
code can use ``isinstance`` checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from local_deepwiki.core.index_manager import IndexStatus


@runtime_checkable
class AnalysisGeneratorProtocol(Protocol):
    """Protocol defining the interface for dependency-graph analysis generators.

    Components that generate module or file dependency graphs should
    accept this Protocol so that test stubs can be substituted without
    subclassing the concrete ``DependencyGraphGenerator``.
    """

    async def generate_module_graph(
        self,
        index_status: IndexStatus,
        *,
        show_external: bool = False,
        max_external: int = 10,
        exclude_tests: bool = True,
        wiki_base_path: str = "",
    ) -> str:
        """Generate Mermaid graph of module dependencies.

        Args:
            index_status: Index status with file information.
            show_external: Whether to include external dependencies.
            max_external: Maximum external dependencies to show.
            exclude_tests: Whether to exclude test modules.
            wiki_base_path: Base path for wiki links.

        Returns:
            Mermaid diagram string.
        """
        ...

    async def generate_file_graph(
        self,
        index_status: IndexStatus,
        module_path: str,
        exclude_tests: bool = True,
    ) -> str:
        """Generate Mermaid graph for files within a module.

        Args:
            index_status: Index status with file information.
            module_path: Module/directory path to show files for.
            exclude_tests: Whether to exclude test files.

        Returns:
            Mermaid diagram string.
        """
        ...


@runtime_checkable
class DiagramGeneratorProtocol(Protocol):
    """Protocol defining the interface for diagram generators.

    Any callable that accepts code chunks and returns a Mermaid diagram
    string satisfies this contract.  This covers the family of
    ``generate_class_diagram``, ``generate_dependency_graph``, etc.
    functions in the ``generators.diagrams`` subpackage.
    """

    def __call__(self, chunks: list, **kwargs: object) -> str | None:
        """Generate a Mermaid diagram from code chunks.

        Args:
            chunks: List of CodeChunk objects to analyze.
            **kwargs: Generator-specific options.

        Returns:
            Mermaid diagram string, or None if the input is insufficient.
        """
        ...
