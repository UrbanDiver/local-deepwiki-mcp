"""Tests for shared source filtering utilities."""

from __future__ import annotations

from pathlib import Path

from local_deepwiki.generators.analysis.source_filter import (
    SKIP_DIRS,
    TEST_DIR_NAMES,
    is_test_file,
    iter_python_files,
    iter_source_files,
    should_skip_dir,
)


# ---------------------------------------------------------------------------
# is_test_file
# ---------------------------------------------------------------------------


def test_is_test_file_by_prefix():
    assert is_test_file(Path("test_foo.py"))


def test_is_test_file_by_suffix():
    assert is_test_file(Path("foo_test.py"))


def test_is_test_file_conftest():
    assert is_test_file(Path("conftest.py"))


def test_is_test_file_in_tests_dir():
    assert is_test_file(Path("tests/helpers.py"))


def test_is_test_file_in_test_dir():
    assert is_test_file(Path("test/helpers.py"))


def test_is_test_file_in_dunder_tests_dir():
    assert is_test_file(Path("__tests__/utils.js"))


def test_is_test_file_in_spec_dir():
    assert is_test_file(Path("spec/user_spec.rb"))


def test_is_test_file_nested_in_tests_dir():
    assert is_test_file(Path("src/core/tests/test_parser.py"))


def test_not_test_file_regular_source():
    assert not is_test_file(Path("src/server.py"))


def test_not_test_file_nested_regular():
    assert not is_test_file(Path("src/core/indexer.py"))


def test_not_test_file_similar_name():
    # "attest.py" should not match — only exact name "conftest.py"
    assert not is_test_file(Path("attest.py"))


def test_not_test_file_no_test_prefix():
    assert not is_test_file(Path("fastest.py"))


# ---------------------------------------------------------------------------
# should_skip_dir
# ---------------------------------------------------------------------------


def test_should_skip_dir_hidden_git():
    assert should_skip_dir(".git")


def test_should_skip_dir_hidden_venv():
    assert should_skip_dir(".venv")


def test_should_skip_dir_hidden_arbitrary():
    assert should_skip_dir(".hidden")


def test_should_skip_dir_pycache():
    assert should_skip_dir("__pycache__")


def test_should_skip_dir_node_modules():
    assert should_skip_dir("node_modules")


def test_should_skip_dir_coverage_html():
    assert should_skip_dir("coverage_html")


def test_should_skip_dir_coverage_openai():
    assert should_skip_dir("coverage_openai_embeddings")


def test_should_skip_dir_htmlcov():
    assert should_skip_dir("htmlcov")


def test_should_skip_dir_venv():
    assert should_skip_dir("venv")


def test_should_skip_dir_tox():
    assert should_skip_dir(".tox")


def test_should_skip_dir_mypy_cache():
    assert should_skip_dir(".mypy_cache")


def test_should_skip_dir_pytest_cache():
    assert should_skip_dir(".pytest_cache")


def test_should_skip_dir_eggs():
    assert should_skip_dir(".eggs")


def test_should_skip_dir_dist():
    assert should_skip_dir("dist")


def test_should_skip_dir_build():
    assert should_skip_dir("build")


def test_should_not_skip_src():
    assert not should_skip_dir("src")


def test_should_not_skip_lib():
    assert not should_skip_dir("lib")


def test_should_not_skip_generators():
    assert not should_skip_dir("generators")


def test_should_not_skip_core():
    assert not should_skip_dir("core")


# ---------------------------------------------------------------------------
# iter_source_files
# ---------------------------------------------------------------------------


def test_iter_source_files_excludes_tests_by_default(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("x = 1")

    results = iter_source_files(
        tmp_path, exclude_tests=True, extensions=frozenset({".py"})
    )
    rel_paths = [r[1] for r in results]
    assert Path("src/main.py") in rel_paths
    assert not any("test" in str(p) for p in rel_paths)


def test_iter_source_files_includes_tests_when_flag_false(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("x = 1")

    results = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    rel_paths = [str(r[1]) for r in results]
    assert any("test" in p for p in rel_paths)
    assert any("main.py" in p for p in rel_paths)


def test_iter_source_files_skips_coverage_html(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "coverage_html").mkdir()
    (tmp_path / "coverage_html" / "report.js").write_text("x = 1")

    results = iter_source_files(tmp_path, exclude_tests=False)
    rel_paths = [str(r[1]) for r in results]
    assert not any("coverage_html" in p for p in rel_paths)


def test_iter_source_files_skips_venv(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "lib.py").write_text("x = 1")

    results = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    rel_paths = [str(r[1]) for r in results]
    assert not any("venv" in p for p in rel_paths)
    assert any("main.py" in p for p in rel_paths)


def test_iter_source_files_skips_hidden_dirs(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.py").write_text("x = 1")

    results = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    rel_paths = [str(r[1]) for r in results]
    assert not any(".hidden" in p for p in rel_paths)


def test_iter_source_files_extension_filtering(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "script.js").write_text("x = 1")

    py_only = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    assert all(r[1].suffix == ".py" for r in py_only)
    assert len(py_only) == 1


def test_iter_source_files_returns_sorted(tmp_path):
    (tmp_path / "z_file.py").write_text("x = 1")
    (tmp_path / "a_file.py").write_text("x = 1")
    (tmp_path / "m_file.py").write_text("x = 1")

    results = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    rel_paths = [r[1] for r in results]
    assert rel_paths == sorted(rel_paths)


def test_iter_source_files_returns_absolute_and_relative(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    results = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    assert len(results) == 1
    full_path, rel_path = results[0]
    assert full_path.is_absolute()
    assert not rel_path.is_absolute()
    assert full_path == tmp_path / rel_path


def test_iter_source_files_empty_dir(tmp_path):
    results = iter_source_files(tmp_path)
    assert results == []


def test_iter_source_files_skips_pycache(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"fake")

    results = iter_source_files(
        tmp_path, exclude_tests=False, extensions=frozenset({".py"})
    )
    rel_paths = [str(r[1]) for r in results]
    assert not any("__pycache__" in p for p in rel_paths)


# ---------------------------------------------------------------------------
# iter_python_files
# ---------------------------------------------------------------------------


def test_iter_python_files_only_py(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "script.js").write_text("x = 1")
    (tmp_path / "styles.css").write_text("x = 1")

    results = iter_python_files(tmp_path)
    assert len(results) == 1
    assert results[0][1] == Path("main.py")


def test_iter_python_files_includes_tests_by_default(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "test_main.py").write_text("x = 1")

    results = iter_python_files(tmp_path)
    rel_paths = [r[1] for r in results]
    assert Path("main.py") in rel_paths
    assert Path("test_main.py") in rel_paths


def test_iter_python_files_can_exclude_tests(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "test_main.py").write_text("x = 1")

    results = iter_python_files(tmp_path, exclude_tests=True)
    rel_paths = [r[1] for r in results]
    assert Path("main.py") in rel_paths
    assert Path("test_main.py") not in rel_paths


# ---------------------------------------------------------------------------
# SKIP_DIRS and TEST_DIR_NAMES constants
# ---------------------------------------------------------------------------


def test_skip_dirs_includes_venv():
    assert "venv" in SKIP_DIRS


def test_skip_dirs_includes_dot_venv():
    assert ".venv" in SKIP_DIRS


def test_skip_dirs_includes_node_modules():
    assert "node_modules" in SKIP_DIRS


def test_skip_dirs_includes_pycache():
    assert "__pycache__" in SKIP_DIRS


def test_skip_dirs_includes_coverage_html():
    assert "coverage_html" in SKIP_DIRS


def test_skip_dirs_includes_htmlcov():
    assert "htmlcov" in SKIP_DIRS


def test_test_dir_names_includes_tests():
    assert "tests" in TEST_DIR_NAMES


def test_test_dir_names_includes_spec():
    assert "spec" in TEST_DIR_NAMES
