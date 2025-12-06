from typing import Dict, Any, Optional
import logging
import aiohttp

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class ZendeskConnector:

    def __init__(
        self,
        subdomain: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        self.subdomain = subdomain or settings.ZENDESK_SUBDOMAIN
        self.email = email or settings.ZENDESK_EMAIL
        self.api_token = api_token or settings.ZENDESK_API_TOKEN
        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

    async def create_ticket(
        self,
        subject: str,
        description: str,
        requester_name: Optional[str] = None,
        requester_email: Optional[str] = None,
        tags: Optional[list] = None,
        custom_fields: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Create a Zendesk ticket via the REST API."""
        api_token = self.api_token
        email = self.email
        if not api_token:
            raise ValueError("Zendesk API token is required")
        if not email:
            raise ValueError("Zendesk email is required")
        url = f"{self.base_url}/tickets.json"
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
