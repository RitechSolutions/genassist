from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.recording import RecordingModel
from app.db.models.role import RoleModel
from app.db.models.permission import PermissionModel
from app.db.models.role_permission import RolePermissionModel
from app.db.models.user_type import UserTypeModel
from app.db.models.user_role import UserRoleModel
from app.db.models.user import UserModel
from app.db.models.llm import LlmAnalystModel, LlmProvidersModel
from app.db.models.job import JobModel
from app.db.models.job_logs import JobLogsModel
# from app.db.models.api_key_permission import ApiKeyPermissionModel
from app.db.models.api_key import ApiKeyModel
from app.db.models.audit_log import AuditLogModel
from app.db.models.api_key_role import ApiKeyRoleModel
from app.db.models.conversation import ConversationModel, ConversationAnalysisModel
from app.db.models.customer import CustomerModel
from app.db.models.datasource import DataSourceModel
from app.db.utils.event_hooks_config import auto_register_updated_by
from .agent import AgentModel
from .agent_security_settings import AgentSecuritySettingsModel
from .tool import ToolModel
from .knowledge_base import KnowledgeBaseModel
from .workflow import WorkflowModel
from .ml_model import MLModel
from .ml_model_pipeline import (
    MLModelPipelineConfig,
    MLModelPipelineRun,
    MLModelPipelineArtifact,
    PipelineRunStatus,
    ArtifactType
)
from .tenant import TenantModel
from .fine_tuning import FineTuningJobModel, OpenAIFileModel, FineTuningEventModel
from .app_settings import AppSettingsModel
from .webhook import WebhookModel
from .mcp_server import MCPServerModel, MCPServerWorkflowModel
__all__ = [
    # Primary model class names
    "OperatorModel",
    "OperatorStatisticsModel",
    "RecordingModel",
    "RoleModel",
    "PermissionModel",
    "RolePermissionModel",
    "UserTypeModel",
    "UserRoleModel",
    "UserModel",
    "LlmAnalystModel",
    "LlmProvidersModel",
    "JobModel",
    "JobLogsModel",
    #    "ApiKeyPermissionModel",
    "ApiKeyModel",
    "AuditLogModel",
    "ApiKeyRoleModel",
    "ConversationModel",
    "ConversationAnalysisModel",
    "CustomerModel",
    "DataSourceModel",
    "ToolModel",
    "KnowledgeBaseModel",
    "AgentModel",
    "AgentSecuritySettingsModel",
    "WorkflowModel",
    "MLModel",
    "MLModelPipelineConfig",
    "MLModelPipelineRun",
    "MLModelPipelineArtifact",
    "PipelineRunStatus",
    "ArtifactType",
    "TenantModel",
    "OpenAIFileModel",
    "FineTuningJobModel",
    "AppSettingsModel",
    "WebhookModel",
    "FineTuningEventModel",
    "MCPServerModel",
    "MCPServerWorkflowModel"
]

models = [
    ConversationModel,
    ConversationAnalysisModel,
    UserModel,
    RoleModel,
    PermissionModel,
    RolePermissionModel,
    RecordingModel,
    OperatorModel,
    OperatorStatisticsModel,
    LlmAnalystModel,
    LlmProvidersModel,
    JobLogsModel,
    JobModel,
    DataSourceModel,
    CustomerModel,
    ApiKeyModel,
    ApiKeyRoleModel,
    UserTypeModel,
    AuditLogModel,
    UserRoleModel,
    KnowledgeBaseModel,
    AgentModel,
    AgentSecuritySettingsModel,
    WorkflowModel,
    MLModel,
    MLModelPipelineConfig,
    MLModelPipelineRun,
    MLModelPipelineArtifact,
    TenantModel,
    AppSettingsModel,
    FineTuningEventModel,
    MCPServerModel,
    MCPServerWorkflowModel
]

auto_register_updated_by(models)
