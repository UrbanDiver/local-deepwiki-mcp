"""MCP server for local DeepWiki functionality."""

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from local_deepwiki.config import Config, get_config, set_config
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.logging import get_logger
from local_deepwiki.models import Language, WikiStructure
from local_deepwiki.providers.embeddings import get_embedding_provider

logger = get_logger(__name__)


# Input validation constants
MIN_CONTEXT_CHUNKS = 1
MAX_CONTEXT_CHUNKS = 50
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 100
VALID_LANGUAGES = {lang.value for lang in Language}
VALID_LLM_PROVIDERS = {"ollama", "anthropic", "openai"}
VALID_EMBEDDING_PROVIDERS = {"local", "openai"}


def _validate_positive_int(value: Any, name: str, min_val: int, max_val: int, default: int) -> int:
    """Validate and bound an integer parameter.

    Args:
        value: The value to validate.
        name: Parameter name for error messages.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        default: Default value if None.

    Returns:
        Validated and bounded integer.

    Raises:
        ValueError: If value is not a valid integer.
    """
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {type(value).__name__}")
    return max(min_val, min(max_val, value))


def _validate_non_empty_string(value: Any, name: str) -> str:
    """Validate that a string is non-empty.

    Args:
        value: The value to validate.
        name: Parameter name for error messages.

    Returns:
        The validated string.

    Raises:
        ValueError: If value is not a non-empty string.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} cannot be empty")
    return value


def _validate_language(language: str | None) -> str | None:
    """Validate a language filter value.

    Args:
        language: The language to validate.

    Returns:
        The validated language or None.

    Raises:
        ValueError: If language is invalid.
    """
    if language is None:
        return None
    if language not in VALID_LANGUAGES:
        raise ValueError(
            f"Invalid language: '{language}'. Valid options: {sorted(VALID_LANGUAGES)}"
        )
    return language


def _validate_languages_list(languages: list[str] | None) -> list[str] | None:
    """Validate a list of languages.

    Args:
        languages: List of languages to validate.

    Returns:
        The validated list or None.

    Raises:
        ValueError: If any language is invalid.
    """
    if languages is None:
        return None
    if not isinstance(languages, list):
        raise ValueError(f"languages must be a list, got {type(languages).__name__}")

    invalid = [lang for lang in languages if lang not in VALID_LANGUAGES]
    if invalid:
        raise ValueError(f"Invalid languages: {invalid}. Valid options: {sorted(VALID_LANGUAGES)}")
    return languages


def _validate_provider(provider: str | None, valid_providers: set[str], name: str) -> str | None:
    """Validate a provider value.

    Args:
        provider: The provider to validate.
        valid_providers: Set of valid provider names.
        name: Parameter name for error messages.

    Returns:
        The validated provider or None.

    Raises:
        ValueError: If provider is invalid.
    """
    if provider is None:
        return None
    if provider not in valid_providers:
        raise ValueError(f"Invalid {name}: '{provider}'. Valid options: {sorted(valid_providers)}")
    return provider


# Create the MCP server
server = Server("local-deepwiki")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="index_repository",
            description="Index a repository and generate wiki documentation. This parses all source files, extracts semantic code chunks, generates embeddings, and creates wiki markdown files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the repository to index",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional output directory for wiki (default: {repo}/.deepwiki)",
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of languages to include (default: all supported)",
                    },
                    "full_rebuild": {
                        "type": "boolean",
                        "description": "Force full rebuild instead of incremental update (default: false)",
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["ollama", "anthropic", "openai"],
                        "description": "LLM provider for wiki generation (default: from config)",
                    },
                    "embedding_provider": {
                        "type": "string",
                        "enum": ["local", "openai"],
                        "description": "Embedding provider for semantic search (default: from config)",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="ask_question",
            description="Ask a question about an indexed repository using RAG. Returns an answer based on relevant code context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the codebase",
                    },
                    "max_context": {
                        "type": "integer",
                        "description": "Maximum number of code chunks for context (default: 5)",
                    },
                },
                "required": ["repo_path", "question"],
            },
        ),
        Tool(
            name="read_wiki_structure",
            description="Get the table of contents and structure of a generated wiki.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                    },
                },
                "required": ["wiki_path"],
            },
        ),
        Tool(
            name="read_wiki_page",
            description="Read a specific wiki page content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory",
                    },
                    "page": {
                        "type": "string",
                        "description": "Page path relative to wiki root (e.g., 'index.md', 'modules/auth.md')",
                    },
                },
                "required": ["wiki_path", "page"],
            },
        ),
        Tool(
            name="search_code",
            description="Semantic search across the indexed codebase. Returns relevant code chunks with similarity scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "query": {
                        "type": "string",
                        "description": "Semantic search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter",
                    },
                },
                "required": ["repo_path", "query"],
            },
        ),
        Tool(
            name="export_wiki_html",
            description="Export wiki documentation to static HTML files. Creates a self-contained website that can be viewed without a server.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output directory for HTML files (default: {wiki_path}_html)",
                    },
                },
                "required": ["wiki_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call received: {name}")
    logger.debug(f"Tool arguments: {arguments}")

    if name == "index_repository":
        return await handle_index_repository(arguments)
    elif name == "ask_question":
        return await handle_ask_question(arguments)
    elif name == "read_wiki_structure":
        return await handle_read_wiki_structure(arguments)
    elif name == "read_wiki_page":
        return await handle_read_wiki_page(arguments)
    elif name == "search_code":
        return await handle_search_code(arguments)
    elif name == "export_wiki_html":
        return await handle_export_wiki_html(arguments)
    else:
        logger.warning(f"Unknown tool requested: {name}")
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_index_repository(args: dict[str, Any]) -> list[TextContent]:
    """Handle index_repository tool call."""
    repo_path = Path(args["repo_path"]).resolve()
    logger.info(f"Indexing repository: {repo_path}")

    if not repo_path.exists():
        logger.error(f"Repository path does not exist: {repo_path}")
        return [
            TextContent(type="text", text=f"Error: Repository path does not exist: {repo_path}")
        ]

    if not repo_path.is_dir():
        logger.error(f"Path is not a directory: {repo_path}")
        return [TextContent(type="text", text=f"Error: Path is not a directory: {repo_path}")]

    # Validate optional parameters
    try:
        languages = _validate_languages_list(args.get("languages"))
        llm_provider = _validate_provider(
            args.get("llm_provider"), VALID_LLM_PROVIDERS, "llm_provider"
        )
        embedding_provider = _validate_provider(
            args.get("embedding_provider"), VALID_EMBEDDING_PROVIDERS, "embedding_provider"
        )
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]

    # Get config
    config = get_config()

    # Override languages if specified
    if languages:
        config.parsing.languages = languages

    # Create indexer
    indexer = RepositoryIndexer(
        repo_path=repo_path,
        config=config,
        embedding_provider_name=embedding_provider,
    )

    # Index the repository
    full_rebuild = args.get("full_rebuild", False)

    messages = []

    def progress_callback(msg: str, current: int, total: int):
        messages.append(f"[{current}/{total}] {msg}")

    try:
        status = await indexer.index(
            full_rebuild=full_rebuild,
            progress_callback=progress_callback,
        )

        # Generate wiki documentation
        messages.append("Generating wiki documentation...")

        wiki_structure = await generate_wiki(
            repo_path=repo_path,
            wiki_path=indexer.wiki_path,
            vector_store=indexer.vector_store,
            index_status=status,
            config=config,
            llm_provider=llm_provider,
            progress_callback=progress_callback,
            full_rebuild=full_rebuild,
        )

        result = {
            "status": "success",
            "repo_path": str(repo_path),
            "wiki_path": str(indexer.wiki_path),
            "files_indexed": status.total_files,
            "chunks_created": status.total_chunks,
            "languages": status.languages,
            "wiki_pages": len(wiki_structure.pages),
            "messages": messages,
        }

        logger.info(
            f"Indexing complete: {status.total_files} files, {status.total_chunks} chunks, {len(wiki_structure.pages)} wiki pages"
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception(f"Error indexing repository: {e}")
        return [TextContent(type="text", text=f"Error indexing repository: {str(e)}")]


async def handle_ask_question(args: dict[str, Any]) -> list[TextContent]:
    """Handle ask_question tool call."""
    repo_path = Path(args["repo_path"]).resolve()

    # Validate inputs
    try:
        question = _validate_non_empty_string(args.get("question", ""), "question")
        max_context = _validate_positive_int(
            args.get("max_context"),
            "max_context",
            MIN_CONTEXT_CHUNKS,
            MAX_CONTEXT_CHUNKS,
            default=5,
        )
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]

    logger.info(f"Question about {repo_path}: {question[:100]}...")
    logger.debug(f"Max context chunks: {max_context}")

    config = get_config()
    wiki_path = config.get_wiki_path(repo_path)
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        logger.error(f"Repository not indexed: {repo_path}")
        return [
            TextContent(
                type="text", text=f"Error: Repository not indexed. Run index_repository first."
            )
        ]

    # Create vector store
    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(vector_db_path, embedding_provider)

    # Search for relevant context
    search_results = await vector_store.search(question, limit=max_context)

    if not search_results:
        return [TextContent(type="text", text="No relevant code found for your question.")]

    # Build context from search results
    context_parts = []
    for result in search_results:
        chunk = result.chunk
        context_parts.append(
            f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
            f"Type: {chunk.chunk_type.value}\n"
            f"```\n{chunk.content}\n```"
        )

    context = "\n\n---\n\n".join(context_parts)

    # Generate answer using LLM
    from local_deepwiki.providers.llm import get_llm_provider

    llm = get_llm_provider(config.llm)

    prompt = f"""Based on the following code context, answer this question: {question}

Code Context:
{context}

Provide a clear, accurate answer based only on the code provided. If the code doesn't contain enough information to answer fully, say so."""

    system_prompt = (
        "You are a helpful code assistant. Answer questions about code clearly and accurately."
    )

    try:
        answer = await llm.generate(prompt, system_prompt=system_prompt)

        result = {
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "file": r.chunk.file_path,
                    "lines": f"{r.chunk.start_line}-{r.chunk.end_line}",
                    "type": r.chunk.chunk_type.value,
                    "score": r.score,
                }
                for r in search_results
            ],
        }

        logger.info(f"Generated answer with {len(search_results)} sources")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception(f"Error generating answer: {e}")
        return [TextContent(type="text", text=f"Error generating answer: {str(e)}")]


async def handle_read_wiki_structure(args: dict[str, Any]) -> list[TextContent]:
    """Handle read_wiki_structure tool call."""
    wiki_path = Path(args["wiki_path"]).resolve()

    if not wiki_path.exists():
        return [TextContent(type="text", text=f"Error: Wiki path does not exist: {wiki_path}")]

    # Check for toc.json (numbered hierarchical structure)
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        try:
            toc_data = json.loads(toc_path.read_text())
            return [TextContent(type="text", text=json.dumps(toc_data, indent=2))]
        except (json.JSONDecodeError, OSError):
            pass  # Fall back to dynamic generation

    # Fall back to dynamic generation if no toc.json
    pages = []
    for md_file in wiki_path.rglob("*.md"):
        rel_path = str(md_file.relative_to(wiki_path))
        # Read first line for title
        try:
            with open(md_file) as f:
                first_line = f.readline().strip()
                title = first_line.lstrip("#").strip() if first_line.startswith("#") else rel_path
        except Exception as e:
            logger.debug(f"Could not read title from {md_file}: {e}")
            title = rel_path

        pages.append(
            {
                "path": rel_path,
                "title": title,
            }
        )

    # Build hierarchical structure (legacy format without numbers)
    structure: dict[str, Any] = {"pages": [], "sections": {}}

    for page in sorted(pages, key=lambda p: p["path"]):
        parts = Path(page["path"]).parts
        if len(parts) == 1:
            structure["pages"].append(page)
        else:
            section = parts[0]
            if section not in structure["sections"]:
                structure["sections"][section] = []
            structure["sections"][section].append(page)

    return [TextContent(type="text", text=json.dumps(structure, indent=2))]


async def handle_read_wiki_page(args: dict[str, Any]) -> list[TextContent]:
    """Handle read_wiki_page tool call."""
    wiki_path = Path(args["wiki_path"]).resolve()
    page = args["page"]

    # Resolve the full path and validate it's within the wiki directory
    # This prevents path traversal attacks (e.g., "../../etc/passwd")
    page_path = (wiki_path / page).resolve()
    if not page_path.is_relative_to(wiki_path):
        return [TextContent(type="text", text="Error: Invalid page path")]

    if not page_path.exists():
        return [TextContent(type="text", text=f"Error: Page not found: {page}")]

    try:
        content = page_path.read_text()
        return [TextContent(type="text", text=content)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading page: {str(e)}")]


async def handle_search_code(args: dict[str, Any]) -> list[TextContent]:
    """Handle search_code tool call."""
    repo_path = Path(args["repo_path"]).resolve()

    # Validate inputs
    try:
        query = _validate_non_empty_string(args.get("query", ""), "query")
        limit = _validate_positive_int(
            args.get("limit"),
            "limit",
            MIN_SEARCH_LIMIT,
            MAX_SEARCH_LIMIT,
            default=10,
        )
        language = _validate_language(args.get("language"))
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]

    logger.info(f"Code search in {repo_path}: {query[:50]}...")
    logger.debug(f"Search limit: {limit}, language filter: {language}")

    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        logger.error(f"Repository not indexed: {repo_path}")
        return [
            TextContent(
                type="text", text=f"Error: Repository not indexed. Run index_repository first."
            )
        ]

    # Create vector store
    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(vector_db_path, embedding_provider)

    # Search
    results = await vector_store.search(query, limit=limit, language=language)

    logger.info(f"Search returned {len(results)} results")
    if not results:
        return [TextContent(type="text", text="No results found.")]

    output = []
    for r in results:
        chunk = r.chunk
        output.append(
            {
                "file_path": chunk.file_path,
                "name": chunk.name,
                "type": chunk.chunk_type.value,
                "language": chunk.language.value,
                "lines": f"{chunk.start_line}-{chunk.end_line}",
                "score": round(r.score, 4),
                "preview": (
                    chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content
                ),
                "docstring": chunk.docstring,
            }
        )

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def handle_export_wiki_html(args: dict[str, Any]) -> list[TextContent]:
    """Handle export_wiki_html tool call."""
    from local_deepwiki.export.html import export_to_html

    wiki_path = Path(args["wiki_path"]).resolve()
    output_path = args.get("output_path")

    if not wiki_path.exists():
        return [TextContent(type="text", text=f"Error: Wiki path does not exist: {wiki_path}")]

    try:
        if output_path:
            output_path = Path(output_path).resolve()

        result = export_to_html(wiki_path, output_path)

        # Get actual output path for the response
        actual_output = output_path or (wiki_path.parent / f"{wiki_path.name}_html")

        response = {
            "status": "success",
            "message": result,
            "output_path": str(actual_output),
            "open_with": f"open {actual_output}/index.html",
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error exporting wiki: {str(e)}")]


def main():
    """Main entry point for the MCP server."""
    logger.info("Starting local-deepwiki MCP server")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
