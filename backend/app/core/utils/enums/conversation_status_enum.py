from enum import Enum


class ConversationStatus(Enum):
    IN_PROGRESS = "in_progress"
    FINALIZED = "finalized"
    TAKE_OVER = "takeover"
