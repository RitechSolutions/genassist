"""Defaults for Help Center → Azure DevOps Boards integration."""

# Default work item type for bug reports (Basic/Agile/Scrum templates use "Bug").
DEFAULT_WORK_ITEM_TYPE = "Bug"

# Standard ADO field reference names.
FIELD_TITLE = "System.Title"
FIELD_DESCRIPTION = "System.Description"
FIELD_STATE = "System.State"
FIELD_TAGS = "System.Tags"
FIELD_PRIORITY = "Microsoft.VSTS.Common.Priority"
FIELD_AREA_PATH = "System.AreaPath"

API_VERSION = "7.1"

# Local statuses mirrored from ADO (unknown ADO states map to "unknown").
OPEN_LOCAL_STATUSES = frozenset(
    {"new", "open", "sync_pending", "active", "in_progress", "unknown"}
)
