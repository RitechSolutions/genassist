import os
import logging

# Set tokenizers parallelism before importing any libraries that might use tokenizers
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures logs are sent to a file
    ]
)
logger = logging.getLogger(__name__)
logger.info("Application starting up")

from app.genagent.services.agent_config_service import AgentConfigService
from app.genagent.services.knowledge_service import KnowledgeService
from app.genagent.services.tool_service import ToolService
from app.genagent.agents.data.datasource_service import DataSourceService
from app.genagent.repositories.tool_repository import ToolRepository
from app.genagent.repositories.knowledge_repository import KnowledgeRepository
from app.genagent.agents.registry import AgentRegistry

# Singleton instances
_config_service = None
_datasource_service = None
_tool_repository = None
_knowledge_repository = None


def get_config_service() -> AgentConfigService:
    """Get or create the AgentConfigService singleton"""
    global _config_service
    if _config_service is None:
        _config_service = AgentConfigService()
    return _config_service

def get_tool_repository() -> ToolRepository:
    """Get or create the ToolRepository singleton"""
    global _tool_repository
    if _tool_repository is None:
        # Configure with default file path or from environment variable
        _tool_repository = ToolRepository(storage_type="file")
    return _tool_repository

def get_knowledge_repository() -> KnowledgeRepository:
    """Get or create the KnowledgeRepository singleton"""
    global _knowledge_repository
    if _knowledge_repository is None:
        _knowledge_repository = KnowledgeRepository(storage_type="file")
    return _knowledge_repository

def get_agent_registry() -> AgentRegistry:
    return AgentRegistry.get_instance()

async def get_datasource_service() -> DataSourceService:
    """Get or create the DataSourceService singleton"""
    global _datasource_service
    logger.info("Getting DataSourceService")
    if _datasource_service is None:
        _datasource_service = DataSourceService()
        logger.info("Initializing DataSourceService and loading knowledge base")
        await _datasource_service.load_knowledge_base()
    return _datasource_service

async def get_knowledge_service() -> KnowledgeService:
    """Get or create the KnowledgeService singleton"""
    repository = get_knowledge_repository()
    _knowledge_service = KnowledgeService(repository)
    return _knowledge_service

async def get_tool_service() -> ToolService:
    """Get or create the ToolService singleton"""

    repository = get_tool_repository()
    _tool_service = ToolService(repository=repository)
    return _tool_service






