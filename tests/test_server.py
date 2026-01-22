"""Tests for the MCP server module (server.py).

This module tests the MCP server functionality including:
- Tool listing
- Tool call dispatch
- Error handling for unknown tools
- Deep research special handling
- Server initialization
"""

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.server import (
    TOOL_HANDLERS,
    call_tool,
    list_tools,
    server,
)


class TestServer:
    """Tests for the MCP Server instance."""

    def test_server_is_initialized(self):
        """Test that the server is properly initialized."""
        assert server is not None
        assert server.name == "local-deepwiki"

    def test_tool_handlers_dictionary_has_expected_tools(self):
        """Test that TOOL_HANDLERS contains all expected tools."""
        expected_tools = [
            "index_repository",
            "ask_question",
            "read_wiki_structure",
            "read_wiki_page",
            "search_code",
            "export_wiki_html",
            "export_wiki_pdf",
        ]
        for tool_name in expected_tools:
            assert tool_name in TOOL_HANDLERS, f"Missing tool: {tool_name}"

    def test_deep_research_not_in_tool_handlers(self):
        """Test that deep_research is NOT in TOOL_HANDLERS (handled specially)."""
        # deep_research is handled specially in call_tool due to server context requirement
        assert "deep_research" not in TOOL_HANDLERS


class TestListTools:
    """Tests for the list_tools function."""

    async def test_list_tools_returns_list(self):
        """Test that list_tools returns a list of Tool objects."""
        tools = await list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    async def test_list_tools_returns_all_expected_tools(self):
        """Test that all expected tools are returned."""
        tools = await list_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "index_repository",
            "ask_question",
            "deep_research",
            "read_wiki_structure",
            "read_wiki_page",
            "search_code",
            "export_wiki_html",
            "export_wiki_pdf",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    async def test_index_repository_tool_schema(self):
        """Test index_repository tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "index_repository")

        assert "repo_path" in tool.inputSchema["properties"]
        assert "repo_path" in tool.inputSchema["required"]
        assert tool.inputSchema["properties"]["repo_path"]["type"] == "string"

        # Optional parameters
        assert "output_dir" in tool.inputSchema["properties"]
        assert "languages" in tool.inputSchema["properties"]
        assert "full_rebuild" in tool.inputSchema["properties"]
        assert "llm_provider" in tool.inputSchema["properties"]
        assert "embedding_provider" in tool.inputSchema["properties"]
        assert "use_cloud_for_github" in tool.inputSchema["properties"]

    async def test_ask_question_tool_schema(self):
        """Test ask_question tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "ask_question")

        assert "repo_path" in tool.inputSchema["properties"]
        assert "question" in tool.inputSchema["properties"]
        assert "max_context" in tool.inputSchema["properties"]

        assert "repo_path" in tool.inputSchema["required"]
        assert "question" in tool.inputSchema["required"]

    async def test_deep_research_tool_schema(self):
        """Test deep_research tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "deep_research")

        assert "repo_path" in tool.inputSchema["properties"]
        assert "question" in tool.inputSchema["properties"]
        assert "max_chunks" in tool.inputSchema["properties"]
        assert "preset" in tool.inputSchema["properties"]

        # Check preset enum values
        preset_enum = tool.inputSchema["properties"]["preset"]["enum"]
        assert "quick" in preset_enum
        assert "default" in preset_enum
        assert "thorough" in preset_enum

    async def test_read_wiki_structure_tool_schema(self):
        """Test read_wiki_structure tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "read_wiki_structure")

        assert "wiki_path" in tool.inputSchema["properties"]
        assert "wiki_path" in tool.inputSchema["required"]

    async def test_read_wiki_page_tool_schema(self):
        """Test read_wiki_page tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "read_wiki_page")

        assert "wiki_path" in tool.inputSchema["properties"]
        assert "page" in tool.inputSchema["properties"]
        assert "wiki_path" in tool.inputSchema["required"]
        assert "page" in tool.inputSchema["required"]

    async def test_search_code_tool_schema(self):
        """Test search_code tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "search_code")

        assert "repo_path" in tool.inputSchema["properties"]
        assert "query" in tool.inputSchema["properties"]
        assert "limit" in tool.inputSchema["properties"]
        assert "language" in tool.inputSchema["properties"]

        assert "repo_path" in tool.inputSchema["required"]
        assert "query" in tool.inputSchema["required"]

    async def test_export_wiki_html_tool_schema(self):
        """Test export_wiki_html tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "export_wiki_html")

        assert "wiki_path" in tool.inputSchema["properties"]
        assert "output_path" in tool.inputSchema["properties"]
        assert "wiki_path" in tool.inputSchema["required"]

    async def test_export_wiki_pdf_tool_schema(self):
        """Test export_wiki_pdf tool has correct schema."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "export_wiki_pdf")

        assert "wiki_path" in tool.inputSchema["properties"]
        assert "output_path" in tool.inputSchema["properties"]
        assert "single_file" in tool.inputSchema["properties"]
        assert "wiki_path" in tool.inputSchema["required"]

    async def test_all_tools_have_descriptions(self):
        """Test that all tools have non-empty descriptions."""
        tools = await list_tools()
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 0, f"Tool {tool.name} has empty description"

    async def test_all_tools_have_input_schemas(self):
        """Test that all tools have input schemas."""
        tools = await list_tools()
        for tool in tools:
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"


class TestCallTool:
    """Tests for the call_tool function."""

    async def test_unknown_tool_returns_error(self):
        """Test that unknown tools return an error message."""
        result = await call_tool("nonexistent_tool", {})

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Unknown tool" in result[0].text
        assert "nonexistent_tool" in result[0].text

    async def test_calls_index_repository_handler(self, tmp_path):
        """Test that index_repository dispatches to handler."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text="success")])
        with patch.dict(TOOL_HANDLERS, {"index_repository": mock_handler}):
            args = {"repo_path": str(tmp_path)}

            result = await call_tool("index_repository", args)

            mock_handler.assert_called_once_with(args)
            assert result[0].text == "success"

    async def test_calls_ask_question_handler(self, tmp_path):
        """Test that ask_question dispatches to handler."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text="answer")])
        with patch.dict(TOOL_HANDLERS, {"ask_question": mock_handler}):
            args = {"repo_path": str(tmp_path), "question": "What does this do?"}

            result = await call_tool("ask_question", args)

            mock_handler.assert_called_once_with(args)
            assert result[0].text == "answer"

    async def test_calls_read_wiki_structure_handler(self, tmp_path):
        """Test that read_wiki_structure dispatches to handler."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text='{"pages": []}')])
        with patch.dict(TOOL_HANDLERS, {"read_wiki_structure": mock_handler}):
            args = {"wiki_path": str(tmp_path)}

            result = await call_tool("read_wiki_structure", args)

            mock_handler.assert_called_once_with(args)

    async def test_calls_read_wiki_page_handler(self, tmp_path):
        """Test that read_wiki_page dispatches to handler."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text="# Page content")])
        with patch.dict(TOOL_HANDLERS, {"read_wiki_page": mock_handler}):
            args = {"wiki_path": str(tmp_path), "page": "index.md"}

            result = await call_tool("read_wiki_page", args)

            mock_handler.assert_called_once_with(args)

    async def test_calls_search_code_handler(self, tmp_path):
        """Test that search_code dispatches to handler."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text="[]")])
        with patch.dict(TOOL_HANDLERS, {"search_code": mock_handler}):
            args = {"repo_path": str(tmp_path), "query": "test"}

            result = await call_tool("search_code", args)

            mock_handler.assert_called_once_with(args)

    async def test_calls_export_wiki_html_handler(self, tmp_path):
        """Test that export_wiki_html dispatches to handler."""
        mock_handler = AsyncMock(
            return_value=[TextContent(type="text", text='{"status": "success"}')]
        )
        with patch.dict(TOOL_HANDLERS, {"export_wiki_html": mock_handler}):
            args = {"wiki_path": str(tmp_path)}

            result = await call_tool("export_wiki_html", args)

            mock_handler.assert_called_once_with(args)

    async def test_calls_export_wiki_pdf_handler(self, tmp_path):
        """Test that export_wiki_pdf dispatches to handler."""
        mock_handler = AsyncMock(
            return_value=[TextContent(type="text", text='{"status": "success"}')]
        )
        with patch.dict(TOOL_HANDLERS, {"export_wiki_pdf": mock_handler}):
            args = {"wiki_path": str(tmp_path)}

            result = await call_tool("export_wiki_pdf", args)

            mock_handler.assert_called_once_with(args)


class TestCallToolDeepResearch:
    """Tests for deep_research special handling in call_tool."""

    async def test_deep_research_passes_server_to_handler(self, tmp_path):
        """Test that deep_research handler receives the server context."""
        with patch("local_deepwiki.server.handle_deep_research") as mock_handler:
            mock_handler.return_value = [TextContent(type="text", text='{"answer": "result"}')]
            args = {"repo_path": str(tmp_path), "question": "How does X work?"}

            await call_tool("deep_research", args)

            # Verify handler was called with server=server keyword argument
            mock_handler.assert_called_once()
            call_args, call_kwargs = mock_handler.call_args
            assert call_args[0] == args
            assert "server" in call_kwargs
            assert call_kwargs["server"] is server

    async def test_deep_research_returns_handler_result(self, tmp_path):
        """Test that deep_research returns the handler's result."""
        expected_response = {
            "question": "How does X work?",
            "answer": "X works by doing Y",
            "sub_questions": [],
            "sources": [],
        }
        with patch("local_deepwiki.server.handle_deep_research") as mock_handler:
            mock_handler.return_value = [
                TextContent(type="text", text=json.dumps(expected_response))
            ]
            args = {"repo_path": str(tmp_path), "question": "How does X work?"}

            result = await call_tool("deep_research", args)

            assert len(result) == 1
            response_data = json.loads(result[0].text)
            assert response_data["answer"] == "X works by doing Y"


class TestToolHandlersIntegration:
    """Integration tests verifying handlers are properly connected."""

    async def test_index_repository_real_handler_validation(self, tmp_path):
        """Test that real handler validates inputs (no mocking)."""
        nonexistent = tmp_path / "nonexistent"
        result = await call_tool("index_repository", {"repo_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_ask_question_real_handler_validation(self):
        """Test that real ask_question handler validates inputs."""
        result = await call_tool("ask_question", {"repo_path": "/tmp", "question": ""})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "cannot be empty" in result[0].text

    async def test_search_code_real_handler_validation(self):
        """Test that real search_code handler validates inputs."""
        result = await call_tool("search_code", {"repo_path": "/tmp", "query": ""})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "cannot be empty" in result[0].text

    async def test_read_wiki_structure_real_handler_validation(self, tmp_path):
        """Test that real read_wiki_structure handler validates inputs."""
        nonexistent = tmp_path / "nonexistent"
        result = await call_tool("read_wiki_structure", {"wiki_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_read_wiki_page_real_handler_validation(self, tmp_path):
        """Test that real read_wiki_page handler validates inputs."""
        result = await call_tool(
            "read_wiki_page", {"wiki_path": str(tmp_path), "page": "nonexistent.md"}
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not found" in result[0].text

    async def test_export_wiki_html_real_handler_validation(self, tmp_path):
        """Test that real export_wiki_html handler validates inputs."""
        nonexistent = tmp_path / "nonexistent"
        result = await call_tool("export_wiki_html", {"wiki_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_export_wiki_pdf_real_handler_validation(self, tmp_path):
        """Test that real export_wiki_pdf handler validates inputs or returns library error."""
        nonexistent = tmp_path / "nonexistent"
        result = await call_tool("export_wiki_pdf", {"wiki_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        # Either validation error (does not exist) or WeasyPrint library error
        assert "does not exist" in result[0].text or "cannot load library" in result[0].text


class TestToolSchemaValidation:
    """Tests for tool schema structure validation."""

    async def test_llm_provider_enum_values(self):
        """Test that llm_provider has correct enum values."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "index_repository")

        llm_provider_enum = tool.inputSchema["properties"]["llm_provider"]["enum"]
        assert "ollama" in llm_provider_enum
        assert "anthropic" in llm_provider_enum
        assert "openai" in llm_provider_enum

    async def test_embedding_provider_enum_values(self):
        """Test that embedding_provider has correct enum values."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "index_repository")

        embedding_provider_enum = tool.inputSchema["properties"]["embedding_provider"]["enum"]
        assert "local" in embedding_provider_enum
        assert "openai" in embedding_provider_enum

    async def test_languages_array_type(self):
        """Test that languages is an array of strings."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "index_repository")

        languages_schema = tool.inputSchema["properties"]["languages"]
        assert languages_schema["type"] == "array"
        assert languages_schema["items"]["type"] == "string"

    async def test_boolean_property_types(self):
        """Test that boolean properties have correct type."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "index_repository")

        assert tool.inputSchema["properties"]["full_rebuild"]["type"] == "boolean"
        assert tool.inputSchema["properties"]["use_cloud_for_github"]["type"] == "boolean"

    async def test_integer_property_types(self):
        """Test that integer properties have correct type."""
        tools = await list_tools()

        # ask_question max_context
        ask_tool = next(t for t in tools if t.name == "ask_question")
        assert ask_tool.inputSchema["properties"]["max_context"]["type"] == "integer"

        # deep_research max_chunks
        deep_tool = next(t for t in tools if t.name == "deep_research")
        assert deep_tool.inputSchema["properties"]["max_chunks"]["type"] == "integer"

        # search_code limit
        search_tool = next(t for t in tools if t.name == "search_code")
        assert search_tool.inputSchema["properties"]["limit"]["type"] == "integer"


class TestMainFunction:
    """Tests for the main entry point."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        from local_deepwiki.server import main

        assert callable(main)

    @patch("local_deepwiki.server.asyncio.run")
    @patch("local_deepwiki.server.stdio_server")
    def test_main_calls_asyncio_run(self, mock_stdio, mock_asyncio_run):
        """Test that main calls asyncio.run."""
        from local_deepwiki.server import main

        # Setup mock to avoid actual server startup
        mock_asyncio_run.return_value = None

        main()

        mock_asyncio_run.assert_called_once()

    @patch("local_deepwiki.server.logger")
    @patch("local_deepwiki.server.asyncio.run")
    def test_main_logs_startup(self, mock_asyncio_run, mock_logger):
        """Test that main logs server startup."""
        from local_deepwiki.server import main

        mock_asyncio_run.return_value = None

        main()

        mock_logger.info.assert_called()
        # Check that startup message was logged
        calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Starting" in str(call) or "local-deepwiki" in str(call) for call in calls)


class TestToolDescriptions:
    """Tests for tool description quality."""

    async def test_index_repository_description_is_informative(self):
        """Test that index_repository has an informative description."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "index_repository")

        description = tool.description.lower()
        assert "index" in description
        assert "repository" in description or "wiki" in description

    async def test_ask_question_description_is_informative(self):
        """Test that ask_question has an informative description."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "ask_question")

        description = tool.description.lower()
        assert "question" in description
        assert "rag" in description or "context" in description or "answer" in description

    async def test_deep_research_description_is_informative(self):
        """Test that deep_research has an informative description."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "deep_research")

        description = tool.description.lower()
        assert "research" in description
        # Should mention multi-step or complex reasoning
        assert "multi" in description or "complex" in description or "step" in description

    async def test_search_code_description_is_informative(self):
        """Test that search_code has an informative description."""
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "search_code")

        description = tool.description.lower()
        assert "search" in description
        assert "semantic" in description or "code" in description

    async def test_export_tools_descriptions_are_informative(self):
        """Test that export tools have informative descriptions."""
        tools = await list_tools()

        html_tool = next(t for t in tools if t.name == "export_wiki_html")
        assert "html" in html_tool.description.lower()
        assert "export" in html_tool.description.lower()

        pdf_tool = next(t for t in tools if t.name == "export_wiki_pdf")
        assert "pdf" in pdf_tool.description.lower()
        assert "export" in pdf_tool.description.lower()
