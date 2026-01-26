"""Tests for the structured error system."""

import pytest

from local_deepwiki.errors import (
    DeepWikiError,
    EnvironmentError,
    ExportError,
    IndexingError,
    ProviderError,
    ResearchError,
    ValidationError,
    environment_error,
    export_error,
    format_error_response,
    indexing_error,
    map_exception_to_deepwiki_error,
    not_indexed_error,
    path_not_found_error,
    provider_error,
    research_error,
    validation_error,
)


class TestDeepWikiError:
    """Tests for the base DeepWikiError class."""

    def test_basic_error_message(self):
        """Test that basic error message is formatted correctly."""
        error = DeepWikiError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.hint is None
        assert error.context == {}

    def test_error_with_hint(self):
        """Test that error with hint is formatted correctly."""
        error = DeepWikiError("Something went wrong", hint="Try again later")
        assert "Something went wrong" in str(error)
        assert "Hint: Try again later" in str(error)

    def test_error_with_context(self):
        """Test that error context is stored."""
        error = DeepWikiError(
            "Something went wrong",
            context={"file": "test.py", "line": 42},
        )
        assert error.context["file"] == "test.py"
        assert error.context["line"] == 42

    def test_repr_includes_all_fields(self):
        """Test that repr includes all fields."""
        error = DeepWikiError(
            "message",
            hint="hint",
            context={"key": "value"},
        )
        repr_str = repr(error)
        assert "DeepWikiError" in repr_str
        assert "message" in repr_str
        assert "hint" in repr_str
        assert "context" in repr_str

    def test_to_dict(self):
        """Test conversion to dictionary."""
        error = DeepWikiError(
            "message",
            hint="hint",
            context={"key": "value"},
        )
        d = error.to_dict()
        assert d["error_type"] == "DeepWikiError"
        assert d["message"] == "message"
        assert d["hint"] == "hint"
        assert d["context"] == {"key": "value"}

    def test_inheritance_from_exception(self):
        """Test that DeepWikiError is a proper Exception."""
        error = DeepWikiError("test")
        assert isinstance(error, Exception)

        # Can be raised and caught
        with pytest.raises(DeepWikiError):
            raise error

        # Can be caught as generic Exception
        with pytest.raises(Exception):
            raise DeepWikiError("test")


class TestValidationError:
    """Tests for ValidationError."""

    def test_basic_validation_error(self):
        """Test basic validation error."""
        error = ValidationError("Invalid input")
        assert "Invalid input" in str(error)
        assert error.field is None
        assert error.value is None

    def test_validation_error_with_field(self):
        """Test validation error with field info."""
        error = ValidationError(
            "Invalid repository path",
            hint="Check the path",
            field="repo_path",
            value="/nonexistent/path",
        )
        assert error.field == "repo_path"
        assert error.value == "/nonexistent/path"
        assert error.context["field"] == "repo_path"
        assert error.context["value"] == "/nonexistent/path"

    def test_validation_error_inherits_from_deepwiki_error(self):
        """Test that ValidationError inherits from DeepWikiError."""
        error = ValidationError("test")
        assert isinstance(error, DeepWikiError)


class TestEnvironmentError:
    """Tests for EnvironmentError."""

    def test_basic_environment_error(self):
        """Test basic environment error."""
        error = EnvironmentError("Missing dependency")
        assert "Missing dependency" in str(error)
        assert error.missing_component is None

    def test_environment_error_with_component(self):
        """Test environment error with component info."""
        error = EnvironmentError(
            "WeasyPrint not installed",
            hint="pip install weasyprint",
            missing_component="weasyprint",
        )
        assert error.missing_component == "weasyprint"
        assert error.context["missing_component"] == "weasyprint"


class TestProviderError:
    """Tests for ProviderError."""

    def test_basic_provider_error(self):
        """Test basic provider error."""
        error = ProviderError("API call failed")
        assert "API call failed" in str(error)
        assert error.provider_name is None
        assert error.original_error is None

    def test_provider_error_with_original_exception(self):
        """Test provider error with original exception."""
        original = ConnectionError("Connection refused")
        error = ProviderError(
            "Failed to connect",
            hint="Check your connection",
            provider_name="anthropic",
            original_error=original,
        )
        assert error.provider_name == "anthropic"
        assert error.original_error is original
        assert error.context["provider"] == "anthropic"
        assert "Connection refused" in error.context["original_error"]
        assert error.context["original_error_type"] == "ConnectionError"


class TestIndexingError:
    """Tests for IndexingError."""

    def test_basic_indexing_error(self):
        """Test basic indexing error."""
        error = IndexingError("Indexing failed")
        assert "Indexing failed" in str(error)
        assert error.repo_path is None
        assert error.file_path is None

    def test_indexing_error_with_paths(self):
        """Test indexing error with path info."""
        error = IndexingError(
            "Permission denied",
            hint="Check permissions",
            repo_path="/path/to/repo",
            file_path="/path/to/repo/file.py",
        )
        assert error.repo_path == "/path/to/repo"
        assert error.file_path == "/path/to/repo/file.py"
        assert error.context["repo_path"] == "/path/to/repo"
        assert error.context["file_path"] == "/path/to/repo/file.py"


class TestExportError:
    """Tests for ExportError."""

    def test_basic_export_error(self):
        """Test basic export error."""
        error = ExportError("Export failed")
        assert "Export failed" in str(error)
        assert error.export_format is None
        assert error.output_path is None

    def test_export_error_with_format(self):
        """Test export error with format info."""
        error = ExportError(
            "PDF generation failed",
            hint="Install weasyprint",
            export_format="pdf",
            output_path="/output/docs.pdf",
        )
        assert error.export_format == "pdf"
        assert error.output_path == "/output/docs.pdf"
        assert error.context["format"] == "pdf"
        assert error.context["output_path"] == "/output/docs.pdf"


class TestResearchError:
    """Tests for ResearchError."""

    def test_basic_research_error(self):
        """Test basic research error."""
        error = ResearchError("Research failed")
        assert "Research failed" in str(error)
        assert error.step is None
        assert error.question is None

    def test_research_error_with_step(self):
        """Test research error with step info."""
        error = ResearchError(
            "Synthesis failed",
            hint="Try a simpler question",
            step="synthesis",
            question="How does the authentication work?",
        )
        assert error.step == "synthesis"
        assert error.question == "How does the authentication work?"
        assert error.context["step"] == "synthesis"
        assert "authentication" in error.context["question"]

    def test_research_error_truncates_long_question(self):
        """Test that long questions are truncated in context."""
        long_question = "x" * 200
        error = ResearchError("Failed", question=long_question)
        assert len(error.context["question"]) == 100


class TestValidationErrorFactory:
    """Tests for the validation_error factory function."""

    def test_creates_validation_error(self):
        """Test that factory creates ValidationError."""
        error = validation_error(
            field="repo_path",
            value="/nonexistent",
            expected="an existing directory",
        )
        assert isinstance(error, ValidationError)
        assert "repo_path" in str(error)
        assert "/nonexistent" in str(error)
        assert "Expected an existing directory" in str(error)

    def test_truncates_long_values(self):
        """Test that long values are truncated."""
        long_value = "x" * 200
        error = validation_error(
            field="test",
            value=long_value,
            expected="a short string",
        )
        # Value should be truncated in message
        assert "..." in str(error)

    def test_includes_additional_context(self):
        """Test that additional context is included."""
        error = validation_error(
            field="test",
            value="value",
            expected="something",
            context={"extra": "info"},
        )
        assert error.context["extra"] == "info"


class TestProviderErrorFactory:
    """Tests for the provider_error factory function."""

    def test_creates_provider_error(self):
        """Test that factory creates ProviderError."""
        original = Exception("API error")
        error = provider_error("anthropic", original)
        assert isinstance(error, ProviderError)
        assert error.provider_name == "anthropic"
        assert error.original_error is original

    def test_detects_api_key_error(self):
        """Test detection of API key errors."""
        original = Exception("Invalid API key")
        error = provider_error("anthropic", original)
        assert "authentication" in str(error).lower()
        assert "ANTHROPIC_API_KEY" in str(error)

    def test_detects_rate_limit_error(self):
        """Test detection of rate limit errors."""
        original = Exception("Rate limit exceeded")
        error = provider_error("openai", original)
        assert "rate limit" in str(error).lower()
        assert "wait" in str(error).lower()

    def test_detects_connection_error(self):
        """Test detection of connection errors."""
        original = Exception("Connection refused")
        error = provider_error("ollama", original)
        assert "connect" in str(error).lower()
        # Ollama-specific hint
        assert "ollama serve" in str(error).lower()

    def test_detects_model_not_found_error(self):
        """Test detection of model not found errors."""
        original = Exception("Model not found")
        error = provider_error("openai", original)
        assert "model" in str(error).lower()
        assert "not found" in str(error).lower() or "available" in str(error).lower()

    def test_detects_server_overloaded_error(self):
        """Test detection of server overloaded errors."""
        original = Exception("Server overloaded, try again later")
        error = provider_error("anthropic", original)
        assert "overloaded" in str(error).lower() or "unavailable" in str(error).lower()

    def test_detects_503_error(self):
        """Test detection of 503 errors."""
        original = Exception("503 Service Unavailable")
        error = provider_error("anthropic", original)
        assert "unavailable" in str(error).lower()

    def test_handles_unknown_error(self):
        """Test handling of unknown errors."""
        original = Exception("Some random error")
        error = provider_error("anthropic", original)
        assert isinstance(error, ProviderError)
        assert "Some random error" in str(error)


class TestEnvironmentErrorFactory:
    """Tests for the environment_error factory function."""

    def test_creates_environment_error(self):
        """Test that factory creates EnvironmentError."""
        error = environment_error(
            missing_component="weasyprint",
            purpose="PDF export",
            setup_instructions="pip install weasyprint",
        )
        assert isinstance(error, EnvironmentError)
        assert "weasyprint" in str(error)
        assert "PDF export" in str(error)
        assert "pip install weasyprint" in str(error)


class TestIndexingErrorFactory:
    """Tests for the indexing_error factory function."""

    def test_creates_indexing_error(self):
        """Test that factory creates IndexingError."""
        error = indexing_error(
            "Repository not found",
            repo_path="/path/to/repo",
        )
        assert isinstance(error, IndexingError)
        assert "not found" in str(error).lower()

    def test_provides_hint_for_not_found(self):
        """Test that not found error has appropriate hint."""
        error = indexing_error("Path does not exist")
        assert "path" in str(error).lower()

    def test_provides_hint_for_permission(self):
        """Test that permission error has appropriate hint."""
        error = indexing_error("Permission denied")
        assert "permission" in str(error).lower()

    def test_provides_hint_for_empty_repo(self):
        """Test that empty repo error has appropriate hint."""
        error = indexing_error("Repository is empty")
        assert "empty" in str(error).lower()

    def test_provides_hint_for_parse_error(self):
        """Test that parse error has appropriate hint."""
        error = indexing_error("Failed to parse file")
        assert "syntax" in str(error).lower() or "parse" in str(error).lower()


class TestExportErrorFactory:
    """Tests for the export_error factory function."""

    def test_creates_export_error(self):
        """Test that factory creates ExportError."""
        error = export_error(
            "Export failed",
            export_format="pdf",
            output_path="/output/docs.pdf",
        )
        assert isinstance(error, ExportError)
        assert error.export_format == "pdf"

    def test_provides_hint_for_weasyprint(self):
        """Test that weasyprint error has appropriate hint."""
        error = export_error("WeasyPrint not found", export_format="pdf")
        assert "weasyprint" in str(error).lower()
        assert "pip install" in str(error).lower()

    def test_provides_hint_for_mermaid(self):
        """Test that mermaid error has appropriate hint."""
        error = export_error("Mermaid CLI not found", export_format="pdf")
        assert "mermaid" in str(error).lower()
        assert "npm install" in str(error).lower()

    def test_provides_hint_for_html_permission(self):
        """Test that HTML permission error has appropriate hint."""
        error = export_error("Permission denied", export_format="html")
        assert "permission" in str(error).lower()


class TestResearchErrorFactory:
    """Tests for the research_error factory function."""

    def test_creates_research_error(self):
        """Test that factory creates ResearchError."""
        error = research_error(
            "Research failed",
            step="synthesis",
            question="How does it work?",
        )
        assert isinstance(error, ResearchError)
        assert error.step == "synthesis"

    def test_provides_hint_for_timeout(self):
        """Test that timeout error has appropriate hint."""
        error = research_error("Request timed out")
        assert "timeout" in str(error).lower() or "simpler" in str(error).lower()

    def test_provides_hint_for_provider_error(self):
        """Test that provider error has appropriate hint."""
        error = research_error("LLM provider failed")
        assert "api key" in str(error).lower() or "provider" in str(error).lower()

    def test_provides_hint_for_vector_error(self):
        """Test that vector search error has appropriate hint."""
        error = research_error("Vector search failed")
        assert "index" in str(error).lower()


class TestNotIndexedError:
    """Tests for not_indexed_error factory."""

    def test_creates_validation_error(self):
        """Test that factory creates ValidationError."""
        error = not_indexed_error("/path/to/repo")
        assert isinstance(error, ValidationError)
        assert "/path/to/repo" in str(error)
        assert "index_repository" in str(error)

    def test_includes_hint(self):
        """Test that error includes hint."""
        error = not_indexed_error("/path/to/repo")
        assert error.hint is not None
        assert "index_repository" in error.hint


class TestPathNotFoundError:
    """Tests for path_not_found_error factory."""

    def test_creates_validation_error(self):
        """Test that factory creates ValidationError."""
        error = path_not_found_error("/nonexistent/path", "repository")
        assert isinstance(error, ValidationError)
        assert "/nonexistent/path" in str(error)
        assert "Repository" in str(error)

    def test_uses_path_type_in_message(self):
        """Test that path type is used in message."""
        error = path_not_found_error("/path", "wiki")
        assert "Wiki" in str(error)


class TestMapExceptionToDeepWikiError:
    """Tests for map_exception_to_deepwiki_error function."""

    def test_returns_deepwiki_error_unchanged(self):
        """Test that DeepWikiError is returned unchanged."""
        original = DeepWikiError("test", hint="hint")
        result = map_exception_to_deepwiki_error(original)
        assert result is original

    def test_maps_file_not_found_error(self):
        """Test mapping of FileNotFoundError."""
        original = FileNotFoundError("No such file")
        result = map_exception_to_deepwiki_error(original)
        assert isinstance(result, DeepWikiError)
        assert result.hint is not None
        assert "file" in result.hint.lower() or "path" in result.hint.lower()

    def test_maps_permission_error(self):
        """Test mapping of PermissionError."""
        original = PermissionError("Access denied")
        result = map_exception_to_deepwiki_error(original)
        assert isinstance(result, DeepWikiError)
        assert "permission" in result.hint.lower()

    def test_maps_connection_error(self):
        """Test mapping of ConnectionError."""
        original = ConnectionError("Connection refused")
        result = map_exception_to_deepwiki_error(original)
        assert isinstance(result, DeepWikiError)
        assert "connection" in result.hint.lower()

    def test_maps_timeout_error(self):
        """Test mapping of TimeoutError."""
        original = TimeoutError("Request timed out")
        result = map_exception_to_deepwiki_error(original)
        assert isinstance(result, DeepWikiError)
        assert "timeout" in result.hint.lower() or "long" in result.hint.lower()

    def test_maps_unknown_error(self):
        """Test mapping of unknown errors."""
        original = Exception("Unknown error")
        result = map_exception_to_deepwiki_error(original)
        assert isinstance(result, DeepWikiError)
        assert result.hint is not None

    def test_preserves_context(self):
        """Test that context is preserved."""
        original = FileNotFoundError("test")
        result = map_exception_to_deepwiki_error(original, context={"key": "value"})
        assert result.context["key"] == "value"


class TestFormatErrorResponse:
    """Tests for format_error_response function."""

    def test_formats_error_without_hint(self):
        """Test formatting error without hint."""
        error = DeepWikiError("Something failed")
        result = format_error_response(error)
        assert result == "Error: Something failed"

    def test_formats_error_with_hint(self):
        """Test formatting error with hint."""
        error = DeepWikiError("Something failed", hint="Try again")
        result = format_error_response(error)
        assert "Error: Something failed" in result
        assert "Hint: Try again" in result


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_all_errors_inherit_from_deepwiki_error(self):
        """Test that all error classes inherit from DeepWikiError."""
        assert issubclass(ValidationError, DeepWikiError)
        assert issubclass(EnvironmentError, DeepWikiError)
        assert issubclass(ProviderError, DeepWikiError)
        assert issubclass(IndexingError, DeepWikiError)
        assert issubclass(ExportError, DeepWikiError)
        assert issubclass(ResearchError, DeepWikiError)

    def test_all_errors_can_be_caught_as_deepwiki_error(self):
        """Test that all errors can be caught as DeepWikiError."""
        errors = [
            ValidationError("test"),
            EnvironmentError("test"),
            ProviderError("test"),
            IndexingError("test"),
            ExportError("test"),
            ResearchError("test"),
        ]

        for error in errors:
            with pytest.raises(DeepWikiError):
                raise error

    def test_all_errors_can_be_caught_as_exception(self):
        """Test that all errors can be caught as Exception."""
        errors = [
            ValidationError("test"),
            EnvironmentError("test"),
            ProviderError("test"),
            IndexingError("test"),
            ExportError("test"),
            ResearchError("test"),
        ]

        for error in errors:
            with pytest.raises(Exception):
                raise error


class TestErrorContextManagement:
    """Tests for error context management."""

    def test_context_immutability(self):
        """Test that context dict is independent per instance."""
        error1 = DeepWikiError("test1")
        error2 = DeepWikiError("test2")

        error1.context["key"] = "value1"
        assert "key" not in error2.context

    def test_context_default_empty(self):
        """Test that context defaults to empty dict."""
        error = DeepWikiError("test")
        assert error.context == {}

    def test_context_can_be_modified(self):
        """Test that context can be modified after creation."""
        error = DeepWikiError("test")
        error.context["new_key"] = "new_value"
        assert error.context["new_key"] == "new_value"


class TestHandlerIntegration:
    """Integration tests for error handling in handlers."""

    async def test_validation_error_caught_by_handler(self):
        """Test that ValidationError is properly caught and formatted."""
        from local_deepwiki.handlers import handle_tool_errors

        @handle_tool_errors
        async def handler_that_raises_validation_error(args):
            raise ValidationError(
                "Invalid input",
                hint="Fix your input",
                field="test_field",
            )

        result = await handler_that_raises_validation_error({})
        assert len(result) == 1
        assert "Error: Invalid input" in result[0].text
        assert "Hint: Fix your input" in result[0].text

    async def test_provider_error_caught_by_handler(self):
        """Test that ProviderError is properly caught and formatted."""
        from local_deepwiki.handlers import handle_tool_errors

        @handle_tool_errors
        async def handler_that_raises_provider_error(args):
            raise ProviderError(
                "API call failed",
                hint="Check your API key",
                provider_name="anthropic",
            )

        result = await handler_that_raises_provider_error({})
        assert len(result) == 1
        assert "Error: API call failed" in result[0].text
        assert "Hint: Check your API key" in result[0].text

    async def test_file_not_found_error_mapped_by_handler(self):
        """Test that FileNotFoundError is mapped to DeepWikiError."""
        from local_deepwiki.handlers import handle_tool_errors

        @handle_tool_errors
        async def handler_that_raises_file_not_found(args):
            raise FileNotFoundError("test.txt not found")

        result = await handler_that_raises_file_not_found({})
        assert len(result) == 1
        assert "Error" in result[0].text
        assert "Hint" in result[0].text  # Should have a hint

    async def test_connection_error_mapped_by_handler(self):
        """Test that ConnectionError is mapped to DeepWikiError."""
        from local_deepwiki.handlers import handle_tool_errors

        @handle_tool_errors
        async def handler_that_raises_connection_error(args):
            raise ConnectionError("Connection refused")

        result = await handler_that_raises_connection_error({})
        assert len(result) == 1
        assert "Error" in result[0].text
        assert "connection" in result[0].text.lower()

    async def test_permission_error_mapped_by_handler(self):
        """Test that PermissionError is mapped to DeepWikiError."""
        from local_deepwiki.handlers import handle_tool_errors

        @handle_tool_errors
        async def handler_that_raises_permission_error(args):
            raise PermissionError("Access denied")

        result = await handler_that_raises_permission_error({})
        assert len(result) == 1
        assert "Error" in result[0].text
        assert "permission" in result[0].text.lower()

    async def test_timeout_error_mapped_by_handler(self):
        """Test that TimeoutError is mapped to DeepWikiError."""
        from local_deepwiki.handlers import handle_tool_errors

        @handle_tool_errors
        async def handler_that_raises_timeout_error(args):
            raise TimeoutError("Request timed out")

        result = await handler_that_raises_timeout_error({})
        assert len(result) == 1
        assert "Error" in result[0].text
        assert "timeout" in result[0].text.lower() or "timed" in result[0].text.lower()


class TestProviderSpecificHints:
    """Tests for provider-specific hint generation."""

    def test_anthropic_api_key_hint(self):
        """Test Anthropic API key error has proper hint."""
        error = provider_error("anthropic", Exception("Invalid API key"))
        assert "ANTHROPIC_API_KEY" in str(error)
        assert "console.anthropic.com" in str(error)

    def test_openai_api_key_hint(self):
        """Test OpenAI API key error has proper hint."""
        error = provider_error("openai", Exception("Authentication failed"))
        assert "OPENAI_API_KEY" in str(error)
        assert "platform.openai.com" in str(error)

    def test_ollama_connection_hint(self):
        """Test Ollama connection error has proper hint."""
        error = provider_error("ollama", Exception("Connection refused"))
        assert "ollama serve" in str(error)
        assert "ollama.ai/download" in str(error)

    def test_unknown_provider_generic_hint(self):
        """Test unknown provider gets generic hint."""
        error = provider_error("unknown_provider", Exception("Some error"))
        # Should still create an error with a hint
        assert error.hint is not None
        assert "unknown_provider" in error.hint.lower()
