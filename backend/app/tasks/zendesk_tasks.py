import asyncio
import logging
from uuid import UUID
import json


from app.core.utils.date_time_utils import utc_now
from app.services.conversations import ConversationService

from app.schemas.conversation import ConversationCreate
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.db.seed.seed_data_config import seed_test_data

from app.modules.integration.zendesk import ZendeskConnector
from app.core.config.settings import settings
from app.dependencies.injector import injector

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def analyze_zendesk_tickets_task():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(analyze_zendesk_tickets_async_with_scope())


async def analyze_zendesk_tickets_async_with_scope():
    """Wrapper to run Zendesk analysis for all tenants"""
    from app.tasks.base import run_task_with_tenant_support

    result = await run_task_with_tenant_support(
        process_zendesk_tickets, "Zendesk ticket analysis"
    )
    # Update status key to match expected format
    if result.get("status") == "success":
        result["status"] = "completed"
    return result


async def analyze_zendesk_tickets_async():
    logger.info("Starting Zendesk ticket analysis task...")
    return await process_zendesk_tickets()


############################
async def process_zendesk_tickets():
    logger.info("Processing Zendesk tickets...")
    conversation_service = injector.get(ConversationService)
    zendesk_connector = ZendeskConnector()
    zen_tickets = await zendesk_connector.get_unrated_closed_tickets()

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
                x = await zendesk_connector.create_followup_ticket(
                    ticket_id, payload
                )  # creates new related ticket (POST)
            else:
                payload["ticket"]["subject"] = f"ANALYZED: {ticket_subject}"
                x = await zendesk_connector.update_ticket(
                    ticket_id, payload=payload
                )  # updates existing ticket with evaluation and closes it (PUT)

            processed += 1

        except Exception as e:
            logger.error(f"Error processing ticket {ticket['id']}: {str(e)}")
            failed += 1

    result = {
        "status": "completed",
        "processed": processed,
        "failed": failed,
        "timestamp": utc_now().isoformat(),
    }

    logger.info(f"Zendesk ticket analysis completed: {result}")
    return result
