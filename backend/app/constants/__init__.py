"""
Application-wide constants and configuration values.
"""

from .embedding_models import (
    EMBEDDING_MODELS,
    ALLOWED_MODEL_NAMES,
    MODELS_FOR_DOWNLOAD,
    FORM_OPTIONS_VECTOR,
    FORM_OPTIONS_LEGRA,
    DEFAULT_MODEL,
)
from .nli_models import NLI_MODELS, FORM_OPTIONS_NLI, DEFAULT_NLI_MODEL

__all__ = [
    "EMBEDDING_MODELS",
    "ALLOWED_MODEL_NAMES",
    "MODELS_FOR_DOWNLOAD",
    "FORM_OPTIONS_VECTOR",
    "FORM_OPTIONS_LEGRA",
    "DEFAULT_MODEL",
    "NLI_MODELS",
    "FORM_OPTIONS_NLI",
    "DEFAULT_NLI_MODEL",
]