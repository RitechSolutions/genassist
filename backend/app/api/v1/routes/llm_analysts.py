from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.schemas.llm import LlmAnalyst, LlmAnalystCreate, LlmAnalystUpdate
from app.services.llm_analysts import LlmAnalystService
from app.schemas.dynamic_form_schemas.llm_analyst_enrichments import AVAILABLE_ENRICHMENTS
from app.schemas.dynamic_form_schemas.nodes import NODE_TYPE_LABELS
from app.services.datasources import DataSourceService
from app.services.agent_knowledge import KnowledgeBaseService


router = APIRouter()


@router.get("/available-enrichments", dependencies=[Depends(auth)])
async def get_available_enrichments(
    datasource_service: DataSourceService = Injected(DataSourceService),
    knowledge_base_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
):
    zendesk_sources = await datasource_service.get_by_type("zendesk")
    has_zendesk = len(zendesk_sources) > 0

    knowledge_bases = await knowledge_base_service.get_all()
    has_knowledge_bases = len(knowledge_bases) > 0

    key_enabled = {
        "zendesk_ticket_created": has_zendesk,
        "knowledge_base_used": has_knowledge_bases,
    }

    return [e for e in AVAILABLE_ENRICHMENTS if key_enabled.get(e["key"], True)]


@router.get("/available-node-types", dependencies=[Depends(auth)])
async def get_available_node_types():
    return [{"node_type": k, "label": v} for k, v in NODE_TYPE_LABELS.items()]


@router.get("", response_model=list[LlmAnalyst], dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.READ))
])
async def get_all(service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.get_all()


@router.get("/{llm_analyst_id}", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.READ))
])
async def get(llm_analyst_id: UUID, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.get_by_id(llm_analyst_id)


@router.post("", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.CREATE))
])
async def create(data: LlmAnalystCreate, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.create(data)


@router.patch("/{llm_analyst_id}", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.UPDATE))
])
async def update(llm_analyst_id: UUID, data: LlmAnalystUpdate, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.update(llm_analyst_id, data)


@router.delete("/{llm_analyst_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.DELETE))
])
async def delete(llm_analyst_id: UUID, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.delete(llm_analyst_id)
