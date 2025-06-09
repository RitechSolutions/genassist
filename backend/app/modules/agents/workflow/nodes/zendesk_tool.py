import logging
from typing import Dict, Any, Optional
import aiohttp

from app.modules.agents.workflow.base_processor import NodeProcessor
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class ZendeskTicketNodeProcessor(NodeProcessor):
    """
    Processor for creating a Zendesk ticket via the REST API.
    Reads credentials from settings, only subject/description are required in input_data.
    """

    async def send_zendesk_ticket(
        self,
        subject: str,
        description: str,
        requester_name: Optional[str] = None,
        requester_email: Optional[str] = None,
        tags: Optional[list] = None,
        custom_fields: Optional[list] = None,
    ) -> Dict[str, Any]:
        subdomain = settings.ZENDESK_SUBDOMAIN
        api_token = settings.ZENDESK_API_TOKEN
        email = settings.ZENDESK_EMAIL

        url = f"https://{subdomain}.zendesk.com/api/v2/tickets.json"
        auth = aiohttp.BasicAuth(f"{email}/token", api_token)

        payload: Dict[str, Any] = {
            "ticket": {
                "subject": subject,
                "comment": {"body": description, "public": True},
            }
        }
        if requester_name or requester_email:
            payload["ticket"]["requester"] = {}
            if requester_name:
                payload["ticket"]["requester"]["name"] = requester_name
            if requester_email:
                payload["ticket"]["requester"]["email"] = requester_email
        if tags:
            payload["ticket"]["tags"] = tags
        if custom_fields:
            payload["ticket"]["custom_fields"] = custom_fields

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(url, json=payload) as resp:
                try:
                    resp.raise_for_status()
                    return {"status": resp.status, "data": await resp.json()}
                except Exception as e:
                    text = await resp.text()
                    logger.error(f"Zendesk ticket creation failed: {e} / {text}")
                    return {"status": resp.status, "data": {"error": text}}

    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        if not input_data:
            msg = "ZendeskTicketNodeProcessor: Missing input_data"
            logger.error(msg)
            self.output = {"status": 400, "data": {"error": msg}}
            return self.output

        subject = input_data.get("subject")
        description = input_data.get("description")
        missing = [f for f in ("subject", "description") if not input_data.get(f)]
        if missing:
            msg = f"ZendeskTicketNodeProcessor: Missing required fields: {missing}"
            logger.error(msg)
            self.output = {"status": 400, "data": {"error": msg}}
            return self.output

        result = await self.send_zendesk_ticket(
            subject=subject,
            description=description,
            requester_name=input_data.get("requester_name"),
            requester_email=input_data.get("requester_email"),
            tags=input_data.get("tags"),
            custom_fields=input_data.get("custom_fields"),
        )
        self.save_output(result)
        return result
