import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_injector import Injected
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import auth

from app.core.config.settings import settings
from app.repositories.conversations import ConversationRepository
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.modules.integration.zendesk import ZendeskConnector
from app.services.zendesk import analyze_ticket_for_db
from app.tasks.zendesk_tasks import analyze_zendesk_tickets_async

logger = logging.getLogger(__name__)
router = APIRouter()


class ZendeskRequester(BaseModel):
    name: Optional[str]
    email: Optional[str]


class ZendeskClosedPayload(BaseModel):
    ticket_id: int
    subject: Optional[str] = None
    updated_at: Optional[str] = None
    requester: Optional[ZendeskRequester] = None
    status: Optional[str] = None
    custom_fields: Optional[list[dict]] = None
    tags: Optional[list[str]] = None


@router.post(
    "/closed",
    status_code=200,
    summary="Zendesk webhook: ticket closed",
    dependencies=[Depends(auth)],
)
async def zendesk_ticket_closed(
    payload: ZendeskClosedPayload,
    db: AsyncSession = Injected(AsyncSession),
):
    logger.info(f"→ Received Zendesk webhook payload: {payload.json()}")

    zendesk_connector = ZendeskConnector()
    ticket = await zendesk_connector.fetch_ticket_details(payload.ticket_id)
    logger.debug(
        f"Fetched ticket #{ticket['id']} from Zendesk: subject={ticket.get('subject')}"
    )

    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_by_zendesk_ticket_id(ticket["id"])

    if not conversation:
        logger.warning(
            f"No conversation found by zendesk_ticket_id={ticket['id']}, trying custom_fields..."
        )
        custom_fields = ticket.get("custom_fields", [])
        conversation_id_str = None

        for field in custom_fields:
            if field.get("id") == settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID:
                conversation_id_str = field.get("value")
                logger.debug(
                    f"Found custom field conversation_id: {conversation_id_str!r}"
                )
                break

        if conversation_id_str:
            try:
                conversation_id = UUID(str(conversation_id_str).strip())
                conversation = await conv_repo.get_by_id(conversation_id)
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Invalid UUID in custom field: {conversation_id_str} ({e})"
                )
                raise HTTPException(
                    status_code=400, detail="Invalid conversation ID in custom field"
                ) from e

    if not conversation:
        logger.error("❌ Conversation not found (even via custom_fields)")
        raise HTTPException(
            status_code=404, detail="No conversation found (even via custom_fields)"
        )

    logger.info(
        f"✔ Found ConversationModel id={conversation.id} for ticket_id={ticket['id']}"
    )

    if conversation.zendesk_ticket_id is None:
        await conv_repo.set_zendesk_ticket_id(UUID(str(conversation.id)), ticket["id"])
        logger.info(
            f"Linked Zendesk ticket ID {ticket['id']} to conversation {conversation.id}"
        )

    try:
        analysis_dict = analyze_ticket_for_db(ticket, UUID(str(conversation.id)))
        logger.debug(f"Analysis result: {analysis_dict}")
    except Exception as e:
        logger.exception("Failed to analyze ticket")
        raise HTTPException(status_code=500, detail="Ticket analysis failed") from e

    from app.schemas.conversation_analysis import ConversationAnalysisCreate

    analysis_payload = ConversationAnalysisCreate(**analysis_dict)

    conv_anal_repo = ConversationAnalysisRepository(db)
    new_analysis = await conv_anal_repo.save_conversation_analysis(analysis_payload)

    logger.info(
        f"✔ Saved ConversationAnalysis id={new_analysis.id} for conversation={conversation.id}"
    )

    try:
        comment_text = (
            f"Conversation analyzed successfully.\n"
            f"Sentiment: {analysis_dict.get('sentiment')}\n"
            f"Message Count: {analysis_dict.get('message_count')}\n"
            f"Other metrics: {analysis_dict}"
        )
        await zendesk_connector.post_private_comment(
            ticket_id=ticket["id"], body=comment_text
        )
    except HTTPException:
        logger.warning("Failed to post comment to Zendesk ticket.")

    return {"status": "ok", "analysis_id": str(new_analysis.id)}


@router.get(
    "/zendesk-unrated-closed-tickets",
    status_code=200,
    summary="Get unrated closed Zendesk tickets",
    dependencies=[Depends(auth)],
)
async def zendesk_unrated_closed_tickets():
    try:
        zendesk_connector = ZendeskConnector()
        return await zendesk_connector.get_unrated_closed_tickets()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.get(
    "/zendesk-analyze-update-closed-tickets",
    status_code=200,
    summary="Analyze closed Zendesk tickets",
    dependencies=[Depends(auth)],
)
async def zendesk_analyze_closed_tickets():
    try:
        return await analyze_zendesk_tickets_async()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e
