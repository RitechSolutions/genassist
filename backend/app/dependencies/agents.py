<<<<<<< HEAD
from functools import lru_cache
import os

from app.schemas.agent_config import AgentConfig
# Set tokenizers parallelism before importing any libraries that might use tokenizers
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from app.repositories.file_repository import FileRepository
from app.services.agent_config import AgentConfigService
from app.modules.agents.data.datasource_service import DataSourceService
=======
import os

from app.db.session import get_db
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.agent_knowledge import KnowledgeBaseService
# Set tokenizers parallelism before importing any libraries that might use tokenizers
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from app.modules.agents.data.datasource_service import AgentDataSourceService
>>>>>>> development
from app.modules.agents.registry import AgentRegistry

from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.gpt_questions import QuestionAnswerer
from app.services.gpt_speaker_separator import SpeakerSeparator
<<<<<<< HEAD
from functools import lru_cache
=======
>>>>>>> development
from app.core.config.settings import settings


def get_agent_registry() -> AgentRegistry:
    return AgentRegistry.get_instance()

<<<<<<< HEAD
# @lru_cache()
def get_agent_config_service() -> AgentConfigService:
    repository = FileRepository("agents_config/agent_config.json", AgentConfig)
    _config_service = AgentConfigService(repository)
    return _config_service

# @lru_cache()
async def get_datasource_service() -> DataSourceService:
    _datasource_service = DataSourceService()
    await _datasource_service.load_knowledge_base()
    return _datasource_service


# # @lru_cache()
# async def get_knowledge_service() -> KnowledgeService:
#     repository = FileRepository("agents_config/knowledge_base.json", KnowledgeItem)
#     _knowledge_service = KnowledgeService(repository)
#     return _knowledge_service

# # @lru_cache()
# async def get_tool_service() -> ToolService:
#     repository = FileRepository("agents_config/tools.json", ToolConfig)
#     _tool_service = ToolService(repository=repository)
#     return _tool_service


def get_speaker_separator() -> SpeakerSeparator:
    return SpeakerSeparator(model_name=settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature=0.0)


def get_gpt_kpi_analyzer() -> GptKpiAnalyzer:
    return GptKpiAnalyzer(model_name=settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature=0.0)


def get_question_answerer_service() -> QuestionAnswerer:
    return QuestionAnswerer(model_name=settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature=0.0)








=======

# async def build_agent_config_service() -> AgentConfigService:
#     # ── repositories ────────────────────────────────────────────────
#     async for db in get_db():
#         agent_repository = AgentRepository(db=db)
#         kb_repo = KnowledgeBaseRepository(db=db)
#         operator_repo = OperatorRepository(db=db)
#         user_repo = UserRepository(db=db)
#         user_types_repo = UserTypesRepository(db=db)
#         conversation_repo = ConversationRepository(db=db)
#
#         # ── nested services ─────────────────────────────────────────────
#         kb_service = KnowledgeBaseService(repository=kb_repo)
#
#         operator_service = OperatorService(
#                 operator_repository=operator_repo,
#                 user_repository=user_repo,
#                 user_types_repository=user_types_repo,
#                 conversation_repository=conversation_repo,
#                 )
#
#         # ── the top-level service we’ll return ───────────────────────────
#         return AgentConfigService(
#                 repository=agent_repository,
#                 knowledge_base_service=kb_service,
#                 agent_data_sources_service= await get_agent_datasource_service(),
#                 operator_service=operator_service,
#                 user_types_repository=user_types_repo,
#                 db=db,  # AgentConfigService itself takes the session too
#                 )
#     return None



# @lru_cache()
async def get_agent_datasource_service() -> AgentDataSourceService:
    return AgentDataSourceService.get_instance()


# async def get_knowledge_service() -> KnowledgeBaseService:
#     async for db in get_db():
#         repository = KnowledgeBaseRepository(db)
#         _knowledge_service = KnowledgeBaseService(repository)
#         return _knowledge_service

def get_speaker_separator() -> SpeakerSeparator:
    return SpeakerSeparator()


def get_gpt_kpi_analyzer() -> GptKpiAnalyzer:
    return GptKpiAnalyzer()


def get_question_answerer_service() -> QuestionAnswerer:
    return QuestionAnswerer(llm_model=settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature=0.0)
>>>>>>> development
