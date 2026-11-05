"""Save the requester's email and name on the active conversation for GDPR lookups."""

import logging
from typing import Any, Optional
from uuid import UUID

from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


async def persist_requester_pii(
    state: Any,
    requester_email: Optional[str],
    requester_name: Optional[str],
    node_label: str,
) -> None:
    """Store the requester in ``custom_attributes.pii``; failures are logged, never raised."""

    if not requester_email and not requester_name:
        return

    try:
        from app.repositories.conversations import ConversationRepository

        thread_id = getattr(state, "thread_id", None)
        if not thread_id:
            return

        try:
            conversation_uuid = UUID(str(thread_id))
        except (ValueError, TypeError):
            return

        conversation_repo = injector.get(ConversationRepository)
        conversation = await conversation_repo.fetch_conversation_by_id(
            conversation_uuid
        )
        if conversation is None:
            return

        existing_attrs = dict(conversation.custom_attributes or {})
        existing_pii = dict(existing_attrs.get("pii") or {})
        if requester_email:
            existing_pii["requester_email"] = str(requester_email).strip().lower()
        if requester_name:
            existing_pii["requester_name"] = str(requester_name).strip()
        existing_attrs["pii"] = existing_pii

        await conversation_repo.update_custom_attributes(
            conversation_uuid, existing_attrs
        )
    except Exception as exc:
        logger.warning(
            f"{node_label}: failed to persist PII to conversation custom_attributes: %s",
            exc,
        )
