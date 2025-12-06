import logging
import os
from typing import Dict, Any
import aiohttp

from app.modules.agents.workflow.base_processor import NodeProcessor

logger = logging.getLogger(__name__)


class WhatsAppMessageNodeProcessor(NodeProcessor):
    """
    Processor that sends a text message with the WhatsApp Cloud API.

    Expected input to `.process()`:

    {
        "token": "<meta-access-token>",
        "phone_number_id": "<business-phone-number-id>",
        "to": "<recipient_phone_number_in_E164_format>",
        "text": "Hello world!"
    }
    """

    async def _send_whatsapp_text(
        self,
        token: str,
        phone_number_id: str,
        to: str,
        text: str,
    ) -> Dict[str, Any]:
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
                },
        }

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=os.getenv("USE_SSL").lower() == "true")) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                try:
                    resp.raise_for_status()
                    return {"status": resp.status, "data": await resp.json()}
                except Exception as e:
                    logger.error(f"WhatsApp message failed: {e}")
                    return {"status": resp.status, "data": {"error": str(e)}}

    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        token = input_data.get("token")
        phone_number_id = input_data.get("phone_number_id")
        to = input_data.get("to")
        text = input_data.get("text")

        if not all([token, phone_number_id, to, text]):
            msg = "WhatsAppMessageNodeProcessor: token, phone_number_id, to and text are required"
            logger.error(msg)
            self.output = {"status": 400, "data": {"error": msg}}
            return self.output

        response = await self._send_whatsapp_text(token, phone_number_id, to, text)
        self.save_output(response)
        return response
