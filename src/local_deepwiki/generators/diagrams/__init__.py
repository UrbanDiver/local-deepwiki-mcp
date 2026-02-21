"""Enhanced Mermaid diagram generation for code visualization."""

from local_deepwiki.generators.diagrams._utils import (
    ClassInfo,
    _MERMAID_SANITIZE_TABLE,
    _unwrap_chunk,
    sanitize_mermaid_name,
)
from local_deepwiki.generators.diagrams.class_diagram import (
    _build_class_lines,
    _build_inheritance_lines,
    _collect_class_from_chunk,
    _collect_method_from_chunk,
    _extract_class_attributes,
    _extract_method_signature,
    _extract_methods_from_class_content,
    _package_from_file_path,
    generate_class_diagram,
)
from local_deepwiki.generators.diagrams.dependency_diagram import (
    _DependencyData,
    _add_circular_styling,
    _add_edges,
    _add_external_subgraph,
    _add_subgraphs,
    _build_internal_deps,
    _build_node_ids,
    _collect_dependencies,
    _find_circular_dependencies,
    _group_modules,
    _is_test_module,
    _module_to_wiki_path,
    _parse_external_import,
    _parse_import_line,
    _path_to_module,
    generate_dependency_graph,
)
from local_deepwiki.generators.diagrams.language_pie import (
    generate_language_pie_chart,
)
from local_deepwiki.generators.diagrams.module_diagram import (
    generate_module_overview,
)
from local_deepwiki.generators.diagrams.sequence_diagram import (
    generate_deep_research_sequence,
    generate_indexing_sequence,
    generate_sequence_diagram,
    generate_wiki_generation_sequence,
    generate_workflow_sequences,
)

__all__ = [
    # _utils
    "ClassInfo",
    "_MERMAID_SANITIZE_TABLE",
    "_unwrap_chunk",
    "sanitize_mermaid_name",
    # class_diagram
    "_build_class_lines",
    "_build_inheritance_lines",
    "_collect_class_from_chunk",
    "_collect_method_from_chunk",
    "_extract_class_attributes",
    "_extract_method_signature",
    "_extract_methods_from_class_content",
    "_package_from_file_path",
    "generate_class_diagram",
    # dependency_diagram
    "_DependencyData",
    "_add_circular_styling",
    "_add_edges",
    "_add_external_subgraph",
    "_add_subgraphs",
    "_build_internal_deps",
    "_build_node_ids",
    "_collect_dependencies",
    "_find_circular_dependencies",
    "_group_modules",
    "_is_test_module",
    "_module_to_wiki_path",
    "_parse_external_import",
    "_parse_import_line",
    "_path_to_module",
    "generate_dependency_graph",
    # language_pie
    "generate_language_pie_chart",
    # module_diagram
    "generate_module_overview",
    # sequence_diagram
    "generate_deep_research_sequence",
    "generate_indexing_sequence",
    "generate_sequence_diagram",
    "generate_wiki_generation_sequence",
    "generate_workflow_sequences",
]
