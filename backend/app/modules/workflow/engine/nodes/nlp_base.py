"""
Shared, dependency-free NLP helpers for the lightweight AI workflow nodes.

These utilities are used by the classifier, sentiment/urgency, entity extractor
and summarizer nodes to robustly parse structured JSON returned by an LLM.
"""

import json
import re


def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences (```json ... ``` or ``` ... ```) from LLM output.

    Args:
        text: Raw text that may be wrapped in Markdown code fences.

    Returns:
        The text with any surrounding code fences removed and stripped.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # Remove a leading fence like ```json or ```
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
    # Remove a trailing fence
    cleaned = re.sub(r"\s*```$", "", cleaned)

    return cleaned.strip()


def parse_json_object(text: str) -> dict | None:
    """Strip code fences then parse the text as a JSON object.

    Args:
        text: Raw text (optionally fenced) expected to contain a JSON object.

    Returns:
        The parsed dict, or None if parsing fails or the result is not a dict.
    """
    cleaned = strip_code_fences(text)
    if not cleaned:
        return None

    try:
        parsed = json.loads(cleaned)
    except (ValueError, TypeError):
        return None

    return parsed if isinstance(parsed, dict) else None
