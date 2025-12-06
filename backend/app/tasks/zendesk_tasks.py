import asyncio
import logging
from uuid import UUID
from datetime import datetime
import json

from fastapi import HTTPException

from datetime import datetime, timedelta


from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.operator_statistics import OperatorStatisticsRepository
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.llm_analysts import LlmAnalystService
from app.services.operator_statistics import OperatorStatisticsService
from app.services.conversations import ConversationService

from app.schemas.conversation import ConversationCreate
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.db.seed.seed_data_config import seed_test_data

from app.services.zendesk import (
    ZendeskClient,
    fetch_ticket_details,
    post_private_comment,
    analyze_ticket_for_db,
)
from app.core.config.settings import settings
import httpx
from app.core.utils.enums.transcript_message_type import TranscriptMessageType
from app.dependencies.injector import injector

from celery import shared_task
from fastapi_injector import RequestScopeFactory
from app.tasks.base import run_task_for_all_tenants

logger = logging.getLogger(__name__)


@shared_task
def analyze_zendesk_tickets_task():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(analyze_zendesk_tickets_async_with_scope())


async def analyze_zendesk_tickets_async_with_scope():
    """Wrapper to run Zendesk analysis for all tenants"""
    try:
        logger.info("Starting Zendesk ticket analysis task for all tenants...")
        request_scope_factory = injector.get(RequestScopeFactory)

        async def run_with_scope():
            async with request_scope_factory.create_scope():
                return await process_zendesk_tickets()

        results = await run_task_for_all_tenants(run_with_scope)

        logger.info(f"Zendesk analysis completed for {len(results)} tenant(s)")
        return {
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error in Zendesk ticket analysis task: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
        }
    finally:
        logger.info("Zendesk ticket analysis task completed.")


async def analyze_zendesk_tickets_async():
    logger.info("Starting Zendesk ticket analysis task...")
    return await process_zendesk_tickets()


############################
async def process_zendesk_tickets():
    logger.info("Processing Zendesk tickets...")
    conversation_service = injector.get(ConversationService)
    zen_tickets = await get_zendesk_unrated_closed_tickets()

    processed = 0
    failed = 0
    for ticket in zen_tickets:
        try:
            ticket_id = ticket["id"]
            comments = ticket.get("transcription")
            conversation_id = UUID(int=ticket_id)
            ticket_subject = ticket.get("subject") or ""
            ticket_status = ticket.get("status") or ""

            # transcript_string = json.dumps([item["body"] for item in comments], ensure_ascii=False, default=str)
            transcript_string = json.dumps(comments, ensure_ascii=False, default=str)

            conversation_transcript = ConversationCreate(
                operator_id=UUID(seed_test_data.zen_operator_id),
                data_source_id=None,
                recording_id=None,
                transcription=transcript_string,
                conversation_date=ticket.get("created_at"),
                customer_id=None,
                word_count=0,
                customer_ratio=0,
                agent_ratio=0,
                duration=0,
                status=ConversationStatus.IN_PROGRESS.value,
                conversation_type=ConversationType.PROGRESSIVE.value,
                zendesk_ticket_id=ticket_id,
            )

            saved_conversation = (
                await conversation_service.conversation_repo.save_conversation(
                    conversation_transcript
                )
            )
            conversation_id = str(saved_conversation.id)
            conversation_analysis = (
                await conversation_service.finalize_in_progress_conversation(
                    None, saved_conversation.id
                )
            )

            # UPDATE Zendesk
            # Pull out the detailed fields for the ticket comment
            topic = conversation_analysis.topic or ""
            summary = conversation_analysis.summary or ""
            resolution_rate = conversation_analysis.resolution_rate or 0
            customer_satisfaction = conversation_analysis.customer_satisfaction or 0
            service_quality = conversation_analysis.quality_of_service or 0

            # Helper to convert 0–10 scale to percentage
            def to_percent(value: int) -> int:
                return int((value / 10) * 100)

            comment_body = (
                "Ticket Closed\n"
                f"🔹 Topic: {topic}\n"
                f"🔹 Summary: {summary}\n"
                f"🔹 Resolution Rate: {resolution_rate}%\n"
                f"🔹 Customer Satisfaction: {to_percent(customer_satisfaction)}%\n"
                f"🔹 Service Quality: {to_percent(service_quality)}%\n\n"
                "For any follow‐up, please contact the customer by email "
                "and ask about any remaining concerns."
            )
            payload = {
                "ticket": {
                    "via_followup_source_id": ticket_id,
                    "comment": {"body": comment_body, "public": False},
                    "subject": f"Followup of ticket # {ticket_id}: {ticket_subject}",
                    "status": "closed",
                    "tags": ["genassist", "analyzed"],
                    "custom_fields": [
                        {
                            "id": settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID,
                            "value": conversation_id,
                        }
                    ],
                }
            }
            # await conversation_service.store_zendesk_analysis(saved_conversation, conversation_analysis) #using ZendeskClient - it creates new ticket

            # if ticket status is 'closed' - no update is allowed so related followup ticket must be created
            # otherwise is status is 'solved' it is allowed to update it and change the status to 'closed'
            if ticket_status == "closed":
                x = await create_followup_zendesk_ticket(
                    ticket_id, payload
                )  # creates new related ticket (POST)
            else:
                payload["ticket"]["subject"] = f"ANALYZED: {ticket_subject}"
                x = await update_ticket_with_statistics(
                    ticket_id, payload
                )  # updates existing ticket with evaluation and closes it (PUT)

            processed += 1

        except Exception as e:
            logger.error(f"Error processing ticket {ticket['id']}: {str(e)}")
            failed += 1

    result = {
        "status": "completed",
        "processed": processed,
        "failed": failed,
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(f"Zendesk ticket analysis completed: {result}")
    return result


################

BASE_URL = f"https://{settings.ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"
AUTH = (f"{settings.ZENDESK_EMAIL}/token", settings.ZENDESK_API_TOKEN)


async def get_zendesk_api(url: str):
    """Authenticates and makes call to Zendesk API."""
    async with httpx.AsyncClient(auth=AUTH, timeout=10.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()  # Raises httpx.HTTPStatusError for 4xx/5xx
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Zendesk API error [{e.response.status_code}]: {e.response.text}"
            )
            raise HTTPException(
                status_code=e.response.status_code, detail="Zendesk fetch failed"
            )
        except httpx.RequestError as e:
            logger.error(f"Network error during Zendesk API call: {e}")
            raise HTTPException(status_code=500, detail="Zendesk API network error")


async def update_ticket_with_statistics(ticket_id: int, payload):
    """Updates a Zendesk ticket with a private comment, status, and tags."""
    url = f"{BASE_URL}/tickets/{ticket_id}.json"

    async with httpx.AsyncClient(auth=AUTH, timeout=10.0) as client:
        try:
            response = await client.put(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Zendesk update error [{e.response.status_code}]: {e.response.text}"
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Zendesk ({e.response.status_code}): {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(f"Network error during Zendesk update: {e}")
            raise HTTPException(status_code=500, detail="Zendesk update network error")


async def create_followup_zendesk_ticket(ticket_id: int, payload):
    """Updates a Zendesk ticket with a private comment, status, and tags."""
    url = f"{BASE_URL}/tickets.json"

    async with httpx.AsyncClient(auth=AUTH, timeout=10.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Zendesk update error [{e.response.status_code}]: {e.response.text}"
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Zendesk ({e.response.status_code}): {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(f"Network error during Zendesk update: {e}")
            raise HTTPException(status_code=500, detail="Zendesk update network error")


async def get_zendesk_unrated_closed_tickets():
    """Fetch all closed, unrated Zendesk tickets (-tags:analyzed) with comments."""
    tickets_to_rate = []
    updated_later_then = ""
    # add time constrains uncomment the next line
    updated_later_then = (
        f" updated>={(datetime.utcnow().date() - timedelta(days=7)).isoformat()}"
    )

    query_definition = f"type:ticket status:solved status:closed -tags:analyzed {updated_later_then}"  # last 7 days
    search_url = f"{BASE_URL}/search.json?query={query_definition}"

    while search_url:
        try:
            response = await get_zendesk_api(search_url)
            results = response.get("results", [])
            search_url = response.get("next_page")  # handle pagination
        except Exception as e:
            print(f"Error fetching tickets: {e}")
            break

        for ticket in results:
            try:
                ticket_id = ticket["id"]
                if ticket.get("followup_ids") == []:
                    # if followup_ids is [] it means it has Related Ticket where is saved analytics
                    new_ticket = {
                        "id": ticket_id,
                        "created_at": ticket.get("created_at"),
                        "subject": ticket.get("raw_subject"),
                        "description": ticket.get("description"),
                        "status": ticket.get("status"),
                        "tags": ticket.get("tags"),
                        "transcription": [],
                    }

                    # Get comments for this ticket
                    comments_url = f"{BASE_URL}/tickets/{ticket_id}/comments.json"
                    comments_response = await get_zendesk_api(comments_url)

                    for comment in comments_response.get("comments", []):
                        new_comment = {
                            "id": comment.get("id"),
                            "timestamp": comment.get("created_at"),
                            "message": comment.get("plain_body"),
                            "type": TranscriptMessageType.MESSAGE.value,
                        }
                        new_ticket["transcription"].append(new_comment)

                    tickets_to_rate.append(new_ticket)
                # else skip the ticket since it is already reated (it has related ticket - followup_ids)
            except Exception as e:
                print(f"Error processing ticket ID {ticket.get('id')}: {e}")
                continue

    return tickets_to_rate
