import logging
from typing import Any, Dict, Optional
from uuid import UUID
import httpx

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

BASE_URL = f"https://{settings.ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"
AUTH = (f"{settings.ZENDESK_EMAIL}/token", settings.ZENDESK_API_TOKEN)

class ZendeskClient:
    """
    Minimal Zendesk v2 API client for creating or updating tickets,
    embedding a custom field=self.conversation_id so that the webhook can match later.
    """
    def __init__(self):
        self.base_url = settings._zendesk_base
        self.auth     = settings._zendesk_auth

    async def create_ticket(
        self,
        subject: str,
        description: str,
        requester_email: str,
        conversation_id: str,
        tags: list[str] = [],
    ) -> Optional[int]:
        """
        Creates a new Zendesk ticket. Returns the Zendesk ticket ID on success.
        We set:
          - subject
          - description
          - requester_email  (customer email)
          - custom_fields → list of { "id": settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID, "value": conversation_id }
        """
        url = f"{self.base_url}/tickets.json"
        payload = {
            "ticket": {
                "subject": subject,
                "comment": { "body": description, "public": True },
                "requester": {  "name": requester_email.split("@")[0] or "Unknown", "email": requester_email },
                "tags": tags,
                "custom_fields": [
                    {
                        "id": settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID,
                        "value": conversation_id
                    }
                ]
            }
        }

        async with httpx.AsyncClient(auth=self.auth, timeout=10.0) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code not in (200, 201):
            logger.error(f"Zendesk create_ticket failed [{resp.status_code}]: {resp.text}")
            return None

        ticket = resp.json().get("ticket", {})
        return ticket.get("id")

    async def update_ticket(
        self,
        ticket_id: int,
        comment: Optional[str] = None,
        custom_field_updates: Optional[dict[int, Any]] = None
    ) -> bool:
        """
        Update an existing Zendesk ticket. Optionally add a new private comment,
        and/or adjust custom_fields. Returns True on HTTP 200, else False.
        """
        url = f"{self.base_url}/tickets/{ticket_id}.json"
        ticket_obj: dict[str, Any] = {}

        if comment is not None:
            ticket_obj["comment"] = { "body": comment, "public": False }

        if custom_field_updates:
            cf_list = []
            for fld_id, val in custom_field_updates.items():
                cf_list.append({ "id": fld_id, "value": val })
            ticket_obj["custom_fields"] = cf_list

        payload = { "ticket": ticket_obj }

        async with httpx.AsyncClient(auth=self.auth, timeout=10.0) as client:
            resp = await client.put(url, json=payload)

        if resp.status_code != 200:
            logger.error(f"Zendesk update_ticket({ticket_id}) failed [{resp.status_code}]: {resp.text}")
            return False

        return True


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

def analyze_ticket_for_db(
    ticket: Dict[str, Any],
    conversation_id: UUID
) -> Dict[str, Any]:
    """
    Map the raw Zendesk ticket JSON (with 'ticket["comments"]') into a
    dict suitable for ConversationAnalysisCreate. Any missing numeric
    fields are defaulted to 0; missing strings default to "".
    """

    topic: Optional[str] = None
    for cf in ticket.get("custom_fields", []):
        if cf["id"] == 11111111:
            topic = cf["value"]
            break
    if not topic:
        tags = ticket.get("tags", [])
        topic = tags[0] if tags else ""
    topic = topic or ""  # ensure non‐None string

    summary = ticket.get("description", "")[:200]  # always a string

    neg_sent: Optional[int] = None
    pos_sent: Optional[int] = None
    neu_sent: Optional[int] = None
    for cf in ticket.get("custom_fields", []):
        if cf["id"] == 33333333:
            neg_sent = cf["value"]
        elif cf["id"] == 44444444:
            pos_sent = cf["value"]
        elif cf["id"] == 55555555:
            neu_sent = cf["value"]

    negative_sentiment = int(neg_sent or 0)
    positive_sentiment = int(pos_sent or 0)
    neutral_sentiment  = int(neu_sent or 0)

    tone: Optional[str] = None
    for cf in ticket.get("custom_fields", []):
        if cf["id"] == 66666666:
            tone = cf["value"]
            break
    tone = tone or ""  # ensure non‐None string

    cust_sat: Optional[int] = None
    for cf in ticket.get("custom_fields", []):
        if cf["id"] == 77777777:
            cust_sat = cf["value"]
            break
    if cust_sat is None:
        sat_obj = ticket.get("satisfaction_rating") or {}
        score = sat_obj.get("score")
        if isinstance(score, str):
            cust_sat = {"good": 5, "bad": 1}.get(score, 0)
    customer_satisfaction = int(cust_sat or 0)

    # ─── 6) Efficiency (# of agent comments / total comments × 100) ───────────
    comments = ticket.get("comments", [])
    total_comments = len(comments)
    if total_comments > 0:
        agent_comments = sum(1 for c in comments if c.get("author_id") != ticket.get("requester_id"))
        efficiency = int((agent_comments / total_comments) * 100)
    else:
        efficiency = 0

    response_time: Optional[int] = None
    created_at = ticket.get("created_at")
    if created_at and comments:
        try:
            dt_created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            first_agent = next((c for c in comments if c.get("author_id") != ticket.get("requester_id")), None)
            if first_agent:
                dt_first = datetime.fromisoformat(first_agent["created_at"].replace("Z", "+00:00"))
                response_time = int((dt_first - dt_created).total_seconds() / 60)
        except Exception:
            response_time = None
    response_time = int(response_time or 0)

    if customer_satisfaction >= 4:
        quality_of_service = 100
    elif customer_satisfaction >= 2:
        quality_of_service = 50
    else:
        quality_of_service = 0

    op_knowledge: Optional[int] = None
    if comments:
        count_know = sum(1 for c in comments if "help" in c.get("body", "").lower())
        op_knowledge = count_know * 10  # scale to 0–100
    operator_knowledge = int(op_knowledge or 0)

    resolution_rate = 100 if ticket.get("status") == "closed" else 0

    llm_analyst_id = None

    return {
        "conversation_id": conversation_id,
        "topic": topic,
        "summary": summary,
        "negative_sentiment": negative_sentiment,
        "positive_sentiment": positive_sentiment,
        "neutral_sentiment": neutral_sentiment,
        "tone": tone,
        "customer_satisfaction": customer_satisfaction,
        "efficiency": efficiency,
        "response_time": response_time,
        "quality_of_service": quality_of_service,
        "operator_knowledge": operator_knowledge,
        "resolution_rate": resolution_rate,
        "llm_analyst_id": llm_analyst_id,
    }
