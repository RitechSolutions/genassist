"""
Tenant resources the Workflow Builder can attach to nodes.

A person asks for "the Northstar knowledge base" or "our Zendesk"; the node
needs an id. This lists what exists (id, name, type only, never credentials)
so the builder can fill those fields itself instead of leaving every workflow
half configured.
"""

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

KINDS = {
    "knowledge_bases": "set as knowledgeBaseNode.selectedBases (a list of ids)",
    "integrations": "set as app_settings_id on Zendesk, Slack, WhatsApp, Salesforce and Jira nodes",
    "data_sources": "set as dataSourceId on Gmail, Calendar, Read Mails and SQL nodes",
}


async def _knowledge_bases() -> List[Dict[str, Any]]:
    from app.dependencies.injector import injector
    from app.services.agent_knowledge import KnowledgeBaseService

    items = await injector.get(KnowledgeBaseService).get_all()
    return [
        {"id": str(kb.id), "name": kb.name, "type": kb.type, "description": kb.description or ""}
        for kb in items
        # Internal knowledge bases are the platform's own, not the tenant's content.
        if (kb.source or "") != "internal"
    ]


async def _integrations() -> List[Dict[str, Any]]:
    from app.dependencies.injector import injector
    from app.services.app_settings import AppSettingsService

    items = await injector.get(AppSettingsService).get_all()
    return [
        {"id": str(item.id), "name": item.name, "type": str(getattr(item.type, "value", item.type))}
        for item in items
        if getattr(item, "is_active", 1)
    ]


async def _data_sources() -> List[Dict[str, Any]]:
    from app.dependencies.injector import injector
    from app.services.datasources import DataSourceService

    items = await injector.get(DataSourceService).get_all()
    return [
        {"id": str(item.id), "name": item.name, "type": item.source_type}
        for item in items
        if getattr(item, "is_active", 1)
    ]


_LOADERS: Dict[str, Callable] = {
    "knowledge_bases": _knowledge_bases,
    "integrations": _integrations,
    "data_sources": _data_sources,
}


async def describe_resources(kind: str) -> str:
    kind = str(kind or "").strip().lower().replace(" ", "_").replace("-", "_")
    if kind not in _LOADERS:
        return f"ERROR: unknown kind '{kind}'. Use one of: {', '.join(KINDS)}."
    try:
        items = await _LOADERS[kind]()
    except Exception as exc:
        logger.warning("Workflow builder could not list %s: %s", kind, exc, exc_info=True)
        return f"ERROR: could not list {kind}: {exc}"
    if not items:
        return (
            f"No {kind.replace('_', ' ')} exist yet. Leave the field unset and tell the person "
            f"they need to create one and select it on the node."
        )
    lines = [f"{kind} ({KINDS[kind]}):"]
    for item in items:
        extra = f" — {item['description'][:120]}" if item.get("description") else ""
        lines.append(f"- {item['name']} [{item.get('type', '')}] id={item['id']}{extra}")
    return "\n".join(lines)


SUMMARY_LIMIT = 12


async def summary() -> str:
    """
    All kinds in one compact block, for the workflow outline. The builder then knows
    what it can attach without a lookup call; the full listing stays available.
    """
    lines: List[str] = []
    for kind, loader in _LOADERS.items():
        try:
            items = await loader()
        except Exception as exc:
            logger.warning("Workflow builder could not list %s: %s", kind, exc)
            continue
        if not items:
            lines.append(f"- {kind.replace('_', ' ')}: none yet")
            continue
        shown = ", ".join(f"{item['name']} [{item.get('type', '')}] id={item['id']}" for item in items[:SUMMARY_LIMIT])
        more = f" … and {len(items) - SUMMARY_LIMIT} more (list_resources)" if len(items) > SUMMARY_LIMIT else ""
        lines.append(f"- {kind.replace('_', ' ')}: {shown}{more}")
    if not lines:
        return ""
    return "Workspace resources (set the id on the node; ask only if several could fit):\n" + "\n".join(lines)
