import asyncio
from typing import Dict, List
import os
import logging
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.core.utils.encryption_utils import decrypt_key
from app.db.models.llm import LlmProvidersModel
from app.db.session import get_db
from app.modules.agents.llm.supported_configuration import LLM_FORM_SCHEMAS
from app.repositories.llm_providers import LlmProviderRepository
from app.services.llm_providers import LlmProviderService

logger = logging.getLogger(__name__)


class LLMProvider:
    """Singleton class for managing LLM instances"""
    
    llm_instances: Dict[str, BaseChatModel] = {}
    configurations: List[LlmProvidersModel] = []
    
    _instance = None

    @staticmethod
    def get_instance() -> 'LLMProvider':
        if LLMProvider._instance is None:
            LLMProvider._instance = LLMProvider()
        return LLMProvider._instance

    def __init__(self):
        self.llm_instances = {}
        logger.info("LLMProvider initialized")
        asyncio.create_task(self.reload())
    
    def get_configuration_definitions(self) -> List[LlmProvidersModel]:
        """
        Get all LLM configurations
        """
        return LLM_FORM_SCHEMAS
    
    async def reload(self) -> List[LlmProvidersModel]:
        """
        Get all LLM configurations
        
        Returns:
            List[LlmProvidersModel]: All LLM configurations
        """
        async for db in get_db():
            service = LlmProviderService(repository=LlmProviderRepository(db))
            self.configurations = await service.get_all()
            self.llm_instances = {}
            logger.info(f"Reloaded {len(self.configurations)} LLM configurations")
            logger.info(f"Reloaded: {[model.id for model in self.configurations]}")

            return self.configurations
    
    def get_all_configurations(self) -> List[LlmProvidersModel]:
        """
        Get all LLM configurations
        
        Returns:
            List[LlmProvidersModel]: All LLM configurations
        """
        return self.configurations
    
    def get_configuration(self, model_id: str) -> LlmProvidersModel:
        """
        Get an LLM configuration by its ID
        """
        default = next((c for c in self.configurations if c.is_default==1), self.configurations[0])
        return next((c for c in self.configurations if str(c.id) == model_id), default)
    

    def get_model(self, model_id: str) -> BaseChatModel:
        """
        Get an LLM instance by its ID
        
        Args:
            model_id: ID of the LLM instance to get
            
        Returns:
            BaseChatModel: The LLM instance
            
        Raises:
            ValueError: If no configuration exists for the given ID
        """
        logger.info(f"Getting configurations {self.configurations}")
        if model_id not in self.llm_instances:
            # Find the configuration
            config = self.get_configuration(model_id)
            if not config:
                raise ValueError(f"No configuration found for model ID: {model_id}")
            
            try:
                # Validate connection data
                validated_data = config.connection_data
                validated_data.pop('masked_api_key', None)
                if 'api_key' in validated_data:
                    validated_data['api_key'] = decrypt_key(validated_data['api_key'])
                # Set up environment variables if needed
                if config.llm_model_provider.lower() == "openai":
                    os.environ["OPENAI_API_KEY"] = validated_data['api_key']
                    if validated_data.get('organization'):
                        os.environ["OPENAI_ORG_ID"] = validated_data['organization']
                
                # Initialize the model with provider-specific configuration
                model_kwargs = {
                    "model_provider": config.llm_model_provider.lower(),
                    "model": config.llm_model,
                    **validated_data
                }
                logger.info(f"Model kwargs: {model_kwargs}")
                
                # Initialize the model
                llm = init_chat_model(**model_kwargs)
                
                self.llm_instances[model_id] = llm
                logger.info(f"Created new LLM instance with ID: {model_id}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM instance: {str(e)}")
                raise
        
        return self.llm_instances[model_id]
    