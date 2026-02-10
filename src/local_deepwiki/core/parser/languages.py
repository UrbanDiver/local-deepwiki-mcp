"""Language detection configuration and tree-sitter module mappings."""

import importlib
import logging
from types import ModuleType

from local_deepwiki.models import Language as LangEnum

_logger = logging.getLogger(__name__)

# Grammar package name -> list of language enums it supports
_GRAMMAR_CONFIG: list[tuple[str, list[LangEnum]]] = [
    ("tree_sitter_python", [LangEnum.PYTHON]),
    ("tree_sitter_javascript", [LangEnum.JAVASCRIPT]),
    ("tree_sitter_typescript", [LangEnum.TYPESCRIPT, LangEnum.TSX]),
    ("tree_sitter_go", [LangEnum.GO]),
    ("tree_sitter_rust", [LangEnum.RUST]),
    ("tree_sitter_java", [LangEnum.JAVA]),
    ("tree_sitter_c", [LangEnum.C]),
    ("tree_sitter_cpp", [LangEnum.CPP]),
    ("tree_sitter_swift", [LangEnum.SWIFT]),
    ("tree_sitter_ruby", [LangEnum.RUBY]),
    ("tree_sitter_php", [LangEnum.PHP]),
    ("tree_sitter_kotlin", [LangEnum.KOTLIN]),
    ("tree_sitter_c_sharp", [LangEnum.CSHARP]),
]

# Build LANGUAGE_MODULES dynamically, skipping grammars that aren't installed
LANGUAGE_MODULES: dict[LangEnum, ModuleType] = {}

for _pkg_name, _langs in _GRAMMAR_CONFIG:
    try:
        _mod = importlib.import_module(_pkg_name)
        for _lang in _langs:
            LANGUAGE_MODULES[_lang] = _mod
    except ImportError:
        _names = ", ".join(lang.value for lang in _langs)
        _logger.warning(
            "Tree-sitter grammar '%s' not installed — "
            "%s files will be skipped. "
            "Install with: uv pip install %s",
            _pkg_name,
            _names,
            _pkg_name.replace("_", "-"),
        )

# Full extension map (static reference, filtered below)
_ALL_EXTENSIONS: dict[str, LangEnum] = {
    ".py": LangEnum.PYTHON,
    ".pyi": LangEnum.PYTHON,
    ".js": LangEnum.JAVASCRIPT,
    ".jsx": LangEnum.JAVASCRIPT,
    ".mjs": LangEnum.JAVASCRIPT,
    ".ts": LangEnum.TYPESCRIPT,
    ".tsx": LangEnum.TSX,
    ".go": LangEnum.GO,
    ".rs": LangEnum.RUST,
    ".java": LangEnum.JAVA,
    ".c": LangEnum.C,
    ".h": LangEnum.C,
    ".cpp": LangEnum.CPP,
    ".cc": LangEnum.CPP,
    ".cxx": LangEnum.CPP,
    ".hpp": LangEnum.CPP,
    ".hxx": LangEnum.CPP,
    ".swift": LangEnum.SWIFT,
    ".rb": LangEnum.RUBY,
    ".rake": LangEnum.RUBY,
    ".gemspec": LangEnum.RUBY,
    ".php": LangEnum.PHP,
    ".phtml": LangEnum.PHP,
    ".kt": LangEnum.KOTLIN,
    ".kts": LangEnum.KOTLIN,
    ".cs": LangEnum.CSHARP,
}

# Only map extensions for languages with available grammars
EXTENSION_MAP: dict[str, LangEnum] = {
    ext: lang for ext, lang in _ALL_EXTENSIONS.items() if lang in LANGUAGE_MODULES
}
