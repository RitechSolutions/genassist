import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.core.utils.enums.template_status_enum import TemplateStatus
from app.db.models.template import TemplateModel
from app.db.multi_tenant_session import multi_tenant_manager
from app.repositories.template import TemplateRepository
from app.schemas.agent import AgentCreate
from app.schemas.template import (
    TemplateCreateFromAgent,
    TemplateInstallResponse,
    TemplateListItem,
    TemplateRead,
)
from app.schemas.workflow import WorkflowCreate
from app.services.agent_config import AgentConfigService
from app.services.template_catalog import get_official_template, get_official_templates
from app.services.template_sanitizer import (
    sanitize_graph,
    sanitize_test_input,
    validate_node_types,
)
from app.services.workflow import WorkflowService

logger = logging.getLogger(__name__)


@inject
class TemplateService:
    """Business logic for the Template Marketplace.

    Serves a merged catalog — bundled official templates + approved cross-tenant
    "community" templates (stored in the master DB) + the current user's own
    private templates (tenant DB) — and handles the publish → approve lifecycle.
    """

    def __init__(
        self,
        repository: TemplateRepository,
        workflow_service: WorkflowService,
        agent_config_service: AgentConfigService,
    ):
        self.repository = repository
        self.workflow_service = workflow_service
        self.agent_config_service = agent_config_service

    # ---------- master-DB access (shared, cross-tenant rows) ----------
    @asynccontextmanager
    async def _master_repo(self):
        """A TemplateRepository bound to the MASTER (control-plane) DB.

        Global/published templates live in the master DB regardless of which
        tenant the request is scoped to, so we open a dedicated master session
        rather than using the tenant-scoped injected one.
        """
        factory = multi_tenant_manager.get_tenant_session_factory("master")
        async with factory() as session:
            yield TemplateRepository(session)

    @staticmethod
    def _to_item(
        row: TemplateModel,
        *,
        is_global: bool = False,
        publish_status: Optional[str] = None,
    ) -> TemplateListItem:
        item = TemplateListItem.model_validate(row)
        item.node_count = len((row.graph or {}).get("nodes", []) or [])
        item.is_global = is_global
        item.publish_status = publish_status
        return item

    # ---------- READ ----------
    async def list_templates(self, user_id: UUID) -> List[TemplateListItem]:
        official = [TemplateListItem(**tmpl) for tmpl in get_official_templates()]

        owned_rows = await self.repository.list_for_user(user_id)
        owned_ids = {row.id for row in owned_rows}
        current_tenant = get_tenant_context()

        async with self._master_repo() as mrepo:
            approved_rows = await mrepo.list_by_status(TemplateStatus.APPROVED)
            my_published = await mrepo.published_by_user(user_id)

        # map originating template id -> publish status, to annotate the owner's
        # cards. my_published is newest-first, so keep the first (latest) row per
        # source and ignore any older duplicates (e.g. a superseded rejection).
        pub_status: dict = {}
        for r in my_published:
            if r.source_template_id is not None:
                pub_status.setdefault(r.source_template_id, r.status)

        owned = [
            self._to_item(row, publish_status=pub_status.get(row.id))
            for row in owned_rows
        ]

        community = []
        seen_sources = set()
        for row in approved_rows:
            # Dedup: the publishing tenant sees its own (annotated) private copy,
            # not a second global card for the same template.
            if row.source_tenant == current_tenant and row.source_template_id in owned_ids:
                continue
            # Guard against accidental multiple approved copies of one source.
            key = row.source_template_id or row.id
            if key in seen_sources:
                continue
            seen_sources.add(key)
            community.append(self._to_item(row, is_global=True))

        return official + community + owned

    async def get_template(self, template_id: UUID, user_id: UUID) -> TemplateRead:
        official = get_official_template(template_id)
        if official is not None:
            return TemplateRead(**official)

        # approved cross-tenant template (master DB) — pending/rejected never exposed here
        async with self._master_repo() as mrepo:
            grow = await mrepo.get_by_id(template_id)
            if grow and not grow.is_deleted and grow.status == TemplateStatus.APPROVED:
                read = TemplateRead.model_validate(grow)
                read.is_global = True
                return read

        # the user's own private template (tenant DB)
        row = await self.repository.get_by_id(template_id)
        if not row or row.is_deleted or row.created_by != user_id:
            raise AppException(error_key=ErrorKey.TEMPLATE_NOT_FOUND, status_code=404)
        return TemplateRead.model_validate(row)

    async def list_pending(self) -> List[TemplateListItem]:
        """Master review queue — pending publish submissions."""
        async with self._master_repo() as mrepo:
            rows = await mrepo.list_by_status(TemplateStatus.PENDING)
        return [self._to_item(row, publish_status=TemplateStatus.PENDING) for row in rows]

    # ---------- WRITE ----------
    async def create_from_agent(
        self, data: TemplateCreateFromAgent, user_id: UUID
    ) -> TemplateRead:
        agent = await self.agent_config_service.get_by_id(data.agent_id)
        # Only the agent's owner (or a shared system agent) can be templated —
        # a user must not save another user's private agent as a template.
        if not agent.is_system and agent.created_by != user_id:
            raise AppException(
                error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                status_code=403,
                error_detail="You can only save your own agents as templates.",
            )
        if not agent.workflow_id:
            raise AppException(
                error_key=ErrorKey.TEMPLATE_INVALID,
                status_code=400,
                error_detail="Agent has no workflow to save as a template.",
            )

        workflow = await self.workflow_service.get_by_id(agent.workflow_id)
        nodes, edges = sanitize_graph(workflow.nodes, workflow.edges)
        node_types = sorted(
            {n.get("type") for n in nodes if isinstance(n, dict) and n.get("type")}
        )

        possible_queries = (
            agent.possible_queries.split(";") if agent.possible_queries else []
        )
        agent_config = {
            "name": data.title,
            "description": (data.description or agent.description or data.title)[:200],
            "welcome_message": agent.welcome_message or "Welcome",
            "possible_queries": [q for q in possible_queries if q],
            "welcome_title": agent.welcome_title,
            "greet_on_start": bool(agent.greet_on_start),
            "greeting_prompt": agent.greeting_prompt,
        }
        graph = {"nodes": nodes, "edges": edges}
        safe_test_input = sanitize_test_input(nodes, workflow.testInput)
        if safe_test_input is not None:
            graph["testInput"] = safe_test_input

        template = TemplateModel(
            title=data.title,
            description=data.description,
            category=data.category,
            icon=data.icon,
            tags=data.tags or [],
            node_types=node_types,
            graph=graph,
            agent_config=agent_config,
            is_official=False,
            status=TemplateStatus.PRIVATE,
            created_by=user_id,
        )
        created = await self.repository.create(template)
        return TemplateRead.model_validate(created)

    async def publish(self, template_id: UUID, user_id: UUID) -> TemplateRead:
        """Submit one of the user's own templates to the global review queue."""
        row = await self.repository.get_by_id(template_id)
        if not row or row.is_deleted or row.created_by != user_id:
            raise AppException(error_key=ErrorKey.TEMPLATE_NOT_FOUND, status_code=404)

        source_graph = row.graph or {}
        nodes, edges = sanitize_graph(source_graph.get("nodes"), source_graph.get("edges"))
        graph = {"nodes": nodes, "edges": edges}
        safe_test_input = sanitize_test_input(nodes, source_graph.get("testInput"))
        if safe_test_input is not None:
            graph["testInput"] = safe_test_input

        current_tenant = get_tenant_context()
        async with self._master_repo() as mrepo:
            existing = await mrepo.find_published(template_id, (TemplateStatus.PENDING, TemplateStatus.APPROVED))
            if existing is not None:
                raise AppException(
                    error_key=ErrorKey.TEMPLATE_INVALID,
                    status_code=400,
                    error_detail="This template has already been submitted or published.",
                )
            # Retract any prior rejected copy so it doesn't linger beside the new
            # submission (a stale card status) or accumulate over re-publishes.
            while True:
                stale = await mrepo.find_published(template_id, (TemplateStatus.REJECTED,))
                if stale is None:
                    break
                await mrepo.soft_delete(stale)
            published = TemplateModel(
                title=row.title,
                description=row.description,
                category=row.category,
                icon=row.icon,
                tags=row.tags or [],
                node_types=row.node_types or [],
                graph=graph,
                agent_config=row.agent_config,
                is_official=False,
                status=TemplateStatus.PENDING,
                source_tenant=current_tenant,
                published_by=user_id,
                source_template_id=template_id,
                created_by=user_id,
            )
            created = await mrepo.create(published)
            read = TemplateRead.model_validate(created)
            read.publish_status = TemplateStatus.PENDING
            return read

    async def approve(self, template_id: UUID, user_id: UUID) -> None:
        await self._transition(template_id, TemplateStatus.APPROVED, user_id)

    async def reject(
        self, template_id: UUID, user_id: UUID, reason: Optional[str]
    ) -> None:
        await self._transition(template_id, TemplateStatus.REJECTED, user_id, reason=reason)

    async def _transition(
        self,
        template_id: UUID,
        new_status: TemplateStatus,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        async with self._master_repo() as mrepo:
            row = await mrepo.get_by_id(template_id)
            if not row or row.is_deleted or row.status != TemplateStatus.PENDING:
                raise AppException(error_key=ErrorKey.TEMPLATE_NOT_FOUND, status_code=404)
            row.status = new_status
            row.approved_by = user_id
            row.approved_at = datetime.now(timezone.utc)
            if new_status == TemplateStatus.REJECTED:
                row.rejection_reason = (reason or "")[:500]
            await mrepo.update(row)

    async def install(
        self, template_id: UUID, name: Optional[str], user_id: UUID
    ) -> TemplateInstallResponse:
        template = await self.get_template(template_id, user_id)

        graph = template.graph or {}
        validate_node_types(graph.get("nodes"))
        # Re-sanitize defensively (official/community/user graphs should already be clean).
        nodes, edges = sanitize_graph(graph.get("nodes"), graph.get("edges"))

        cfg = template.agent_config or {}
        agent_name = (name or cfg.get("name") or template.title)[:100]
        description = (cfg.get("description") or template.description or agent_name)[:200]

        workflow = await self.workflow_service.create(
            WorkflowCreate(
                name=f"{agent_name} Workflow",
                description=description,
                nodes=nodes,
                edges=edges,
                testInput=graph.get("testInput"),
                version="1.0",
            )
        )

        agent_create = AgentCreate(
            name=agent_name,
            description=description,
            is_active=False,
            welcome_message=(cfg.get("welcome_message") or "Welcome")[:500],
            welcome_title=cfg.get("welcome_title"),
            possible_queries=cfg.get("possible_queries") or [],
            greet_on_start=bool(cfg.get("greet_on_start")),
            greeting_prompt=cfg.get("greeting_prompt"),
            workflow_id=workflow.id,
        )
        # AgentConfigService.create back-links agent_id/user_id onto the workflow.
        agent = await self.agent_config_service.create(agent_create, user_id=user_id)

        # Best-effort usage tracking (drives "most used"); never fail the install.
        try:
            if template.is_global:
                async with self._master_repo() as mrepo:
                    await mrepo.increment_install(template_id)
            elif not template.is_official:
                await self.repository.increment_install(template_id)
        except Exception:
            logger.warning(
                "Failed to increment install_count for template %s", template_id
            )

        return TemplateInstallResponse(agent_id=agent.id, workflow_id=workflow.id)

    async def delete_template(self, template_id: UUID, user_id: UUID) -> None:
        if get_official_template(template_id) is not None:
            raise AppException(
                error_key=ErrorKey.TEMPLATE_INVALID,
                status_code=400,
                error_detail="Official templates cannot be deleted.",
            )
        row = await self.repository.get_by_id(template_id)
        if not row or row.is_deleted or row.created_by != user_id:
            raise AppException(error_key=ErrorKey.TEMPLATE_NOT_FOUND, status_code=404)
        await self.repository.soft_delete(row)

    async def unpublish(self, template_id: UUID, user_id: UUID) -> None:
        """Withdraw the caller's published copy (pending or approved) of a template.

        ``template_id`` is the caller's own (private) template id.
        """
        row = await self.repository.get_by_id(template_id)
        if not row or row.is_deleted or row.created_by != user_id:
            raise AppException(error_key=ErrorKey.TEMPLATE_NOT_FOUND, status_code=404)
        async with self._master_repo() as mrepo:
            published = await mrepo.find_published(template_id, (TemplateStatus.PENDING, TemplateStatus.APPROVED))
            if published is None:
                return
            await mrepo.soft_delete(published)

    async def remove_global(self, template_id: UUID, user_id: UUID) -> None:
        """Master-admin removal of a published/community template (by master id)."""
        async with self._master_repo() as mrepo:
            row = await mrepo.get_by_id(template_id)
            if not row or row.is_deleted:
                raise AppException(error_key=ErrorKey.TEMPLATE_NOT_FOUND, status_code=404)
            await mrepo.soft_delete(row)
