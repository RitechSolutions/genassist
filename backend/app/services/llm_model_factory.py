from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey
from app.core.utils.encryption_utils import decrypt_key
from app.schemas.llm import LlmAnalyst
import logging


logger = logging.getLogger(__name__)


class LlmModelFactory:
    @staticmethod
    def switch_model(llm_analyst: LlmAnalyst) -> BaseChatModel:
        """
        Given an LlmAnalyst, return the appropriate LangChain Chat model.
        """
        logger.info(
            f"Using LLM {llm_analyst.llm_provider.llm_model_provider} model: {llm_analyst.llm_provider.llm_model}")

        provider = llm_analyst.llm_provider.llm_model_provider.lower()
        model = llm_analyst.llm_provider.llm_model
        connection_data = llm_analyst.llm_provider.connection_data
        temperature = connection_data.get("temperature", 0)
        thinking_level = connection_data.get("thinking_level", "high")

        if provider == "openai":
            api_key = decrypt_key(connection_data.get("api_key"))
            return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)

        elif provider == "anthropic":
            api_key = decrypt_key(connection_data.get("api_key"))
            return ChatAnthropic(model_name=model, temperature=temperature, api_key=api_key)

        elif provider == "google_genai":
            api_key = decrypt_key(connection_data.get("api_key"))
            return ChatGoogleGenerativeAI(model=model, temperature=temperature, thinking_level=thinking_level,
                                          api_key=api_key)

        elif provider == "ollama":
            # Ollama doesn't need API key, but uses base_url for local server
            base_url = connection_data.get("base_url", "http://localhost:11434")
            return ChatOllama(
                    model=model,
                    temperature=temperature,
                    base_url=base_url
                    )
        elif provider == "vllm":
            # vLLM uses OpenAI-compatible API
            base_url = connection_data.get("base_url", "http://localhost:8976/v1")

            # vLLM uses OpenAI-compatible API, so we need to decrypt the API key
            api_key = decrypt_key(connection_data.get("api_key"))

            return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    openai_api_base=base_url,
                    temperature=temperature,
                    )

        else:
            raise AppException(error_key=ErrorKey.PROVIDER_NOT_SUPPORTED)
