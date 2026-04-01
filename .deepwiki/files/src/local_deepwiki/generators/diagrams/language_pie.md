# File: `src/local_deepwiki/generators/diagrams/language_pie.py`

## File Overview

This file is responsible for generating a Mermaid-formatted pie chart that visualizes the distribution of languages within an index. It provides a single function, `generate_language_pie_chart`, which takes an [`IndexStatus`](../../models/wiki.md) object and returns a string representation of a Mermaid pie chart. The chart is intended for use in documentation or reports to show how content is distributed across different languages.

The design rationale behind this file is to abstract the generation of a language distribution visualization into a reusable component. This allows other parts of the system to generate consistent visual representations of language data without needing to know the internal structure of the Mermaid syntax or how to sort and format language counts.

## Key Concepts

The key abstraction in this file is the `generate_language_pie_chart` function, which encapsulates the logic for:
- Checking whether language data is available (`index_status.languages`)
- Sorting languages by count in descending order for better visualization
- Formatting the output as a Mermaid pie chart block

The choice to use Mermaid for visualization aligns with the project's documentation generation pipeline, where Mermaid diagrams are commonly used for embedding diagrams in documentation. The sorting by count ensures that the most prevalent languages are shown first, improving readability of the chart.

## Integration

This file is integrated into the larger codebase via its dependency on [`IndexStatus`](../../models/wiki.md) from `local_deepwiki.models`, which suggests that it is part of a system that tracks indexing progress and status. The function `generate_language_pie_chart` is called from:
- `__init__`
- `generator_service`
- `test_diagrams_misc`

These call sites indicate that the pie chart generation is used during initialization, as part of a service that generates documentation, and in tests for diagram generation. The integration with [`IndexStatus`](../../models/wiki.md) implies that this file works closely with the indexing system, where language distribution data is tracked and made available for visualization.

## Design Notes

- **Edge Case Handling**: The function returns `None` if `index_status.languages` is empty, which gracefully handles cases where no language data is available.
- **Sorting Strategy**: Languages are sorted by count in descending order using `key=lambda x: -x[1]`. This ensures that the most frequent languages appear first in the chart, improving visual clarity.
- **Mermaid Format**: The output is formatted as a Mermaid block with proper fencing (```mermaid ... ```), making it directly embeddable in documentation systems that support Mermaid rendering.
- **Return Type**: The function returns `str | None`, indicating that it may return `None` when no language data is present. This type annotation reflects the optional nature of the output.

## API Reference

### Functions

#### `generate_language_pie_chart`

```python
def generate_language_pie_chart(index_status: IndexStatus) -> str | None
```

Generate a pie chart showing language distribution.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | `IndexStatus` | - | Index status with language counts. |

**Returns:** `str | None`




<details>
<summary>View Source (lines 8-27) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/diagrams/language_pie.py#L8-L27">GitHub</a></summary>

```python
def generate_language_pie_chart(index_status: IndexStatus) -> str | None:
    """Generate a pie chart showing language distribution.

    Args:
        index_status: Index status with language counts.

    Returns:
        Mermaid pie chart string, or None if no languages.
    """
    if not index_status.languages:
        return None

    lines = ["```mermaid", "pie title Language Distribution"]

    for lang, count in sorted(index_status.languages.items(), key=lambda x: -x[1]):
        lines.append(f'    "{lang}" : {count}')

    lines.append("```")

    return "\n".join(lines)
```

</details>

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `generate_language_pie_chart` | function | Brian Breidenbach | Feb 21, 2026 | `fecde6f` refactor: split 10 large fi... |

## Relevant Source Files

- `src/local_deepwiki/generators/diagrams/language_pie.py:8-27`
