"""Defaults for Help Center → Azure DevOps Boards integration."""

# Default work item type for bug reports (Basic/Agile/Scrum templates use "Bug").
DEFAULT_WORK_ITEM_TYPE = "Bug"

# Default Azure DevOps work item type per Help Center ticket type. These match the
# work item types available on Azure Boards (Agile/Scrum process templates).
WORK_ITEM_TYPE_BY_TICKET_TYPE = {
    "bug": "Bug",
    "feature": "Feature",
    "task": "Task",
}

# Standard ADO field reference names.
FIELD_TITLE = "System.Title"
FIELD_DESCRIPTION = "System.Description"
FIELD_STATE = "System.State"
FIELD_TAGS = "System.Tags"
FIELD_PRIORITY = "Microsoft.VSTS.Common.Priority"
FIELD_AREA_PATH = "System.AreaPath"
FIELD_REPRO_STEPS = "Microsoft.VSTS.TCM.ReproSteps"
FIELD_SYSTEM_INFO = "Microsoft.VSTS.TCM.SystemInfo"
FIELD_ACCEPTANCE_CRITERIA = "Microsoft.VSTS.Common.AcceptanceCriteria"

API_VERSION = "7.1"

# Local statuses mirrored from ADO (unknown ADO states map to "unknown").
OPEN_LOCAL_STATUSES = frozenset(
    {"new", "open", "sync_pending", "active", "in_progress", "unknown"}
)

# Terminal Azure DevOps states (lowercased). A ticket whose state is NOT one of
# these is considered "open" for duplicate detection. Kept as an exclusion list
# so it works across process templates and custom states without enumerating
# every possible open state (To Do, In Progress, In Review, On Hold, ...).
CLOSED_STATE_KEYWORDS = frozenset(
    {
        "done",
        "closed",
        "resolved",
        "removed",
        "completed",
        "cancelled",
        "canceled",
        "rejected",
        "abandoned",
    }
)
