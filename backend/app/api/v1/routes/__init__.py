from fastapi import APIRouter

from app.api.v1.routes import (
    agent_config,
    agent_knowledge,
    agents,
    api_keys,
    audit_logs,
    auth,
    conversations,
    datasources,
    llm_analysts,
    llm_providers,
    open_ai_fine_tuning,
    operators,
    permissions,
    recordings,
    role_permissions,
    roles,
    twilio_agents,
    user_types,
    users,
    voice,
    app_settings,
    feature_flags,
    webhook,
    webhook_execute,
    workflows,
    reports,
    zendesk,
    gmail,
    office365,
    ml_models,
    ml_model_pipeline,
    playground,
    smb_share_router,
    tenants,
    azure_blob_router, 
    public_registration,
    workflow_manager,
    mcp,
    mcp_servers,
    customers,
    file_manager
)

# Disable redirect slashes for all routes
default_router_options = {
    "redirect_slashes": False
}

router = APIRouter(**default_router_options)

router.include_router(auth.router, prefix="/auth", tags=["Auth"])
router.include_router(users.router, prefix="/user", tags=["User"])
router.include_router(user_types.router, prefix="/user-type", tags=["UserTypes"])
router.include_router(roles.router, prefix="/roles", tags=["Roles"])
router.include_router(api_keys.router, prefix="/api-keys", tags=["ApiKeys"])
router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
router.include_router(
    role_permissions.router, prefix="/role-permissions", tags=["RolePermissions"]
)
router.include_router(app_settings.router, prefix="/app-settings", tags=["AppSettings"])
router.include_router(
    feature_flags.router, prefix="/feature-flags", tags=["FeatureFlags"]
)
router.include_router(audit_logs.router, prefix="/audit-logs", tags=["Audit Logs"])

router.include_router(datasources.router, prefix="/datasources", tags=["Datasources"])
router.include_router(recordings.router, prefix="/audio", tags=["Audio"])
router.include_router(operators.router, prefix="/operators", tags=["Operators"])
router.include_router(
    conversations.router, prefix="/conversations", tags=["Conversations"]
)
router.include_router(voice.router, prefix="/voice", tags=["Voice"])

# router.include_router(conversation_analysis.router, prefix="/conversation-analysis", tags=["ConversationAnalysisRead"])

router.include_router(
    llm_providers.router, prefix="/llm-providers", tags=["LlmProviders"]
)
router.include_router(llm_analysts.router, prefix="/llm-analyst", tags=["LlmAnalyst"])

router.include_router(agents.router, prefix="/genagent/agents", tags=["agents"])
router.include_router(agent_config.router, prefix="/genagent/agents", tags=["agents"])
router.include_router(
    agent_knowledge.router, prefix="/genagent/knowledge", tags=["Knowledge Base"]
)
router.include_router(workflows.router, prefix="/genagent/workflow", tags=["Workflows"])

router.include_router(reports.router, tags=["Reports"])

router.include_router(zendesk.router, prefix="/zendesk", tags=["Zendesk"])
router.include_router(gmail.router, prefix="/gmail", tags=["Gmail"])

router.include_router(office365.router, prefix="/office365", tags=["Office365"])
router.include_router(twilio_agents.router, prefix="/twilio", tags=["Twilio Agents"])
router.include_router(
    webhook.router, prefix="/webhooks", tags=["Webhook for Workflows"]
)
router.include_router(
    webhook_execute.router, prefix="/webhook/execute", tags=["Webhook Execution"]
)
router.include_router(
    file_manager.router, prefix="/file-manager", tags=["FileManager"]
)


router.include_router(ml_models.router, prefix="/ml-models", tags=["ML Models"])
router.include_router(ml_model_pipeline.router, prefix="/ml-models", tags=["ML Model Pipelines"])
router.include_router(playground.router, prefix="/playground", tags=["Playground"])

router.include_router(
    smb_share_router.router,
    prefix="/smb-share",
    tags=["SMB (Windows) share file/folder operations"],
)

router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])

router.include_router(open_ai_fine_tuning.router, prefix="/openai", tags=["OpenAI API"])

router.include_router(azure_blob_router.router, prefix="/azure-blob-storage", tags=["Azure Blob Storage"])

router.include_router(public_registration.router, prefix="/public-registration", tags=["Public Registration"])  
router.include_router(workflow_manager.router, prefix="/workflow-manager", tags=["Workflow Manager"])
router.include_router(mcp.router, prefix="/mcp", tags=["MCP"])
router.include_router(mcp_servers.router, prefix="/mcp-servers", tags=["MCP Servers"])
router.include_router(customers.router, prefix="/customers", tags=["Customers"])