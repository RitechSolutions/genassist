from enum import Enum


class IssueStatus(Enum):
    """Lifecycle status of a reported issue (a comment left on a message)."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


# Terminal states — used to stamp resolved_by / resolved_at.
TERMINAL_ISSUE_STATUSES = frozenset({IssueStatus.RESOLVED, IssueStatus.WONT_FIX})
