import uuid
from unittest.mock import MagicMock, patch

from app.tasks.ml_model_pipeline_tasks import (
    _notify_run_failed,
    _summarize_run_failure,
    _training_succeeded,
)


class TestTrainingSucceeded:
    def test_true_when_output_success_is_true(self):
        assert _training_succeeded({"output": {"success": True, "metrics": {"accuracy": 0.9}}}) is True

    def test_false_when_output_missing(self):
        assert _training_succeeded({}) is False
        assert _training_succeeded({"output": None}) is False

    def test_false_when_output_is_an_error_object(self):
        execution_output = {"output": {"error": "value missing for required key: message"}}
        assert _training_succeeded(execution_output) is False

    def test_true_even_when_has_failures_is_true(self):
        """
        A workflow can have an unrelated, disconnected node fail (e.g. a
        leftover chat "Start" node never wired into the training chain)
        while the actual Train Data Source -> Train Model chain still
        completes and produces real metrics. has_failures=True must NOT
        make this look like a failed run, or every model whose graph has
        such a vestigial node would wrongly disappear from Evaluate Model.
        """
        execution_output = {
            "has_failures": True,
            "failed_nodes": [
                {"name": "Start", "type": "chatInputNode", "error": "value missing for required key: message"}
            ],
            "output": {"success": True, "metrics": {"r2_score": 0.98}},
        }
        assert _training_succeeded(execution_output) is True


class TestSummarizeRunFailure:
    def test_prefers_the_final_output_error(self):
        execution_output = {
            "output": {"error": "value missing for required key: message"},
            "failed_nodes": [{"name": "Start", "error": "some other error"}],
        }
        assert _summarize_run_failure(execution_output) == "value missing for required key: message"

    def test_falls_back_to_failed_nodes_when_no_output_error(self):
        execution_output = {
            "output": {},
            "failed_nodes": [
                {"name": "Train Data Source", "error": "file_not_found"},
            ],
        }
        assert _summarize_run_failure(execution_output) == "Train Data Source: file_not_found"

    def test_multiple_failed_nodes_are_joined(self):
        execution_output = {
            "failed_nodes": [
                {"node_id": "abc", "name": "Start", "error": "value missing for required key: message"},
                {"node_id": "def", "name": "Train Data Source", "error": "file_not_found"},
            ]
        }
        assert _summarize_run_failure(execution_output) == (
            "Start: value missing for required key: message; Train Data Source: file_not_found"
        )

    def test_missing_name_falls_back_to_node_id(self):
        execution_output = {"failed_nodes": [{"node_id": "abc-123", "error": "boom"}]}
        assert _summarize_run_failure(execution_output) == "abc-123: boom"

    def test_generic_message_when_nothing_to_report(self):
        assert _summarize_run_failure({}) == "Workflow execution completed without producing a successful result"


class TestNotifyRunFailed:
    @patch("app.tasks.ml_model_pipeline_tasks.emit_notification")
    @patch("app.tasks.ml_model_pipeline_tasks.injector")
    def test_emits_error_notification_with_run_id(self, mock_injector, mock_emit_notification):
        mock_socket_manager = MagicMock()
        mock_injector.get.return_value = mock_socket_manager
        run_id = uuid.uuid4()

        _notify_run_failed("tenant-1", run_id)

        mock_emit_notification.assert_called_once()
        kwargs = mock_emit_notification.call_args.kwargs
        assert kwargs["socket_connection_manager"] is mock_socket_manager
        assert kwargs["tenant_id"] == "tenant-1"
        payload = kwargs["payload"]
        assert payload["entity_id"] == str(run_id)
        assert payload["entity_kind"] == "pipeline_run"
        assert payload["type"] == "error"
        assert payload["action_url"] == "/ml-models"
