"""
Centralized configuration for NLI models.

This mirrors the embedding model configuration pattern and provides
safe, curated options for local NLI classifiers.
"""

from typing import List, Dict, TypedDict


class NLIModelInfo(TypedDict):
    """Information about an NLI model"""

    value: str
    label: str
    description: str


# IMPORTANT:
# - Only include models that are compatible with
#   AutoModelForSequenceClassification and do not require unsafe code
#   execution.
NLI_MODELS: List[NLIModelInfo] = [
    {
        "value": "cross-encoder/nli-deberta-v3-base",
        "label": "DeBERTa v3 Base (cross-encoder NLI)",
        "description": "Balanced speed and quality, good default choice.",
    },
    {
        "value": "cross-encoder/nli-roberta-base",
        "label": "RoBERTa Base (cross-encoder NLI)",
        "description": "Alternative NLI model based on RoBERTa.",
    },
]


FORM_OPTIONS_NLI: List[Dict[str, str]] = [
    {"value": model["value"], "label": model["label"]} for model in NLI_MODELS
]

DEFAULT_NLI_MODEL = "cross-encoder/nli-deberta-v3-base"
