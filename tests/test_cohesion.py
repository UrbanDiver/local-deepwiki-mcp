"""Tests for cohesion analysis module."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_compute_lcom4_perfectly_cohesive():
    """All methods share the same fields -> LCOM4 = 1."""
    from local_deepwiki.generators.analysis.cohesion import compute_lcom4
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.models import Language as LangEnum

    source = """
class Cohesive:
    def __init__(self):
        self.x = 0
        self.y = 0
    def get_x(self):
        return self.x
    def get_y(self):
        return self.y
    def get_both(self):
        return self.x + self.y
"""
    parser = CodeParser()
    root = parser.parse_source(source, LangEnum.PYTHON)
    from local_deepwiki.core.parser.ast_utils import find_nodes_by_type
    from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES

    classes = find_nodes_by_type(root, CLASS_NODE_TYPES[LangEnum.PYTHON])
    assert len(classes) == 1
    result = compute_lcom4(classes[0], source.encode(), LangEnum.PYTHON)
    assert result == 1


def test_compute_lcom4_splittable():
    """Two groups of methods access disjoint fields -> LCOM4 = 2."""
    from local_deepwiki.generators.analysis.cohesion import compute_lcom4
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.models import Language as LangEnum

    source = """
class Splittable:
    def set_a(self):
        self.a = 1
    def get_a(self):
        return self.a
    def set_b(self):
        self.b = 2
    def get_b(self):
        return self.b
"""
    parser = CodeParser()
    root = parser.parse_source(source, LangEnum.PYTHON)
    from local_deepwiki.core.parser.ast_utils import find_nodes_by_type
    from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES

    classes = find_nodes_by_type(root, CLASS_NODE_TYPES[LangEnum.PYTHON])
    result = compute_lcom4(classes[0], source.encode(), LangEnum.PYTHON)
    assert result == 2


def test_compute_lcom4_no_methods():
    """Class with no methods -> LCOM4 = 0."""
    from local_deepwiki.generators.analysis.cohesion import compute_lcom4
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.models import Language as LangEnum

    source = """
class Empty:
    pass
"""
    parser = CodeParser()
    root = parser.parse_source(source, LangEnum.PYTHON)
    from local_deepwiki.core.parser.ast_utils import find_nodes_by_type
    from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES

    classes = find_nodes_by_type(root, CLASS_NODE_TYPES[LangEnum.PYTHON])
    result = compute_lcom4(classes[0], source.encode(), LangEnum.PYTHON)
    assert result == 0


def test_compute_lcom4_single_method():
    """Class with one method -> LCOM4 = 1."""
    from local_deepwiki.generators.analysis.cohesion import compute_lcom4
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.models import Language as LangEnum

    source = """
class Single:
    def do_thing(self):
        self.x = 1
"""
    parser = CodeParser()
    root = parser.parse_source(source, LangEnum.PYTHON)
    from local_deepwiki.core.parser.ast_utils import find_nodes_by_type
    from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES

    classes = find_nodes_by_type(root, CLASS_NODE_TYPES[LangEnum.PYTHON])
    result = compute_lcom4(classes[0], source.encode(), LangEnum.PYTHON)
    assert result == 1


def test_compute_lcom4_method_with_no_fields():
    """Methods accessing no fields each form their own component."""
    from local_deepwiki.generators.analysis.cohesion import compute_lcom4
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.models import Language as LangEnum

    source = """
class NoFields:
    def method_a(self):
        return 1
    def method_b(self):
        return 2
"""
    parser = CodeParser()
    root = parser.parse_source(source, LangEnum.PYTHON)
    from local_deepwiki.core.parser.ast_utils import find_nodes_by_type
    from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES

    classes = find_nodes_by_type(root, CLASS_NODE_TYPES[LangEnum.PYTHON])
    result = compute_lcom4(classes[0], source.encode(), LangEnum.PYTHON)
    # Two methods with no shared fields -> 2 components
    assert result == 2


def test_analyze_class_cohesion(tmp_path):
    from local_deepwiki.generators.analysis.cohesion import analyze_class_cohesion

    _write_py(
        tmp_path / "src" / "mod.py",
        """
class Foo:
    def set_x(self):
        self.x = 1
    def get_x(self):
        return self.x
    def set_y(self):
        self.y = 2
    def get_y(self):
        return self.y
""",
    )
    results = analyze_class_cohesion(tmp_path)
    assert len(results) >= 1
    assert results[0]["class_name"] == "Foo"
    assert results[0]["lcom4"] == 2
    assert results[0]["method_count"] == 4
    assert results[0]["field_count"] == 2


def test_analyze_class_cohesion_sorted_descending(tmp_path):
    """Results should be sorted by LCOM4 descending."""
    from local_deepwiki.generators.analysis.cohesion import analyze_class_cohesion

    _write_py(
        tmp_path / "src" / "mod.py",
        """
class Low:
    def __init__(self):
        self.x = 0
    def get_x(self):
        return self.x

class High:
    def set_a(self):
        self.a = 1
    def set_b(self):
        self.b = 2
    def set_c(self):
        self.c = 3
""",
    )
    results = analyze_class_cohesion(tmp_path)
    assert len(results) == 2
    assert results[0]["class_name"] == "High"
    assert results[0]["lcom4"] == 3
    assert results[1]["class_name"] == "Low"
    assert results[1]["lcom4"] == 1


def test_analyze_class_cohesion_excludes_tests(tmp_path):
    """Test files should be excluded when exclude_tests=True."""
    from local_deepwiki.generators.analysis.cohesion import analyze_class_cohesion

    _write_py(
        tmp_path / "src" / "mod.py",
        """
class Real:
    def do(self):
        self.x = 1
""",
    )
    _write_py(
        tmp_path / "tests" / "test_mod.py",
        """
class TestFake:
    def test_do(self):
        self.y = 2
""",
    )
    results = analyze_class_cohesion(tmp_path, exclude_tests=True)
    names = [r["class_name"] for r in results]
    assert "Real" in names
    assert "TestFake" not in names


def test_compute_module_cohesion(tmp_path):
    from local_deepwiki.generators.analysis.cohesion import compute_module_cohesion

    pkg = tmp_path / "src" / "mypkg"
    _write_py(pkg / "__init__.py", "")
    _write_py(pkg / "a.py", "from mypkg.b import helper\nimport os\n")
    _write_py(pkg / "b.py", "from mypkg.a import stuff\n")
    results = compute_module_cohesion(tmp_path)
    assert len(results) >= 1
    # mypkg has 2 internal imports out of 3 total -> ratio ~0.67
    mypkg = next((m for m in results if "mypkg" in m["module"]), None)
    assert mypkg is not None
    assert mypkg["cohesion_ratio"] > 0.5


def test_compute_module_cohesion_no_internal(tmp_path):
    """Module with only external imports has cohesion_ratio 0."""
    from local_deepwiki.generators.analysis.cohesion import compute_module_cohesion

    pkg = tmp_path / "src" / "mypkg"
    _write_py(pkg / "__init__.py", "")
    _write_py(pkg / "a.py", "import os\nimport sys\n")
    results = compute_module_cohesion(tmp_path)
    mypkg = next((m for m in results if "mypkg" in m["module"]), None)
    assert mypkg is not None
    assert mypkg["cohesion_ratio"] == 0.0


def test_compute_module_cohesion_sorted_ascending(tmp_path):
    """Results should be sorted by cohesion_ratio ascending."""
    from local_deepwiki.generators.analysis.cohesion import compute_module_cohesion

    pkg_a = tmp_path / "src" / "alpha"
    _write_py(pkg_a / "__init__.py", "")
    _write_py(pkg_a / "mod.py", "import os\n")  # 0 internal / 1 total = 0.0

    pkg_b = tmp_path / "src" / "beta"
    _write_py(pkg_b / "__init__.py", "")
    _write_py(
        pkg_b / "mod.py", "from beta.other import x\n"
    )  # 1 internal / 1 total = 1.0
    _write_py(pkg_b / "other.py", "x = 1\n")

    results = compute_module_cohesion(tmp_path)
    # alpha (ratio 0) should appear before beta (ratio 1)
    alpha_idx = next(i for i, m in enumerate(results) if "alpha" in m["module"])
    beta_idx = next(i for i, m in enumerate(results) if "beta" in m["module"])
    assert alpha_idx < beta_idx


def test_analyze_cohesion_orchestrator(tmp_path):
    from local_deepwiki.generators.analysis.cohesion import analyze_cohesion

    _write_py(
        tmp_path / "src" / "mod.py",
        """
class Simple:
    def do(self):
        self.x = 1
""",
    )
    result = analyze_cohesion(tmp_path)
    assert result["status"] == "success"
    assert "class_cohesion" in result
    assert "module_cohesion" in result
    assert "stats" in result
    assert "total_classes" in result["stats"]
    assert "avg_lcom" in result["stats"]
    assert "classes_with_lcom_gt_2" in result["stats"]
    assert "total_modules" in result["stats"]
    assert "low_cohesion_modules" in result["stats"]


def test_analyze_cohesion_top_n(tmp_path):
    """top_n limits the class_cohesion list."""
    from local_deepwiki.generators.analysis.cohesion import analyze_cohesion

    # Create 5 classes
    classes = "\n".join(
        f"""
class C{i}:
    def m{i}(self):
        self.f{i} = {i}
"""
        for i in range(5)
    )
    _write_py(tmp_path / "src" / "many.py", classes)
    result = analyze_cohesion(tmp_path, top_n=3)
    assert len(result["class_cohesion"]) <= 3
    assert result["stats"]["total_classes"] == 5
