"""The email task runs like every other task, on the unpooled background engine."""
from unittest.mock import patch

from app.core.tenant_scope import is_background_task
from app.tasks.email_tasks import send_email_task


def test_email_task_runs_in_the_background_context():
    """Outside it, the task's sessions came from the pooled engine and could outlive its event loop."""
    seen = {}

    def fake_run(coro, **_kwargs):
        seen["background"] = is_background_task()
        coro.close()
        return {"status": "sent"}

    with patch("app.tasks.email_tasks.run_async_in_celery", fake_run):
        assert send_email_task(to="user@example.com", subject="Hi", template_name="generic_notification") == {
            "status": "sent"
        }

    assert seen["background"] is True
    assert is_background_task() is False
