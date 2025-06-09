import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.db.session import get_db
from app.repositories.conversations import ConversationRepository
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.services.zendesk import analyze_ticket_for_db

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
    tags: Optional[list[str]]  = None

BASE_URL = f"https://{settings.ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"
AUTH = (f"{settings.ZENDESK_EMAIL}/token", settings.ZENDESK_API_TOKEN)


async def fetch_ticket_details(ticket_id: int) -> Dict[str, Any]:
    url = f"{BASE_URL}/tickets/{ticket_id}.json?include=comments"
    logger.debug(f"Fetching Zendesk ticket: {url}")

    async with httpx.AsyncClient(auth=AUTH, timeout=10.0) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        logger.error(f"Failed to fetch ticket [{resp.status_code}]: {resp.text}")
        raise HTTPException(status_code=502, detail="Zendesk fetch failed")

    return resp.json()["ticket"]


async def post_private_comment(ticket_id: int, body: str):
    url = f"{BASE_URL}/tickets/{ticket_id}.json"
    payload = {
        "ticket": {
            "comment": {
                "body": body,
                "public": False
            }
        }
    }

    async with httpx.AsyncClient(auth=AUTH, timeout=10.0) as client:
        resp = await client.put(url, json=payload)

    if resp.status_code != 200:
        logger.error(f"Failed to post comment to ticket {ticket_id}: {resp.status_code} {resp.text}")
    else:
        logger.info(f"Posted analysis comment to ticket #{ticket_id}")


@router.post("/closed", status_code=200, summary="Zendesk webhook: ticket closed")
async def zendesk_ticket_closed(
    payload: ZendeskClosedPayload,
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"→ Received Zendesk webhook payload: {payload.json()}")

    ticket = await fetch_ticket_details(payload.ticket_id)
    logger.debug(f"Fetched ticket #{ticket['id']} from Zendesk: subject={ticket.get('subject')}")

    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_by_zendesk_ticket_id(ticket["id"])

    if not conversation:
        logger.warning(f"No conversation found by zendesk_ticket_id={ticket['id']}, trying custom_fields...")
        custom_fields = ticket.get("custom_fields", [])
        conversation_id_str = None

        for field in custom_fields:
            if field.get("id") == settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID:
                conversation_id_str = field.get("value")
                logger.debug(f"Found custom field conversation_id: {conversation_id_str!r}")
                break

        if conversation_id_str:
            try:
                conversation_id = UUID(str(conversation_id_str).strip())
                conversation = await conv_repo.get_by_id(conversation_id)
            except Exception as e:
                logger.error(f"Invalid UUID in custom field: {conversation_id_str} ({e})")
                raise HTTPException(status_code=400, detail="Invalid conversation ID in custom field")

    if not conversation:
        logger.error("❌ Conversation not found (even via custom_fields)")
        raise HTTPException(status_code=404, detail="No conversation found (even via custom_fields)")

    logger.info(f"✔ Found ConversationModel id={conversation.id} for ticket_id={ticket['id']}")

    if conversation.zendesk_ticket_id is None:
        await conv_repo.set_zendesk_ticket_id(conversation.id, ticket["id"])
        logger.info(f"Linked Zendesk ticket ID {ticket['id']} to conversation {conversation.id}")

    try:
        analysis_dict = analyze_ticket_for_db(ticket, conversation.id)
        logger.debug(f"Analysis result: {analysis_dict}")
    except Exception as e:
        logger.exception("Failed to analyze ticket")
        raise HTTPException(status_code=500, detail="Ticket analysis failed")

    from app.schemas.conversation_analysis import ConversationAnalysisCreate
    analysis_payload = ConversationAnalysisCreate(**analysis_dict)

    conv_anal_repo = ConversationAnalysisRepository(db)
    new_analysis = await conv_anal_repo.save_conversation_analysis(analysis_payload)

    logger.info(f"✔ Saved ConversationAnalysis id={new_analysis.id} for conversation={conversation.id}")

    try:
        comment_text = (
            f"Conversation analyzed successfully.\n"
            f"Sentiment: {analysis_dict.get('sentiment')}\n"
            f"Message Count: {analysis_dict.get('message_count')}\n"
            f"Other metrics: {analysis_dict}"
        )
        await post_private_comment(ticket_id=ticket["id"], body=comment_text)
    except Exception:
        logger.warning("Failed to post comment to Zendesk ticket.")

    return {"status": "ok", "analysis_id": str(new_analysis.id)}
