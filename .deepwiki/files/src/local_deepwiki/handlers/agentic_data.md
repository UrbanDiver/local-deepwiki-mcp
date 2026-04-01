# File: `src/local_deepwiki/handlers/agentic_data.py`

## File Overview

This file serves as a data module for the agentic handler, containing shared constants, tool graph definitions, and workflow presets used by the agentic system. It is responsible for encapsulating the core data structures and logic that support the agentic retrieval and escalation behavior, particularly in determining when an answer is insufficient.

The module is designed to be imported and used by other components in the `local_deepwiki.handlers` package, especially those involved in processing user queries and managing the flow of information through a chain of tools or agents.

## Key Concepts

### Agentic Retrieval Logic

The module introduces a mechanism for detecting when an answer to a question is insufficient. This is implemented via the `_answer_seems_insufficient` function, which uses keyword matching rather than raw text length to avoid false positives on concise but accurate responses.

This approach was chosen to ensure that the system doesn't mistakenly escalate valid, short answers, such as "I don't know" or "I'm not sure," which may be perfectly appropriate for certain queries.

### Shared Constants

The file defines a list of phrases (`_INSUFFICIENT_PHRASES`) that are used to identify when an answer should be considered inadequate. These phrases are carefully selected to capture common patterns in low-quality or unhelpful responses, such as vague terms or expressions of uncertainty.

## Integration

This module is part of the `local_deepwiki.handlers` package and is likely imported by other modules within the same package, such as the main agentic handler or workflow managers. It provides shared data and logic that supports decision-making within the agentic retrieval pipeline, particularly in determining whether a retrieved answer should trigger further action or escalation.

The function `_answer_seems_insufficient` is a utility used by the agentic workflow to evaluate the quality of answers returned by the `ask_question` function. Its integration into the system allows for intelligent routing of queries based on the sufficiency of the retrieved information.

## Design Notes

### Escalation Logic

The design of `_answer_seems_insufficient` prioritizes accuracy over simplicity by using keyword matching instead of heuristics like word count or character length. This prevents false positives where a correct, brief answer might be incorrectly flagged as insufficient.

### Extensibility

The use of a constant list (`_INSUFFICIENT_PHRASES`) allows for easy extension or modification of the detection logic without changing the core function. This supports future updates to the agentic system's behavior without requiring deep changes to the logic.

### Reserved Parameters

The `question` parameter in `_answer_seems_insufficient` is currently unused but reserved for future use. This design choice allows for potential enhancements where the sufficiency of an answer might be evaluated in the context of the original query, such as checking for relevance or completeness.

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `_answer_seems_insufficient` | function | Brian Breidenbach | Feb 21, 2026 | `aad50cb` refactor: split 9 files (80... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_answer_seems_insufficient`

<details>
<summary>View Source (lines 157-171) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/handlers/agentic_data.py#L157-L171">GitHub</a></summary>

```python
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
```

</details>

## Relevant Source Files

- `src/local_deepwiki/handlers/agentic_data.py:157-171`
