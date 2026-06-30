from unittest.mock import AsyncMock, patch

import pytest

from app.core.config.help_center_ado import resolve_work_item_type
from app.modules.integration.azure_devops import AzureDevOpsConnector


def test_create_work_item_url_uses_json_patch_and_work_item_type():
    connector = AzureDevOpsConnector(
        organization_url="https://dev.azure.com/my-org",
        project="My Project",
        pat="test-pat",
        work_item_type="Bug",
    )
    url = (
        f"{connector._project_base()}/_apis/wit/workitems/"
        f"$User%20Story?api-version=7.1"
    )

    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"id": 42, "url": "https://dev.azure.com/my-org/_apis/wit/workItems/42"}

        import asyncio

        asyncio.run(
            connector.create_work_item(
                "Sample task",
                "<p>Details</p>",
                tags=["genassist"],
                work_item_type="User Story",
            )
        )

        mock_request.assert_awaited_once()
        method, called_url = mock_request.await_args.args[:2]
        assert method == "POST"
        assert called_url == url
        kwargs = mock_request.await_args.kwargs
        assert kwargs["content_type"] == "application/json-patch+json"
        body = kwargs["json_body"]
        assert body[0] == {"op": "add", "path": "/fields/System.Title", "value": "Sample task"}
        assert body[1]["path"] == "/fields/System.Description"


@pytest.mark.parametrize(
    ("ticket_type", "bug_type", "feature_type", "task_type", "expected"),
    [
        # Defaults map each ticket type to its matching Azure Boards work item type.
        ("bug", "Bug", None, None, "Bug"),
        ("feature", "Bug", None, None, "Feature"),
        ("task", "Bug", None, None, "Task"),
        # Per-type overrides win when configured.
        ("feature", "Bug", "User Story", None, "User Story"),
        ("task", "Bug", None, "Custom Task", "Custom Task"),
        # Unknown types fall back to the bug/default work item type.
        ("unknown", "Bug", None, None, "Bug"),
    ],
)
def test_resolve_work_item_type(ticket_type, bug_type, feature_type, task_type, expected):
    with patch("app.core.config.help_center_ado.settings") as mock_settings:
        mock_settings.AZURE_DEVOPS_WORK_ITEM_TYPE = bug_type
        mock_settings.AZURE_DEVOPS_FEATURE_WORK_ITEM_TYPE = feature_type
        mock_settings.AZURE_DEVOPS_TASK_WORK_ITEM_TYPE = task_type
        assert resolve_work_item_type(ticket_type) == expected
