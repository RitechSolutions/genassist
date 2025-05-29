LLM_FORM_SCHEMAS = {
    "openai": {
        "name": "OpenAI",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your OpenAI API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "gpt-3.5-turbo",
                "options": [
                    {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
                    {"value": "gpt-3.5-turbo-16k", "label": "GPT-3.5 Turbo 16K"},
                    {"value": "gpt-4o", "label": "GPT-4o"},
                    {"value": "gpt-4o-mini", "label": "GPT-4o Mini"},
                    {"value": "gpt-4", "label": "GPT-4"},
                    {"value": "gpt-4-32k", "label": "GPT-4 32K"},
                    {"value": "gpt-4-turbo-preview", "label": "GPT-4 Turbo Preview"},
                    {"value": "o1-mini", "label": "O1 Mini"},
                    {"value": "o1-small", "label": "O1 Small"},
                    {"value": "o1-medium", "label": "O1 Medium"},
                    {"value": "o1-large", "label": "O1 Large"}
                ]
            },
            {
                "name": "organization",
                "type": "text",
                "label": "Organization ID",
                "required": False,
                "description": "Your OpenAI organization ID (optional)"
            },
            {
                "name": "temperature",
                "type": "number",
                "label": "Temperature",
                "required": False,
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
                "description": "Controls randomness (0.0 to 2.0)"
            },
            {
                "name": "max_tokens",
                "type": "number",
                "label": "Max Tokens",
                "required": False,
                "default": 1024,
                "min": 1,
                "step": 1,
                "description": "Maximum number of tokens to generate"
            },
            {
                "name": "timeout",
                "type": "number",
                "label": "Timeout",
                "required": False,
                "default": 60,
                "min": 1,
                "step": 1,
                "description": "Maximum time in seconds to wait for response"
            },
            {
                "name": "max_retries",
                "type": "number",
                "label": "Max Retries",
                "required": False,
                "default": 3,
                "min": 0,
                "step": 1,
                "description": "Maximum number of retry attempts"
            }
        ]
    },
    "gemini": {
        "name": "Google Gemini",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Google AI API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "gemini-pro",
                "options": [
                    {"value": "gemini-pro", "label": "Gemini Pro"},
                    {"value": "gemini-pro-vision", "label": "Gemini Pro Vision"}
                ]
            },
            {
                "name": "project_id",
                "type": "text",
                "label": "Project ID",
                "required": False,
                "description": "Your Google Cloud project ID (optional)"
            },
            {
                "name": "temperature",
                "type": "number",
                "label": "Temperature",
                "required": False,
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
                "description": "Controls randomness (0.0 to 2.0)"
            },
            {
                "name": "max_tokens",
                "type": "number",
                "label": "Max Tokens",
                "required": False,
                "default": 1024,
                "min": 1,
                "step": 1,
                "description": "Maximum number of tokens to generate"
            }
        ]
    },
    "llama": {
        "name": "Llama",
        "fields": [
            {
                "name": "base_url",
                "type": "text",
                "label": "Base URL",
                "required": True,
                "description": "URL of your Llama server (e.g., http://localhost:8000)"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "llama-2-7b-chat",
                "options": [
                    {"value": "llama-2-7b-chat", "label": "Llama 2 7B Chat"},
                    {"value": "llama-2-13b-chat", "label": "Llama 2 13B Chat"},
                    {"value": "llama-2-70b-chat", "label": "Llama 2 70B Chat"},
                    {"value": "llama-2-7b-instruct", "label": "Llama 2 7B Instruct"},
                    {"value": "llama-2-13b-instruct", "label": "Llama 2 13B Instruct"},
                    {"value": "llama-2-70b-instruct", "label": "Llama 2 70B Instruct"}
                ]
            },
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": False,
                "description": "API key if your server requires authentication"
            },
            {
                "name": "context_window",
                "type": "number",
                "label": "Context Window",
                "required": False,
                "default": 4096,
                "min": 1,
                "step": 1,
                "description": "Maximum context window size"
            },
            {
                "name": "stop_sequences",
                "type": "tags",
                "label": "Stop Sequences",
                "required": False,
                "description": "Sequences that stop generation (e.g., </s>, Human:)"
            },
            {
                "name": "temperature",
                "type": "number",
                "label": "Temperature",
                "required": False,
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
                "description": "Controls randomness (0.0 to 2.0)"
            },
            {
                "name": "max_tokens",
                "type": "number",
                "label": "Max Tokens",
                "required": False,
                "default": 1024,
                "min": 1,
                "step": 1,
                "description": "Maximum number of tokens to generate"
            }
        ]
    },
    "mistral": {
        "name": "Mistral",
        "fields": [
            {
                "name": "base_url",
                "type": "text",
                "label": "Base URL",
                "required": True,
                "description": "URL of your Mistral server (e.g., http://localhost:8000)"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "mistral-7b-instruct",
                "options": [
                    {"value": "mistral-7b-instruct", "label": "Mistral 7B Instruct"},
                    {"value": "mistral-7b-instruct-v0.2", "label": "Mistral 7B Instruct v0.2"},
                    {"value": "mistral-small", "label": "Mistral Small"},
                    {"value": "mistral-medium", "label": "Mistral Medium"},
                    {"value": "mistral-large", "label": "Mistral Large"}
                ]
            },
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": False,
                "description": "API key if your server requires authentication"
            },
            {
                "name": "context_window",
                "type": "number",
                "label": "Context Window",
                "required": False,
                "default": 8192,
                "min": 1,
                "step": 1,
                "description": "Maximum context window size"
            },
            {
                "name": "stop_sequences",
                "type": "tags",
                "label": "Stop Sequences",
                "required": False,
                "description": "Sequences that stop generation (e.g., </s>, Human:)"
            },
            {
                "name": "temperature",
                "type": "number",
                "label": "Temperature",
                "required": False,
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
                "description": "Controls randomness (0.0 to 2.0)"
            },
            {
                "name": "max_tokens",
                "type": "number",
                "label": "Max Tokens",
                "required": False,
                "default": 1024,
                "min": 1,
                "step": 1,
                "description": "Maximum number of tokens to generate"
            }
        ]
    },
    "anthropic": {
        "name": "Anthropic",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Anthropic API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "claude-3-sonnet-20240229",
                "options": [
                    {"value": "claude-3-sonnet-20240229", "label": "Claude 3 Sonnet"},
                    {"value": "claude-3-opus-20240229", "label": "Claude 3 Opus"},
                    {"value": "claude-3-haiku-20240307", "label": "Claude 3 Haiku"}
                ]
            },
            {
                "name": "temperature",
                "type": "number",
                "label": "Temperature",
                "required": False,
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
                "description": "Controls randomness (0.0 to 2.0)"
            },
            {
                "name": "max_tokens",
                "type": "number",
                "label": "Max Tokens",
                "required": False,
                "default": 1024,
                "min": 1,
                "step": 1,
                "description": "Maximum number of tokens to generate"
            }
        ]
    },
    "azure_openai": {
        "name": "Azure OpenAI",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Azure OpenAI API key"
            },
            {
                "name": "base_url",
                "type": "text",
                "label": "Base URL",
                "required": True,
                "description": "Your Azure OpenAI endpoint URL"
            },
            {
                "name": "deployment_name",
                "type": "text",
                "label": "Deployment Name",
                "required": True,
                "description": "Your Azure OpenAI deployment name"
            },
            {
                "name": "api_version",
                "type": "text",
                "label": "API Version",
                "required": True,
                "default": "2024-02-15-preview",
                "description": "Azure OpenAI API version"
            }
        ]
    },
    "google_vertexai": {
        "name": "Google Vertex AI",
        "fields": [
            {
                "name": "project_id",
                "type": "text",
                "label": "Project ID",
                "required": True,
                "description": "Your Google Cloud project ID"
            },
            {
                "name": "location",
                "type": "text",
                "label": "Location",
                "required": True,
                "default": "us-central1",
                "description": "Google Cloud location"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "gemini-pro",
                "options": [
                    {"value": "gemini-pro", "label": "Gemini Pro"},
                    {"value": "gemini-pro-vision", "label": "Gemini Pro Vision"}
                ]
            }
        ]
    },
    "cohere": {
        "name": "Cohere",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Cohere API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "command",
                "options": [
                    {"value": "command", "label": "Command"},
                    {"value": "command-light", "label": "Command Light"},
                    {"value": "command-r", "label": "Command R"},
                    {"value": "command-r-plus", "label": "Command R Plus"}
                ]
            }
        ]
    },
    "bedrock": {
        "name": "Amazon Bedrock",
        "fields": [
            {
                "name": "aws_access_key_id",
                "type": "password",
                "label": "AWS Access Key ID",
                "required": True,
                "description": "Your AWS Access Key ID"
            },
            {
                "name": "aws_secret_access_key",
                "type": "password",
                "label": "AWS Secret Access Key",
                "required": True,
                "description": "Your AWS Secret Access Key"
            },
            {
                "name": "region_name",
                "type": "text",
                "label": "Region",
                "required": True,
                "default": "us-east-1",
                "description": "AWS region name"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "anthropic.claude-3-sonnet-20240229-v1:0",
                "options": [
                    {"value": "anthropic.claude-3-sonnet-20240229-v1:0", "label": "Claude 3 Sonnet"},
                    {"value": "anthropic.claude-3-opus-20240229-v1:0", "label": "Claude 3 Opus"},
                    {"value": "anthropic.claude-3-haiku-20240307-v1:0", "label": "Claude 3 Haiku"},
                    {"value": "amazon.titan-text-express-v1", "label": "Titan Text Express"},
                    {"value": "meta.llama2-13b-chat-v1", "label": "Llama 2 13B Chat"},
                    {"value": "meta.llama2-70b-chat-v1", "label": "Llama 2 70B Chat"}
                ]
            }
        ]
    },
    "mistralai": {
        "name": "Mistral AI",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Mistral AI API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "mistral-small",
                "options": [
                    {"value": "mistral-small", "label": "Mistral Small"},
                    {"value": "mistral-medium", "label": "Mistral Medium"},
                    {"value": "mistral-large", "label": "Mistral Large"}
                ]
            }
        ]
    },
    "groq": {
        "name": "Groq",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Groq API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "llama2-70b-4096",
                "options": [
                    {"value": "llama2-70b-4096", "label": "Llama 2 70B"},
                    {"value": "mixtral-8x7b-32768", "label": "Mixtral 8x7B"}
                ]
            }
        ]
    },
    "ollama": {
        "name": "Ollama",
        "fields": [
            {
                "name": "base_url",
                "type": "text",
                "label": "Base URL",
                "required": True,
                "default": "http://localhost:11434",
                "description": "URL of your Ollama server"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "llama2",
                "options": [
                    {"value": "llama2", "label": "Llama 2"},
                    {"value": "mistral:7b", "label": "Mistral 7B"},

                    {"value": "mistral:7b-instruct", "label": "Mistral 7B Instruct"},
                    {"value": "mistral:7b-instruct-v0.2", "label": "Mistral 7B Instruct v0.2"},
                    {"value": "codellama", "label": "CodeLlama"},
                    {"value": "neural-chat", "label": "Neural Chat"},
                    {"value": "starling-lm", "label": "Starling LM"}
                ]
            }
        ]
    },
    "perplexity": {
        "name": "Perplexity",
        "fields": [
            {
                "name": "api_key",
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Your Perplexity API key"
            },
            {
                "name": "model",
                "type": "select",
                "label": "Model",
                "required": True,
                "default": "sonar-small-chat",
                "options": [
                    {"value": "sonar-small-chat", "label": "Sonar Small Chat"},
                    {"value": "sonar-medium-chat", "label": "Sonar Medium Chat"},
                    {"value": "sonar-small-online", "label": "Sonar Small Online"},
                    {"value": "sonar-medium-online", "label": "Sonar Medium Online"}
                ]
            }
        ]
    }
}
