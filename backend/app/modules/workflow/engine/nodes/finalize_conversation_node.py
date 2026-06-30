"""Finalize Conversation node ("End Conversation").

Pass-through node that finalizes the conversation associated with the running
workflow by reusing the canonical
``ConversationService.finalize_in_progress_conversation`` logic. The node owns no
business logic of its own: it only resolves the conversation id from the run's
``thread_id``, delegates to the service, and maps known error conditions onto a
handled no-op (vs. a surfaced error).
"""

import logging
from typing import Any, Dict
from uuid import UUID

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
from app.services.conversations import ConversationService

from ..base_node import BaseNode

logger = logging.getLogger(__name__)

# AppException error keys that mean "nothing to finalize" — handled as a no-op so
# the workflow run is never faulted (FR-4, FR-9).
_NO_OP_ERROR_KEYS = {
    ErrorKey.CONVERSATION_FINALIZED,
    ErrorKey.CONVERSATION_NOT_FOUND,
}


class FinalizeConversationNode(BaseNode):
    """Finalize the active conversation, mirroring the canonical finalize action.

    The target conversation is resolved from the run's ``thread_id`` (which equals
    ``str(conversation_id)`` in the client-chat flow). The node always uses the
    system default analyst — no analyst configuration is exposed (C4).
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize the conversation resolved from the workflow run's context.

        Returns a small status dict. Already-finalized / not-found conditions are
        returned as a handled no-op; a conversation with no analyzable messages is
        surfaced as an error (re-raised) so the node faults consistently with the
        engine's error-surfacing convention.
        """
        thread_id = getattr(self.state, "thread_id", None)
        if thread_id is None:
            logger.info("FinalizeConversationNode: no thread_id in context, skipping finalize")
            return {"status": "skipped", "reason": "no_conversation"}

        try:
            conversation_id = UUID(str(thread_id))
        except (ValueError, TypeError):
            logger.info("FinalizeConversationNode: thread_id %r is not a conversation id, skipping", thread_id)
            return {"status": "skipped", "reason": "no_conversation"}

        service = injector.get(ConversationService)

        try:
            await service.finalize_in_progress_conversation(conversation_id=conversation_id)
        except AppException as exc:
            if exc.error_key in _NO_OP_ERROR_KEYS:
                logger.info(
                    "FinalizeConversationNode: handled no-op for conversation %s (%s)",
                    conversation_id,
                    exc.error_key.value,
                )
                return {
                    "status": "skipped",
                    "reason": exc.error_key.value,
                    "conversation_id": str(conversation_id),
                }
            # e.g. EMPTY_MESSAGES_FOR_CONVERSATION — surface as a node error (FR-8).
            logger.error(
                "FinalizeConversationNode: failed to finalize conversation %s (%s)",
                conversation_id,
                exc.error_key.value,
            )
            raise

        return {
            "status": "success",
            "finalized": True,
            "conversation_id": str(conversation_id),
        }
