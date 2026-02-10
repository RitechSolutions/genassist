"""
Permission constants for the application.

Each class represents a resource and defines its available permissions.
Use these constants in your route dependencies instead of hardcoded strings.

Example:
    from app.core.permissions.constants import Permissions as P

    @router.post("/", dependencies=[Depends(permissions(P.ApiKey.CREATE))])
    async def create_api_key(...):
        ...
"""


class AgentPermissions:
    """Agent-related permissions"""
    SWITCH = "switch:agent"


class ApiKeyPermissions:
    """API Key CRUD permissions"""
    CREATE = "create:api_key"
    READ = "read:api_key"
    UPDATE = "update:api_key"
    DELETE = "delete:api_key"


class AppSettingsPermissions:
    """Application settings permissions"""
    CREATE = "create:app_settings"
    READ = "read:app_settings"
    WRITE = "write:app_settings"
    UPDATE = "update:app_settings"
    DELETE = "delete:app_settings"


class AuditLogPermissions:
    """Audit log permissions"""
    READ = "read:audit_log"


class ConversationPermissions:
    """Conversation permissions"""
    READ = "read:conversation"
    CREATE_IN_PROGRESS = "create:in_progress_conversation"
    UPDATE_IN_PROGRESS = "update:in_progress_conversation"
    TAKEOVER_IN_PROGRESS = "takeover_in_progress_conversation"


class DataSourcePermissions:
    """Data source CRUD permissions"""
    CREATE = "create:data_source"
    READ = "read:data_source"
    UPDATE = "update:data_source"
    DELETE = "delete:data_source"


class FeatureFlagPermissions:
    """Feature flag CRUD permissions"""
    CREATE = "create:feature_flag"
    READ = "read:feature_flag"
    UPDATE = "update:feature_flag"
    DELETE = "delete:feature_flag"


class KnowledgeBasePermissions:
    """Knowledge base permissions"""
    UPDATE = "update:knowledge_base"


class LlmAnalystPermissions:
    """LLM Analyst CRUD permissions"""
    CREATE = "create:llm_analyst"
    READ = "read:llm_analyst"
    UPDATE = "update:llm_analyst"
    DELETE = "delete:llm_analyst"


class LlmProviderPermissions:
    """LLM Provider CRUD permissions"""
    CREATE = "create:llm_provider"
    READ = "read:llm_provider"
    UPDATE = "update:llm_provider"
    DELETE = "delete:llm_provider"


class MlModelPermissions:
    """ML Model CRUD permissions"""
    CREATE = "create:ml_model"
    READ = "read:ml_model"
    UPDATE = "update:ml_model"
    DELETE = "delete:ml_model"


class OperatorPermissions:
    """Operator permissions"""
    READ = "read:operator"
    UPDATE = "update:operator"


class PermissionPermissions:
    """Permission CRUD permissions (meta-permissions)"""
    CREATE = "create:permission"
    READ = "read:permission"
    UPDATE = "update:permission"
    DELETE = "delete:permission"


class RecordingPermissions:
    """Recording-related permissions"""
    READ = "read:recording"
    CREATE_ANALYZE = "create:analyze_recording"
    CREATE_UPLOAD_TRANSCRIPT = "create:upload_transcript"
    CREATE_ASK_QUESTION = "create:ask_question"
    READ_FILES = "read:files"
    READ_METRICS = "read:metrics"


class RolePermissions:
    """Role CRUD permissions"""
    CREATE = "create:role"
    READ = "read:role"
    UPDATE = "update:role"
    DELETE = "delete:role"


class RolePermissionPermissions:
    """Role-Permission relationship CRUD permissions"""
    CREATE = "create:role_permission"
    READ = "read:role_permission"
    UPDATE = "update:role_permission"
    DELETE = "delete:role_permission"


class TenantPermissions:
    """Tenant CRUD permissions"""
    CREATE = "create:tenant"
    READ = "read:tenant"
    UPDATE = "update:tenant"
    DELETE = "delete:tenant"


class UserPermissions:
    """User CRUD permissions"""
    CREATE = "create:user"
    READ = "read:user"
    UPDATE = "update:user"


class UserTypePermissions:
    """User type CRUD permissions"""
    CREATE = "create:user_type"
    READ = "read:user_type"
    UPDATE = "update:user_type"
    DELETE = "delete:user_type"


class WorkflowPermissions:
    """Workflow permissions"""
    CREATE = "create:workflow"
    READ = "read:workflow"
    UPDATE = "update:workflow"
    DELETE = "delete:workflow"
    EXECUTE = "execute:workflow"
    TEST = "test:workflow"


class OpenAIPermissions:
    """OpenAI fine-tuning permissions"""
    WRITE_FILE = "write:openai_file"
    READ_FILE = "read:openai_file"
    WRITE_JOB = "write:openai_job"
    READ_JOB = "read:openai_job"
    DELETE_FILE = "delete:openai-file"
    READ_FINE_TUNABLE_MODELS = "read:openai_fine_tunable_models"
    DELETE_FINE_TUNED_MODEL = "delete:openai_fine_tuned_model"

class CustomerPermissions:
    CREATE = "create:customer"
    READ = "read:customer"
    UPDATE = "update:customer"
    DELETE = "delete:customer"

class FileManagerPermissions:
    """File manager permissions"""
    READ = "read:file"
    CREATE = "create:file"
    UPDATE = "update:file"
    DELETE = "delete:file"

class Permissions:
    """
    Centralized access to all permission constants.

    Usage:
        from app.core.permissions.constants import Permissions as P

        # In routes
        @router.post("/", dependencies=[Depends(permissions(P.ApiKey.CREATE))])

        # In code
        if has_permission(user, P.LlmProvider.READ):
            ...
    """
    Agent = AgentPermissions
    ApiKey = ApiKeyPermissions
    AppSettings = AppSettingsPermissions
    AuditLog = AuditLogPermissions
    Conversation = ConversationPermissions
    DataSource = DataSourcePermissions
    FeatureFlag = FeatureFlagPermissions
    KnowledgeBase = KnowledgeBasePermissions
    LlmAnalyst = LlmAnalystPermissions
    LlmProvider = LlmProviderPermissions
    MlModel = MlModelPermissions
    Operator = OperatorPermissions
    Permission = PermissionPermissions
    Recording = RecordingPermissions
    Role = RolePermissions
    RolePermission = RolePermissionPermissions
    Tenant = TenantPermissions
    User = UserPermissions
    UserType = UserTypePermissions
    Workflow = WorkflowPermissions
    OpenAI = OpenAIPermissions
    Customer = CustomerPermissions
    FileManager = FileManagerPermissions


# Backwards compatibility: support "write:app_settings" style
class LegacyPermissions:
    """Legacy permission strings that don't follow standard naming"""
    WRITE_APP_SETTINGS = "write:app_settings"


def get_all_permission_constants() -> set[str]:
    """
    Get all permission string constants defined in this module.

    Returns:
        Set of all permission strings
    """
    all_perms = set()

    # Get all permission classes
    permission_classes = [
        AgentPermissions, ApiKeyPermissions, AppSettingsPermissions,
        AuditLogPermissions, ConversationPermissions, DataSourcePermissions,
        FeatureFlagPermissions, KnowledgeBasePermissions, LlmAnalystPermissions,
        LlmProviderPermissions, MlModelPermissions, OperatorPermissions,
        PermissionPermissions, RecordingPermissions, RolePermissions,
        RolePermissionPermissions, TenantPermissions, UserPermissions,
        UserTypePermissions, WorkflowPermissions, OpenAIPermissions,
        LegacyPermissions, FileManagerPermissions
    ]

    # Extract all string constants
    for perm_class in permission_classes:
        for attr_name in dir(perm_class):
            if not attr_name.startswith('_'):
                attr_value = getattr(perm_class, attr_name)
                if isinstance(attr_value, str):
                    all_perms.add(attr_value)

    return all_perms
