"""
Centralized constants for OpenAI fine-tuning.

Kept out of the service so the model list and setting keys live in one place,
alongside the other model constants (see embedding_models.py, bedrock_fine_tuning.py).
"""

# OpenAI base models that support (supervised) fine-tuning.
# See https://developers.openai.com/api/docs/guides/supervised-fine-tuning for the
# latest list. As of the 2026 platform wind-down, only the GPT-4.1 family is
# supported for new SFT jobs; the older gpt-4o / gpt-4 / gpt-3.5-turbo snapshots
# were retired for fine-tuning and cause OpenAI to 500 on job creation.
# This is the zero-config fallback; the list can be overridden at runtime via an
# App Settings row (type="Other", name="OpenAIFineTunableModels") without a deploy.
OPENAI_FINE_TUNABLE_MODELS = [
    "gpt-4.1-2025-04-14",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4.1-nano-2025-04-14",
]

# App Settings row that overrides OPENAI_FINE_TUNABLE_MODELS at runtime.
FINE_TUNABLE_MODELS_SETTING_TYPE = "Other"
FINE_TUNABLE_MODELS_SETTING_NAME = "OpenAIFineTunableModels"