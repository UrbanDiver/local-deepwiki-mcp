"""LanceDB vector store for code chunk storage and retrieval."""

import json
from pathlib import Path
from typing import Any

import lancedb
from lancedb.table import Table

from local_deepwiki.models import CodeChunk, SearchResult
from local_deepwiki.providers.base import EmbeddingProvider


class VectorStore:
    """Vector store using LanceDB for code chunk storage and semantic search."""

    TABLE_NAME = "code_chunks"

    def __init__(self, db_path: Path, embedding_provider: EmbeddingProvider):
        """Initialize the vector store.

        Args:
            db_path: Path to the LanceDB database directory.
            embedding_provider: Provider for generating embeddings.
        """
        self.db_path = db_path
        self.embedding_provider = embedding_provider
        self._db: lancedb.DBConnection | None = None
        self._table: Table | None = None

    def _connect(self) -> lancedb.DBConnection:
        """Get or create database connection."""
        if self._db is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.db_path))
        return self._db

    def _get_table(self) -> Table | None:
        """Get the chunks table if it exists."""
        if self._table is None:
            db = self._connect()
            if self.TABLE_NAME in db.table_names():
                self._table = db.open_table(self.TABLE_NAME)
        return self._table

    async def create_or_update_table(self, chunks: list[CodeChunk]) -> int:
        """Create or update the vector table with code chunks.

        Args:
            chunks: List of code chunks to store.

        Returns:
            Number of chunks stored.
        """
        if not chunks:
            return 0

        db = self._connect()

        # Generate embeddings for all chunks
        texts = [self._chunk_to_text(chunk) for chunk in chunks]
        embeddings = await self.embedding_provider.embed(texts)

        # Prepare data for LanceDB
        data = []
        for chunk, embedding in zip(chunks, embeddings):
            data.append({
                "id": chunk.id,
                "file_path": chunk.file_path,
                "language": chunk.language.value,
                "chunk_type": chunk.chunk_type.value,
                "name": chunk.name or "",
                "content": chunk.content,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "docstring": chunk.docstring or "",
                "parent_name": chunk.parent_name or "",
                "metadata": json.dumps(chunk.metadata),
                "vector": embedding,
            })

        # Drop existing table and create new one
        if self.TABLE_NAME in db.table_names():
            db.drop_table(self.TABLE_NAME)

        self._table = db.create_table(self.TABLE_NAME, data)
        return len(data)

    async def add_chunks(self, chunks: list[CodeChunk]) -> int:
        """Add chunks to existing table.

        Args:
            chunks: List of code chunks to add.

        Returns:
            Number of chunks added.
        """
        if not chunks:
            return 0

        table = self._get_table()
        if table is None:
            return await self.create_or_update_table(chunks)

        # Generate embeddings
        texts = [self._chunk_to_text(chunk) for chunk in chunks]
        embeddings = await self.embedding_provider.embed(texts)

        # Prepare data
        data = []
        for chunk, embedding in zip(chunks, embeddings):
            data.append({
                "id": chunk.id,
                "file_path": chunk.file_path,
                "language": chunk.language.value,
                "chunk_type": chunk.chunk_type.value,
                "name": chunk.name or "",
                "content": chunk.content,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "docstring": chunk.docstring or "",
                "parent_name": chunk.parent_name or "",
                "metadata": json.dumps(chunk.metadata),
                "vector": embedding,
            })

        table.add(data)
        return len(data)

    async def search(
        self,
        query: str,
        limit: int = 10,
        language: str | None = None,
        chunk_type: str | None = None,
    ) -> list[SearchResult]:
        """Search for similar code chunks.

        Args:
            query: Search query text.
            limit: Maximum number of results.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.

        Returns:
            List of search results with scores.
        """
        table = self._get_table()
        if table is None:
            return []

        # Generate query embedding
        query_embedding = (await self.embedding_provider.embed([query]))[0]

        # Build search query
        search = table.search(query_embedding).limit(limit)

        # Apply filters
        filters = []
        if language:
            filters.append(f"language = '{language}'")
        if chunk_type:
            filters.append(f"chunk_type = '{chunk_type}'")

        if filters:
            search = search.where(" AND ".join(filters))

        # Execute search
        results = search.to_list()

        # Convert to SearchResult objects
        search_results = []
        for row in results:
            chunk = CodeChunk(
                id=row["id"],
                file_path=row["file_path"],
                language=row["language"],
                chunk_type=row["chunk_type"],
                name=row["name"] or None,
                content=row["content"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                docstring=row["docstring"] or None,
                parent_name=row["parent_name"] or None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            search_results.append(SearchResult(
                chunk=chunk,
                score=1.0 - row.get("_distance", 0),  # Convert distance to similarity
                highlights=[],
            ))

        return search_results

    async def get_chunk_by_id(self, chunk_id: str) -> CodeChunk | None:
        """Get a specific chunk by ID.

        Args:
            chunk_id: The chunk ID.

        Returns:
            The CodeChunk or None if not found.
        """
        table = self._get_table()
        if table is None:
            return None

        results = table.search().where(f"id = '{chunk_id}'").limit(1).to_list()
        if not results:
            return None

        row = results[0]
        return CodeChunk(
            id=row["id"],
            file_path=row["file_path"],
            language=row["language"],
            chunk_type=row["chunk_type"],
            name=row["name"] or None,
            content=row["content"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            docstring=row["docstring"] or None,
            parent_name=row["parent_name"] or None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    async def get_chunks_by_file(self, file_path: str) -> list[CodeChunk]:
        """Get all chunks for a specific file.

        Args:
            file_path: The file path.

        Returns:
            List of CodeChunks for the file.
        """
        table = self._get_table()
        if table is None:
            return []

        results = table.search().where(f"file_path = '{file_path}'").to_list()
        chunks = []
        for row in results:
            chunks.append(CodeChunk(
                id=row["id"],
                file_path=row["file_path"],
                language=row["language"],
                chunk_type=row["chunk_type"],
                name=row["name"] or None,
                content=row["content"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                docstring=row["docstring"] or None,
                parent_name=row["parent_name"] or None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            ))
        return chunks

    async def delete_chunks_by_file(self, file_path: str) -> int:
        """Delete all chunks for a specific file.

        Args:
            file_path: The file path.

        Returns:
            Number of chunks deleted.
        """
        table = self._get_table()
        if table is None:
            return 0

        # Count before delete
        before = len(table.search().where(f"file_path = '{file_path}'").to_list())

        # Delete matching rows
        table.delete(f"file_path = '{file_path}'")

        return before

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the vector store.

        Returns:
            Dictionary with store statistics.
        """
        table = self._get_table()
        if table is None:
            return {"total_chunks": 0, "languages": {}, "chunk_types": {}}

        # Get all data for stats
        all_data = table.to_pandas()

        return {
            "total_chunks": len(all_data),
            "languages": all_data["language"].value_counts().to_dict(),
            "chunk_types": all_data["chunk_type"].value_counts().to_dict(),
            "files": all_data["file_path"].nunique(),
        }

    def _chunk_to_text(self, chunk: CodeChunk) -> str:
        """Convert a chunk to text for embedding.

        Args:
            chunk: The code chunk.

        Returns:
            Text representation for embedding.
        """
        parts = []

        # Add context about the chunk
        if chunk.name:
            parts.append(f"{chunk.chunk_type.value}: {chunk.name}")

        if chunk.parent_name:
            parts.append(f"in {chunk.parent_name}")

        parts.append(f"({chunk.language.value})")

        # Add docstring if present
        if chunk.docstring:
            parts.append(f"\n{chunk.docstring}")

        # Add the actual code
        parts.append(f"\n{chunk.content}")

        return " ".join(parts)
