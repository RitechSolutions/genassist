from typing import Dict, Any
import logging

from app.core.utils.bi_utils import make_async_web_call

logger = logging.getLogger(__name__)


class WhatsAppConnector:

    def __init__(self, token: str, phone_number_id: str):
        self.token = token
        self.phone_number_id = phone_number_id
        self.base_url = "https://graph.facebook.com/v22.0"

    async def send_text_message(
        self, recipient_number: str, text: str
    ) -> Dict[str, Any]:
        """Send a WhatsApp text message."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        return await make_async_web_call(
            method="POST", url=url, headers=headers, payload=payload
        )
