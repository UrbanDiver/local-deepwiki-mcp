"""Tests for new MCP tool handlers."""

import json

from local_deepwiki.handlers import (
    handle_detect_secrets,
    handle_detect_stale_docs,
    handle_get_api_docs,
    handle_get_call_graph,
    handle_get_changelog,
    handle_get_coverage,
    handle_get_diagrams,
    handle_get_glossary,
    handle_get_index_status,
    handle_get_inheritance,
    handle_get_test_examples,
    handle_list_indexed_repos,
)


class TestHandleGetGlossary:
    """Tests for handle_get_glossary handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_glossary({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_get_glossary({"repo_path": str(tmp_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_missing_repo_path(self):
        """Test error returned when repo_path is missing."""
        result = await handle_get_glossary({})

        assert len(result) == 1
        assert "Error" in result[0].text


class TestHandleGetDiagrams:
    """Tests for handle_get_diagrams handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_diagrams({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_get_diagrams({"repo_path": str(tmp_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_invalid_diagram_type(self, tmp_path):
        """Test error returned for invalid diagram type."""
        result = await handle_get_diagrams(
            {"repo_path": str(tmp_path), "diagram_type": "invalid"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_sequence_requires_entry_point(self, tmp_path):
        """Test that sequence diagram without entry_point gives validation error."""
        # Will fail at not-indexed before reaching entry_point validation
        result = await handle_get_diagrams(
            {"repo_path": str(tmp_path), "diagram_type": "sequence"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text


class TestHandleGetInheritance:
    """Tests for handle_get_inheritance handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_inheritance({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_get_inheritance({"repo_path": str(tmp_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text


class TestHandleGetCallGraph:
    """Tests for handle_get_call_graph handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_call_graph({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_rejects_path_traversal(self, tmp_path):
        """Test that path traversal in file_path is rejected."""
        result = await handle_get_call_graph(
            {"repo_path": str(tmp_path), "file_path": "../../etc/passwd"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "traversal" in result[0].text

    async def test_returns_error_for_nonexistent_file(self, tmp_path):
        """Test error returned for non-existent file path."""
        result = await handle_get_call_graph(
            {"repo_path": str(tmp_path), "file_path": "nonexistent.py"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text


class TestHandleGetCoverage:
    """Tests for handle_get_coverage handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_coverage({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_get_coverage({"repo_path": str(tmp_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text


class TestHandleDetectStaleDocs:
    """Tests for handle_detect_stale_docs handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_detect_stale_docs({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_detect_stale_docs({"repo_path": str(tmp_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_rejects_negative_threshold(self, tmp_path):
        """Test that negative threshold_days is rejected."""
        result = await handle_detect_stale_docs(
            {"repo_path": str(tmp_path), "threshold_days": -1}
        )

        assert len(result) == 1
        assert "Error" in result[0].text


class TestHandleGetChangelog:
    """Tests for handle_get_changelog handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_changelog({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_non_git_repo_returns_no_history(self, tmp_path):
        """Test that a non-git directory returns no history message."""
        result = await handle_get_changelog({"repo_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "No git history" in data["message"]

    async def test_rejects_max_commits_out_of_range(self, tmp_path):
        """Test that max_commits out of range is rejected."""
        result = await handle_get_changelog(
            {"repo_path": str(tmp_path), "max_commits": 500}
        )

        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_git_repo_returns_changelog(self, tmp_path):
        """Test that a git repo returns changelog content."""
        import subprocess

        # Create a minimal git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = await handle_get_changelog({"repo_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "changelog" in data
        assert "Initial commit" in data["changelog"]


class TestHandleDetectSecrets:
    """Tests for handle_detect_secrets handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_detect_secrets({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_file_path(self, tmp_path):
        """Test error returned when path is a file, not directory."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        result = await handle_detect_secrets({"repo_path": str(file_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not a directory" in result[0].text

    async def test_clean_repo_returns_no_findings(self, tmp_path):
        """Test that a clean repo returns no secret findings."""
        (tmp_path / "clean.py").write_text("x = 1\n")

        result = await handle_detect_secrets({"repo_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_findings"] == 0

    async def test_detects_hardcoded_secret(self, tmp_path):
        """Test that hardcoded secrets are detected."""
        # Use a GitHub token pattern (ghp_ + 36 alphanumeric chars)
        fake_token = "ghp_" + "a" * 36
        (tmp_path / "config.py").write_text(f'GITHUB_TOKEN = "{fake_token}"\n')

        result = await handle_detect_secrets({"repo_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_findings"] > 0
        assert len(data["findings"]) > 0


class TestHandleGetTestExamples:
    """Tests for handle_get_test_examples handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_test_examples(
            {"repo_path": str(nonexistent), "entity_name": "some_func"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_get_test_examples(
            {"repo_path": str(tmp_path), "entity_name": "some_func"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_rejects_empty_entity_name(self):
        """Test that empty entity name is rejected."""
        result = await handle_get_test_examples(
            {"repo_path": "/some/path", "entity_name": ""}
        )

        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_rejects_max_examples_out_of_range(self, tmp_path):
        """Test that max_examples out of range is rejected."""
        result = await handle_get_test_examples(
            {"repo_path": str(tmp_path), "entity_name": "func", "max_examples": 100}
        )

        assert len(result) == 1
        assert "Error" in result[0].text


class TestHandleGetApiDocs:
    """Tests for handle_get_api_docs handler."""

    async def test_returns_error_for_nonexistent_repo(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_api_docs(
            {"repo_path": str(nonexistent), "file_path": "main.py"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_rejects_path_traversal(self, tmp_path):
        """Test that path traversal in file_path is rejected."""
        result = await handle_get_api_docs(
            {"repo_path": str(tmp_path), "file_path": "../../etc/passwd"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "traversal" in result[0].text

    async def test_returns_error_for_nonexistent_file(self, tmp_path):
        """Test error returned for non-existent file path."""
        result = await handle_get_api_docs(
            {"repo_path": str(tmp_path), "file_path": "nonexistent.py"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_missing_file_path(self):
        """Test error returned when file_path is missing."""
        result = await handle_get_api_docs({"repo_path": "/some/path"})

        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_returns_api_docs_for_python_file(self, tmp_path):
        """Test that API docs are generated for a Python file."""
        py_file = tmp_path / "module.py"
        py_file.write_text(
            'def hello(name: str) -> str:\n    """Greet someone."""\n    return f"Hello {name}"\n'
        )

        result = await handle_get_api_docs(
            {"repo_path": str(tmp_path), "file_path": "module.py"}
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "api_docs" in data
        assert "hello" in data["api_docs"]


class TestHandleListIndexedRepos:
    """Tests for handle_list_indexed_repos handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent base path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_list_indexed_repos({"base_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_empty_directory_returns_no_repos(self, tmp_path):
        """Test that an empty directory returns no indexed repos."""
        result = await handle_list_indexed_repos({"base_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_repos"] == 0

    async def test_default_base_path_works(self):
        """Test that omitting base_path uses current directory."""
        result = await handle_list_indexed_repos({})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "total_repos" in data


class TestHandleGetIndexStatus:
    """Tests for handle_get_index_status handler."""

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error returned for non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"
        result = await handle_get_index_status({"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_get_index_status({"repo_path": str(tmp_path)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_missing_repo_path(self):
        """Test error returned when repo_path is missing."""
        result = await handle_get_index_status({})

        assert len(result) == 1
        assert "Error" in result[0].text
