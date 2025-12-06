from contextlib import asynccontextmanager
from injector import Module, provider, singleton
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_injector import request_scope
from fastapi_injector import RequestScopeFactory
from app.core.tenant_scope import tenant_scope
from app.repositories.transcript_message import TranscriptMessageRepository
from app.repositories.tenant import TenantRepository
from app.services.tenant import TenantService
from app.services.transcript_message_service import TranscriptMessageService
from app.services.workflow import WorkflowService
from app.services.users import UserService
from app.services.user_types import UserTypesService
from app.services.roles import RolesService
from app.services.role_permissions import RolePermissionsService
from app.services.permissions import PermissionsService
from app.services.operators import OperatorService
from app.services.operator_statistics import OperatorStatisticsService
from app.services.llm_providers import LlmProviderService
from app.services.llm_analysts import LlmAnalystService
from app.services.gpt_speaker_separator import SpeakerSeparator
from app.services.gpt_questions import QuestionAnswerer
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.feature_flag import FeatureFlagService
from app.services.datasources import DataSourceService
from app.services.conversations import ConversationService
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.auth import AuthService
from app.services.audit_logs import AuditLogService
from app.services.audio import AudioService
from app.services.app_settings import AppSettingsService
from app.services.api_keys import ApiKeysService
from app.services.agent_tool import ToolService
from app.repositories.tool import ToolRepository
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.agent_config import AgentConfigService
from app.repositories.workflow import WorkflowRepository
from app.repositories.users import UserRepository
from app.repositories.user_types import UserTypesRepository
from app.repositories.roles import RolesRepository
from app.repositories.role_permissions import RolePermissionsRepository
from app.repositories.recordings import RecordingsRepository
from app.repositories.permissions import PermissionsRepository
from app.repositories.operators import OperatorRepository
from app.repositories.operator_statistics import OperatorStatisticsRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.feature_flag import FeatureFlagRepository
from app.repositories.datasources import DataSourcesRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.api_keys import ApiKeysRepository
from app.repositories.agent import AgentRepository
from app.db.multi_tenant_session import multi_tenant_manager
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.workflow.registry import AgentRegistry
from app.modules.workflow.llm.provider import LLMProvider
from app.cache.redis_connection_manager import RedisConnectionManager
from app.modules.data.manager import AgentRAGServiceManager
from app.core.config.settings import settings


logger = logging.getLogger(__name__)


class Dependencies(Module):

    # ------------------------------------------------------------------
    # PROVIDERS  (must be class methods,)
    # ------------------------------------------------------------------
    # @provider
    # @singleton
    # def provide_session_factory(self) -> async_sessionmaker:
    #     # Use multi-tenant session manager
    #     return multi_tenant_manager.get_master_session_factory()

    @provider
    @singleton
    async def provide_redis_connection_manager(self) -> RedisConnectionManager:
        """Provide Redis connection manager as a global singleton."""
        manager = RedisConnectionManager()
        await manager.initialize()
        return manager

    @provider
    @request_scope
    def provide_session(
        self,
    ) -> AsyncSession:
        """
        Provide tenant-aware session based on tenant context.

        Returns an AsyncSession instance managed by fastapi-injector's request scope.
        """
        from app.core.tenant_scope import get_tenant_context

        tenant_id = get_tenant_context()
        logger.debug(f"DI: Tenant context: {tenant_id}")

        session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

        return session_factory()

    def configure(self, binder):
        binder.bind(ToolService, scope=request_scope)
        binder.bind(ToolRepository, scope=request_scope)

        binder.bind(KnowledgeBaseService, scope=request_scope)
        binder.bind(KnowledgeBaseRepository, scope=request_scope)

        binder.bind(WorkflowService, scope=request_scope)
        binder.bind(WorkflowRepository, scope=request_scope)

        binder.bind(OperatorService, scope=request_scope)
        binder.bind(OperatorRepository, scope=request_scope)

        binder.bind(OperatorStatisticsService, scope=request_scope)
        binder.bind(OperatorStatisticsRepository, scope=request_scope)

        binder.bind(AgentRepository, scope=request_scope)
        binder.bind(AgentConfigService, scope=request_scope)

        binder.bind(UserService, scope=request_scope)
        binder.bind(UserRepository, scope=request_scope)

        binder.bind(UserTypesService, scope=request_scope)
        binder.bind(UserTypesRepository, scope=request_scope)

        binder.bind(ApiKeysService, scope=request_scope)
        binder.bind(ApiKeysRepository, scope=request_scope)

        binder.bind(AppSettingsService, scope=request_scope)
        binder.bind(AppSettingsRepository, scope=request_scope)

        binder.bind(AuditLogService, scope=request_scope)
        binder.bind(AuditLogRepository, scope=request_scope)

        binder.bind(ConversationService, scope=request_scope)
        binder.bind(ConversationRepository, scope=request_scope)

        binder.bind(ConversationAnalysisService, scope=request_scope)
        binder.bind(ConversationAnalysisRepository, scope=request_scope)

        binder.bind(TranscriptMessageService, scope=request_scope)
        binder.bind(TranscriptMessageRepository, scope=request_scope)

        binder.bind(AuthService, scope=request_scope)

        binder.bind(DataSourceService, scope=request_scope)
        binder.bind(DataSourcesRepository, scope=request_scope)

        binder.bind(FeatureFlagService, scope=request_scope)
        binder.bind(FeatureFlagRepository, scope=request_scope)

        binder.bind(LlmProviderService, scope=request_scope)
        binder.bind(LlmProviderRepository, scope=request_scope)

        binder.bind(LlmAnalystService, scope=request_scope)
        binder.bind(LlmAnalystRepository, scope=request_scope)

        binder.bind(PermissionsService, scope=request_scope)
        binder.bind(PermissionsRepository, scope=request_scope)

        binder.bind(AudioService, scope=request_scope)
        binder.bind(RecordingsRepository, scope=request_scope)

        binder.bind(RolesService, scope=request_scope)
        binder.bind(RolesRepository, scope=request_scope)

        binder.bind(RolePermissionsService, scope=request_scope)
        binder.bind(RolePermissionsRepository, scope=request_scope)

        binder.bind(
            GptKpiAnalyzer,  # the interface / type
            to=GptKpiAnalyzer,  # how to build it (here: call the ctor)
            scope=request_scope,
        )

        binder.bind(SpeakerSeparator, to=SpeakerSeparator, scope=request_scope)

        binder.bind(
            QuestionAnswerer,
            to=QuestionAnswerer(
                llm_model=settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature=0.0
            ),
            scope=request_scope,
        )

        # Agent & Workflow Services (Tenant-aware singletons)
        # These are tenant-scoped to ensure isolation between tenants:
        # - AgentRegistry: Each tenant has their own agent registry with isolated agents
        # - LLMProvider: Each tenant may have different LLM configurations/API keys
        # - AgentRAGServiceManager: Each tenant has their own RAG service cache to prevent KB ID collisions
        # - ThreadScopedRAG: Each tenant has their own per-chat RAG instance
        from app.modules.workflow.agents.rag import ThreadScopedRAG

        binder.bind(AgentRegistry, scope=tenant_scope)
        binder.bind(LLMProvider, scope=tenant_scope)
        binder.bind(AgentRAGServiceManager, scope=tenant_scope)
        binder.bind(ThreadScopedRAG, scope=tenant_scope)

        # Global singletons (shared across all tenants)
        # - SocketConnectionManager: Global singleton with tenant-aware room IDs
        #   (Tenant isolation achieved via room ID prefixes: tenant_{id}_room_id)
        # - RedisConnectionManager: Connection pool is stateless, shared across tenants
        #   (Tenant isolation achieved via key prefixes in Redis keys)
        # - RequestScopeFactory: Infrastructure for creating request scopes
        binder.bind(SocketConnectionManager, scope=singleton)
        binder.bind(RedisConnectionManager, scope=singleton)
        binder.bind(RequestScopeFactory, scope=singleton)

        binder.bind(logging.Logger, to=lambda: logging.getLogger(), scope=request_scope)

        # Multi-tenant services
        binder.bind(TenantService, scope=request_scope)
        binder.bind(TenantRepository, scope=request_scope)
