"""Agentic handler data: tool graph, workflow presets, and shared constants."""

from __future__ import annotations

# --- Tool graph for suggest_next_actions ---

# Keywords per tool used for context-aware suggestion boosting (Item 5)
_TOOL_KEYWORDS: dict[str, list[str]] = {
    "detect_secrets": [
        "secret",
        "credential",
        "security",
        "vulnerability",
        "leak",
        "key",
        "token",
        "password",
    ],
    "get_complexity_metrics": [
        "complex",
        "complexity",
        "cyclomatic",
        "nesting",
        "refactor",
        "quality",
    ],
    "impact_analysis": [
        "change",
        "impact",
        "blast",
        "radius",
        "modify",
        "refactor",
        "risk",
        "breaking",
    ],
    "get_coverage": ["coverage", "documentation", "undocumented", "missing", "docs"],
    "detect_stale_docs": ["stale", "outdated", "update", "refresh", "drift"],
    "deep_research": [
        "research",
        "investigate",
        "understand",
        "architecture",
        "design",
        "how",
    ],
    "explain_entity": [
        "explain",
        "entity",
        "function",
        "class",
        "method",
        "what",
        "does",
    ],
    "search_code": ["find", "search", "locate", "where", "code", "function", "class"],
    "get_diagrams": [
        "diagram",
        "visualize",
        "chart",
        "mermaid",
        "class diagram",
        "dependency",
    ],
    "generate_codemap": [
        "flow",
        "execution",
        "trace",
        "codemap",
        "how does",
        "pipeline",
    ],
    "get_call_graph": ["call", "caller", "callee", "invoke", "call graph"],
    "get_test_examples": ["test", "example", "usage", "how to use"],
    "get_file_context": ["import", "file", "context", "role", "dependency"],
    "ask_question": ["question", "ask", "what", "why", "how", "explain"],
    "get_changelog": ["changelog", "history", "commit", "recent", "changes"],
    "fuzzy_search": ["fuzzy", "search", "find", "similar", "name"],
    "get_project_manifest": [
        "manifest",
        "package",
        "dependency",
        "version",
        "metadata",
    ],
    "analyze_diff": ["diff", "change", "commit", "pr", "pull request", "review"],
    "index_repository": ["index", "reindex", "rebuild", "generate"],
    "suggest_codemap_topics": ["topic", "discover", "explore", "flow", "entry point"],
    "analyze_architecture": [
        "architecture",
        "health",
        "analysis",
        "composite",
        "report",
        "grade",
        "score",
        "smells",
        "coupling",
        "complexity",
    ],
    "get_onboarding_guide": [
        "onboard",
        "onboarding",
        "getting started",
        "new developer",
        "orientation",
        "entry point",
        "overview",
    ],
    "get_recommendations": [
        "recommend",
        "recommendation",
        "refactor",
        "improve",
        "suggestion",
        "priority",
        "action",
        "fix",
    ],
    "get_architecture_trends": [
        "trend",
        "history",
        "health",
        "score",
        "grade",
        "snapshot",
        "over time",
    ],
}


# Phrases indicating an insufficient answer (for query_codebase escalation, Item 6)
_INSUFFICIENT_PHRASES = [
    "i don't have enough",
    "no relevant code found",
    "not found",
    "unable to determine",
    "cannot determine",
    "i'm not sure",
    "no information",
    "insufficient context",
    "no matching",
    "couldn't find",
    "no results",
]


def _answer_seems_insufficient(answer: str, question: str) -> bool:
    """Check if an answer seems insufficient and should trigger escalation.

    Uses keyword matching instead of raw length, avoiding false positives
    on concise but correct answers.

    Args:
        answer: The answer text from ask_question.
        question: The original question (unused for now, reserved for future use).

    Returns:
        True if the answer appears insufficient.
    """
    answer_lower = answer.lower()
    return any(phrase in answer_lower for phrase in _INSUFFICIENT_PHRASES)


TOOL_GRAPH: dict[str, list[dict[str, str]]] = {
    "index_repository": [
        {
            "tool": "read_wiki_structure",
            "reason": "Browse the generated wiki",
            "priority": "high",
        },
        {
            "tool": "get_wiki_stats",
            "reason": "Check wiki health and coverage",
            "priority": "high",
        },
        {
            "tool": "ask_question",
            "reason": "Ask questions about the codebase",
            "priority": "medium",
        },
    ],
    "ask_question": [
        {
            "tool": "explain_entity",
            "reason": "Deep-dive on a specific entity mentioned in the answer",
            "priority": "high",
        },
        {
            "tool": "deep_research",
            "reason": "Investigate the topic more thoroughly",
            "priority": "medium",
        },
        {
            "tool": "search_code",
            "reason": "Find related code snippets",
            "priority": "medium",
        },
    ],
    "search_code": [
        {
            "tool": "explain_entity",
            "reason": "Understand a found code entity",
            "priority": "high",
        },
        {
            "tool": "get_file_context",
            "reason": "See imports, callers, and related files",
            "priority": "high",
        },
        {
            "tool": "impact_analysis",
            "reason": "Assess blast radius of changes",
            "priority": "medium",
        },
    ],
    "read_wiki_structure": [
        {
            "tool": "read_wiki_page",
            "reason": "Read a specific wiki page",
            "priority": "high",
        },
        {
            "tool": "search_wiki",
            "reason": "Search across wiki content",
            "priority": "medium",
        },
        {
            "tool": "get_coverage",
            "reason": "Check documentation coverage",
            "priority": "low",
        },
    ],
    "explain_entity": [
        {
            "tool": "get_call_graph",
            "reason": "Visualize function call relationships",
            "priority": "high",
        },
        {
            "tool": "impact_analysis",
            "reason": "Assess change impact for this entity",
            "priority": "medium",
        },
        {
            "tool": "generate_codemap",
            "reason": "Trace execution flow through this entity",
            "priority": "medium",
        },
    ],
    "deep_research": [
        {
            "tool": "generate_codemap",
            "reason": "Visualize the execution flow",
            "priority": "high",
        },
        {
            "tool": "explain_entity",
            "reason": "Deep-dive on a specific entity",
            "priority": "medium",
        },
        {
            "tool": "search_code",
            "reason": "Find additional code context",
            "priority": "low",
        },
    ],
    "read_wiki_page": [
        {
            "tool": "explain_entity",
            "reason": "Understand an entity mentioned on the page",
            "priority": "high",
        },
        {
            "tool": "search_wiki",
            "reason": "Find related wiki pages",
            "priority": "medium",
        },
        {
            "tool": "get_file_context",
            "reason": "Explore the source file's role",
            "priority": "medium",
        },
    ],
    "generate_codemap": [
        {
            "tool": "explain_entity",
            "reason": "Deep-dive on a node in the codemap",
            "priority": "high",
        },
        {
            "tool": "impact_analysis",
            "reason": "Assess change impact for mapped code",
            "priority": "medium",
        },
        {
            "tool": "ask_question",
            "reason": "Ask follow-up questions about the flow",
            "priority": "medium",
        },
    ],
    "get_wiki_stats": [
        {
            "tool": "get_coverage",
            "reason": "Check documentation coverage details",
            "priority": "high",
        },
        {
            "tool": "detect_stale_docs",
            "reason": "Find outdated documentation",
            "priority": "medium",
        },
        {
            "tool": "suggest_codemap_topics",
            "reason": "Discover interesting code flows",
            "priority": "low",
        },
    ],
}


# --- Workflow presets ---

WORKFLOW_PRESETS = frozenset(
    {"onboarding", "security_audit", "full_analysis", "quick_refresh"}
)

# Workflow name -> module-level function name (looked up via globals() for mock-ability)
_WORKFLOW_RUNNER_NAMES: dict[str, str] = {
    "onboarding": "_run_onboarding",
    "security_audit": "_run_security_audit",
    "full_analysis": "_run_full_analysis",
    "quick_refresh": "_run_quick_refresh",
}
