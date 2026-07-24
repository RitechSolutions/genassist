"""User-facing sub-agent delegation messages"""

CONVERSATION_UNRESUMABLE = "This conversation could not be resumed. Please start a new message."
DELEGATION_DEPTH_REACHED = "The sub-agent delegation depth limit was reached."
DELEGATION_IN_PROGRESS = "Another sub-agent delegation is already in progress for this turn."
NEEDS_INTERACTIVE_SESSION = "This sub-agent needs an interactive chat session and can't be used in this context."
CHILD_FAILED = "The sub-agent could not complete the task."


def child_failed(*, retry: bool = False) -> str:
    """Generic child failure; the resume surface asks the user to retry."""
    return f"{CHILD_FAILED} Please try again." if retry else CHILD_FAILED


def child_timeout(timeout_seconds: float, *, retry: bool = False) -> str:
    """Child ran past its timeout; the resume surface asks the user to resend."""
    msg = f"The sub-agent did not respond in time ({int(timeout_seconds)}s)."
    return f"{msg} Please send your message again." if retry else msg
