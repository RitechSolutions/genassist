from enum import Enum

DEFAULT_ISSUE_STATUS_KEY = "open"


class IssueStatusCategory(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


# (key, label, category, position, color)
DEFAULT_ISSUE_STATUSES = (
    ("open", "Open", IssueStatusCategory.TODO.value, 0, "amber"),
    ("in_progress", "In Progress", IssueStatusCategory.IN_PROGRESS.value, 1, "blue"),
    ("needs_help_desk_fix", "Needs Help Desk Fix", IssueStatusCategory.IN_PROGRESS.value, 2, "purple"),
    ("qa_approved", "QA Approved", IssueStatusCategory.IN_PROGRESS.value, 3, "teal"),
    ("resolved", "Resolved", IssueStatusCategory.DONE.value, 4, "emerald"),
    ("wont_fix", "Won't Fix", IssueStatusCategory.DONE.value, 5, "zinc"),
)
