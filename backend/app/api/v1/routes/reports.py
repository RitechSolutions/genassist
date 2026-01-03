from fastapi import APIRouter, Depends
from typing import Dict

from fastapi_injector import Injected

from app.services.conversations import ConversationService
from app.schemas.report import TopicsReport

router = APIRouter()

@router.get(
    "/topics-report",
    response_model=TopicsReport,
    summary="Counts per topics report",
    description="Returns a map of topic→count across all conversation analyses.",
)
async def topics_report(
    service: ConversationService = Injected(ConversationService),
    ) -> TopicsReport:
    return await service.get_topics_count()