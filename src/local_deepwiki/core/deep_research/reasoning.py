"""Core reasoning methods for the deep research pipeline.

Contains the LLM-driven decomposition, gap analysis, synthesis, and
retrieval logic that forms the intellectual core of deep research.
"""

from __future__ import annotations

import asyncio
import json
import re

from local_deepwiki.core.rate_limiter import get_rate_limiter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import SearchResult, SourceReference, SubQuestion

logger = get_logger(__name__)

# Prompts for each research step

DECOMPOSITION_SYSTEM_PROMPT = """You are analyzing questions about codebases. Your task is to break down complex questions into simpler sub-questions that can be investigated independently.

Always respond with valid JSON only, no other text."""

DECOMPOSITION_USER_PROMPT = """Break down this question about a codebase into 2-4 sub-questions that would help answer it comprehensively.

Question: {question}

Respond in this exact JSON format:
{{
  "sub_questions": [
    {{"question": "What is the specific sub-question?", "category": "structure"}},
    {{"question": "Another sub-question?", "category": "flow"}}
  ]
}}

Categories must be one of: structure, flow, dependencies, impact, comparison

Provide only the JSON, no other text."""


GAP_ANALYSIS_SYSTEM_PROMPT = """You are analyzing code context to identify missing information. Your task is to determine what additional context would help answer the question more completely.

Always respond with valid JSON only, no other text."""

GAP_ANALYSIS_USER_PROMPT = """You analyzed code to answer this question: {question}

Sub-questions investigated:
{sub_questions}

Code context retrieved (summary):
{context_summary}

Identify what important information is still missing and generate 1-3 follow-up search queries to fill gaps.

If the context seems sufficient, return empty arrays.

Respond in this exact JSON format:
{{
  "gaps": ["description of what's missing"],
  "follow_up_queries": ["specific search query to find missing info"]
}}

Provide only the JSON, no other text."""


SYNTHESIS_SYSTEM_PROMPT = """You are a senior software engineer explaining code architecture. Provide clear, accurate answers based on the code context provided. Always cite specific files and line numbers when referencing code."""

SYNTHESIS_USER_PROMPT = """Answer this question about the codebase using the research findings below.

Original question: {question}

Research sub-questions investigated:
{sub_questions}

Code context (from {num_files} files, {num_chunks} code sections):

{full_context}

---

Provide a comprehensive answer that:
1. Directly addresses the original question
2. Explains the architectural reasoning
3. Cites specific files and line numbers (e.g., `file.py:42-50`)
4. Notes any limitations or uncertainties

Format your answer with clear sections if appropriate."""


class ReasoningMixin:
    """Mixin providing core reasoning methods for DeepResearchPipeline.

    These methods handle LLM interactions for question decomposition,
    gap analysis, synthesis, and vector store retrieval operations.

    Expects the following attributes on the host class:
        - llm: LLMProvider
        - vector_store: VectorStore
        - decomposition_prompt: str
        - gap_analysis_prompt: str
        - synthesis_prompt: str
        - max_sub_questions: int
        - max_follow_up_queries: int
        - chunks_per_subquestion: int
        - max_total_chunks: int
        - synthesis_temperature: float
        - synthesis_max_tokens: int
    """

    async def _decompose_question(self, question: str) -> list[SubQuestion]:
        """Decompose a complex question into sub-questions.

        Args:
            question: The original question.

        Returns:
            List of sub-questions to investigate.
        """
        prompt = DECOMPOSITION_USER_PROMPT.format(question=question)

        # Acquire rate limit before LLM call
        async with get_rate_limiter():
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=self.decomposition_prompt,
                temperature=0.3,  # Lower temperature for structured output
            )

        # Parse JSON response
        sub_questions = self._parse_decomposition_response(response)

        # Limit to max
        if len(sub_questions) > self.max_sub_questions:
            sub_questions = sub_questions[: self.max_sub_questions]

        return sub_questions

    def _parse_decomposition_response(self, response: str) -> list[SubQuestion]:
        """Parse the LLM decomposition response.

        Args:
            response: Raw LLM response.

        Returns:
            List of parsed SubQuestions.
        """
        try:
            # Try to extract JSON from the response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                logger.warning("No JSON found in decomposition response")
                return []

            data = json.loads(json_match.group())
            sub_questions = []

            for item in data.get("sub_questions", []):
                if isinstance(item, dict) and "question" in item:
                    category = item.get("category", "structure")
                    # Validate category
                    valid_categories = {
                        "structure",
                        "flow",
                        "dependencies",
                        "impact",
                        "comparison",
                    }
                    if category not in valid_categories:
                        category = "structure"
                    sub_questions.append(
                        SubQuestion(question=item["question"], category=category)
                    )

            return sub_questions

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse decomposition JSON: %s", e)
            return []

    async def _parallel_retrieve(
        self, sub_questions: list[SubQuestion]
    ) -> list[SearchResult]:
        """Retrieve code chunks for each sub-question in parallel.

        Args:
            sub_questions: List of sub-questions to search for.

        Returns:
            Combined list of search results.
        """
        if not sub_questions:
            return []

        # Create search tasks
        tasks = [
            self.vector_store.search(sq.question, limit=self.chunks_per_subquestion)
            for sq in sub_questions
        ]

        # Execute in parallel
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        all_results: list[SearchResult] = []
        for i, result_or_exc in enumerate(results_lists):
            if isinstance(
                result_or_exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)
            ):
                raise result_or_exc
            if isinstance(result_or_exc, BaseException):
                logger.warning(
                    "Search failed for sub-question %s: %s", i, result_or_exc
                )
                continue
            all_results.extend(result_or_exc)

        return all_results

    async def _analyze_gaps(
        self,
        question: str,
        sub_questions: list[SubQuestion],
        results: list[SearchResult],
    ) -> list[str]:
        """Analyze retrieved context for gaps.

        Args:
            question: Original question.
            sub_questions: Sub-questions investigated.
            results: Retrieved search results.

        Returns:
            List of follow-up queries to fill gaps.
        """
        if not results:
            # No results, generate basic follow-up
            return [question]

        # Build context summary
        context_summary = self._build_context_summary(results)
        sub_q_text = "\n".join(
            f"- [{sq.category}] {sq.question}" for sq in sub_questions
        )

        prompt = GAP_ANALYSIS_USER_PROMPT.format(
            question=question,
            sub_questions=sub_q_text,
            context_summary=context_summary,
        )

        # Acquire rate limit before LLM call
        async with get_rate_limiter():
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=self.gap_analysis_prompt,
                temperature=0.3,
            )

        # Parse response
        follow_ups = self._parse_gap_analysis_response(response)

        # Limit follow-up queries
        if len(follow_ups) > self.max_follow_up_queries:
            follow_ups = follow_ups[: self.max_follow_up_queries]

        return follow_ups

    def _build_context_summary(self, results: list[SearchResult]) -> str:
        """Build a summary of retrieved context for gap analysis.

        Args:
            results: Search results to summarize.

        Returns:
            String summary of the context.
        """
        if not results:
            return "No code context retrieved."

        # Group by file
        files: dict[str, list[SearchResult]] = {}
        for r in results:
            path = r.chunk.file_path
            if path not in files:
                files[path] = []
            files[path].append(r)

        summary_parts = []
        for path, file_results in files.items():
            chunks = ", ".join(
                f"{r.chunk.chunk_type.value} '{r.chunk.name or 'unnamed'}'"
                for r in file_results[:3]  # Limit per file
            )
            summary_parts.append(f"- {path}: {chunks}")

        return "\n".join(summary_parts[:10])  # Limit total files

    def _parse_gap_analysis_response(self, response: str) -> list[str]:
        """Parse the LLM gap analysis response.

        Args:
            response: Raw LLM response.

        Returns:
            List of follow-up queries.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            follow_ups = data.get("follow_up_queries", [])

            # Filter out empty strings
            return [q for q in follow_ups if q and isinstance(q, str)]

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse gap analysis JSON: %s", e)
            return []

    async def _targeted_retrieve(self, queries: list[str]) -> list[SearchResult]:
        """Perform targeted retrieval for follow-up queries.

        Args:
            queries: List of search queries.

        Returns:
            Combined search results.
        """
        if not queries:
            return []

        # Use slightly fewer chunks per query for follow-ups
        chunks_per_query = max(3, self.chunks_per_subquestion - 2)

        tasks = [
            self.vector_store.search(query, limit=chunks_per_query) for query in queries
        ]

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[SearchResult] = []
        for i, result_or_exc in enumerate(results_lists):
            if isinstance(
                result_or_exc,
                (asyncio.CancelledError, KeyboardInterrupt, SystemExit),
            ):
                raise result_or_exc
            if isinstance(result_or_exc, BaseException):
                logger.warning(
                    "Follow-up search failed for query %d: %s", i, result_or_exc
                )
                continue
            all_results.extend(result_or_exc)

        return all_results

    def _deduplicate_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Remove duplicate chunks, keeping highest-scoring ones.

        Args:
            results: List of search results.

        Returns:
            Deduplicated list sorted by score.
        """
        seen: dict[str, SearchResult] = {}

        for r in results:
            chunk_id = r.chunk.id
            if chunk_id not in seen or r.score > seen[chunk_id].score:
                seen[chunk_id] = r

        # Sort by score descending
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)

    async def _synthesize(
        self,
        question: str,
        sub_questions: list[SubQuestion],
        results: list[SearchResult],
    ) -> str:
        """Synthesize a comprehensive answer from all context.

        Args:
            question: Original question.
            sub_questions: Sub-questions investigated.
            results: All retrieved search results.

        Returns:
            Comprehensive answer string.
        """
        if not results:
            return (
                "I couldn't find relevant code context to answer this question. "
                "Please ensure the repository has been indexed."
            )

        # Build full context
        full_context = self._build_full_context(results)
        sub_q_text = "\n".join(
            f"- [{sq.category}] {sq.question}" for sq in sub_questions
        )

        # Count unique files
        unique_files = len(set(r.chunk.file_path for r in results))

        prompt = SYNTHESIS_USER_PROMPT.format(
            question=question,
            sub_questions=sub_q_text,
            num_files=unique_files,
            num_chunks=len(results),
            full_context=full_context,
        )

        # Acquire rate limit before LLM call
        async with get_rate_limiter():
            answer = await self.llm.generate(
                prompt=prompt,
                system_prompt=self.synthesis_prompt,
                temperature=self.synthesis_temperature,
                max_tokens=self.synthesis_max_tokens,
            )

        return answer

    def _build_full_context(self, results: list[SearchResult]) -> str:
        """Build full context string for synthesis.

        Args:
            results: Search results to include.

        Returns:
            Formatted context string.
        """
        context_parts = []

        for r in results:
            chunk = r.chunk
            header = f"File: {chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
            header += f" | Type: {chunk.chunk_type.value}"
            if chunk.name:
                header += f" | Name: {chunk.name}"

            context_parts.append(f"{header}\n```\n{chunk.content}\n```")

        return "\n\n---\n\n".join(context_parts)

    def _build_sources(self, results: list[SearchResult]) -> list[SourceReference]:
        """Build source references from search results.

        Args:
            results: Search results to convert.

        Returns:
            List of SourceReference objects.
        """
        return [
            SourceReference(
                file_path=r.chunk.file_path,
                start_line=r.chunk.start_line,
                end_line=r.chunk.end_line,
                chunk_type=r.chunk.chunk_type.value,
                name=r.chunk.name,
                relevance_score=r.score,
            )
            for r in results
        ]
