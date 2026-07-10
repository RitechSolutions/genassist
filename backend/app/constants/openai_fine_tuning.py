"""
Centralized constants for OpenAI fine-tuning.

Kept out of the service so the model list and setting keys live in one place,
alongside the other model constants (see embedding_models.py, bedrock_fine_tuning.py).
"""

# OpenAI base models that support fine-tuning.
# See https://platform.openai.com/docs/guides/fine-tuning for the latest list.
# This is the zero-config fallback; the list can be overridden at runtime via an
# App Settings row (type="Other", name="OpenAIFineTunableModels") without a deploy.
OPENAI_FINE_TUNABLE_MODELS = [
    "gpt-4o-2024-08-06",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-0613",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0613",
]

# App Settings row that overrides OPENAI_FINE_TUNABLE_MODELS at runtime.
FINE_TUNABLE_MODELS_SETTING_TYPE = "Other"
FINE_TUNABLE_MODELS_SETTING_NAME = "OpenAIFineTunableModels"