"""Language detection configuration and tree-sitter module mappings."""

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_kotlin
import tree_sitter_php
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_swift
import tree_sitter_typescript

from local_deepwiki.models import Language as LangEnum

# Language modules mapping
LANGUAGE_MODULES = {
    LangEnum.PYTHON: tree_sitter_python,
    LangEnum.JAVASCRIPT: tree_sitter_javascript,
    LangEnum.TYPESCRIPT: tree_sitter_typescript,
    LangEnum.TSX: tree_sitter_typescript,
    LangEnum.GO: tree_sitter_go,
    LangEnum.RUST: tree_sitter_rust,
    LangEnum.JAVA: tree_sitter_java,
    LangEnum.C: tree_sitter_c,
    LangEnum.CPP: tree_sitter_cpp,
    LangEnum.SWIFT: tree_sitter_swift,
    LangEnum.RUBY: tree_sitter_ruby,
    LangEnum.PHP: tree_sitter_php,
    LangEnum.KOTLIN: tree_sitter_kotlin,
    LangEnum.CSHARP: tree_sitter_c_sharp,
}

# File extension to language mapping
EXTENSION_MAP: dict[str, LangEnum] = {
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
