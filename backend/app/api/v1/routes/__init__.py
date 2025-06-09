from fastapi import APIRouter

from app.api.v1.routes import agent_config, agent_knowledge, agent_tools, agents, api_keys, audit_logs, auth,conversations, datasources, llm_analysts, llm_providers, operators, permissions, recordings, role_permissions, roles, user_types, users, voice, app_settings, feature_flags, workflows, reports, zendesk


router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Auth"])
router.include_router(recordings.router, prefix="/audio", tags=["Audio"])
router.include_router(operators.router, prefix="/operators", tags=["Operators"])
router.include_router(users.router, prefix="/user", tags=["User"])
router.include_router(user_types.router, prefix="/user-type", tags=["UserTypes"])
router.include_router(roles.router, prefix="/roles", tags=["Roles"])
router.include_router(api_keys.router, prefix="/api-keys", tags=["ApiKeys"])
router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
router.include_router(role_permissions.router, prefix="/role-permissions", tags=["RolePermissions"])
router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
router.include_router(datasources.router, prefix="/datasources", tags=["Datasources"])
# router.include_router(conversation_analysis.router, prefix="/conversation-analysis", tags=["ConversationAnalysisRead"])
router.include_router(audit_logs.router, prefix="/audit-logs", tags=["Audit Logs"])
router.include_router(llm_providers.router, prefix="/llm-providers", tags=["LlmProviders"])
router.include_router(llm_analysts.router, prefix="/llm-analyst", tags=["LlmAnalyst"])
router.include_router(agents.router, prefix="/genagent/agents", tags=["agents"])
router.include_router(agent_config.router, prefix="/genagent/agents", tags=["agents"])
router.include_router(agent_knowledge.router, prefix="/genagent/knowledge", tags=["Knowledge Base"])
router.include_router(agent_tools.router, prefix="/genagent/tools", tags=["Tools"])
router.include_router(workflows.router, prefix="/genagent/workflow", tags=["Workflows"])
router.include_router(voice.router, prefix="/voice", tags=["Voice"])
router.include_router(app_settings.router, prefix="/app-settings", tags=["AppSettings"])
router.include_router(feature_flags.router, prefix="/feature-flags", tags=["FeatureFlags"])
router.include_router(reports.router, tags=["Reports"])
router.include_router(zendesk.router, prefix="/zendesk", tags=["Zendesk"])
