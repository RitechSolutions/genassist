"""
Centralized constants for Bedrock (Amazon Nova) fine-tuning.

Kept out of the service so the model list and setting keys live in one place,
alongside the other model constants (see embedding_models.py, nli_models.py).
"""

# Amazon Nova models that can be fine-tuned and served on-demand.
# See AWS "Supported models and Regions for fine-tuning" (us-east-1).
# This is the zero-config fallback; the list can be overridden at runtime via an
# App Settings row (type="Other", name="BedrockFineTunableModels") without a deploy.
NOVA_FINE_TUNABLE_MODELS = [
    "amazon.nova-micro-v1:0:128k",
    "amazon.nova-lite-v1:0:300k",
    "amazon.nova-pro-v1:0:300k",
]

# App Settings row that overrides NOVA_FINE_TUNABLE_MODELS at runtime.
FINE_TUNABLE_MODELS_SETTING_TYPE = "Other"
FINE_TUNABLE_MODELS_SETTING_NAME = "BedrockFineTunableModels"

# Bedrock requires a non-empty hyperParameters map for Nova FINE_TUNING jobs.
# These are AWS's documented Nova SFT defaults (see custom-models-hp.html) and are
# applied whenever the user leaves a field blank. Values are strings because
# Bedrock expects string-valued hyperparameters.
NOVA_DEFAULT_HYPERPARAMETERS = {
    "epochCount": "1",
    "learningRate": "0.00001",
    "learningRateWarmupSteps": "10",
}

# Schema version required by Nova supervised fine-tuning JSONL training data.
NOVA_SCHEMA_VERSION = "bedrock-conversation-2024"