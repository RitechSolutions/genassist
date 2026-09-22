"""Solo pool watchdog: a task that outlives its hard limit takes the worker down with it."""
from types import SimpleNamespace
from unittest.mock import patch

from app.tasks import solo_watchdog
from app.tasks.solo_watchdog import GRACE_SECONDS, TaskWatchdog, hard_limit_for, is_solo_pool


class FakeTimer:
    """Records the delay and fires only when told to."""

    started = []

    def __init__(self, interval, function, args=None, kwargs=None):
        self.interval = interval
        self._function = function
        self._args = args or ()
        self.cancelled = False
        self.daemon = False
        FakeTimer.started.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self._function(*self._args)


def _watchdog():
    FakeTimer.started = []
    exits = []
    return TaskWatchdog(terminate=lambda: exits.append(True), timer_factory=FakeTimer), exits


def _task(time_limit=7800, global_limit=480):
    conf = SimpleNamespace(task_time_limit=global_limit)
    return SimpleNamespace(name="execute_workflow_run", time_limit=time_limit, app=SimpleNamespace(conf=conf))


class TestTaskWatchdog:
    def test_arms_at_the_hard_limit_plus_grace(self):
        watchdog, _ = _watchdog()
        watchdog.arm("t1", "execute_test_suite_run", 7800)

        timer = FakeTimer.started[0]
        assert timer.interval == 7800 + GRACE_SECONDS
        assert timer.daemon is True

    def test_a_finished_task_disarms_its_timer(self):
        watchdog, exits = _watchdog()
        watchdog.arm("t1", "task", 10)
        watchdog.disarm("t1")
        FakeTimer.started[0].fire()

        assert FakeTimer.started[0].cancelled is True
        assert exits == []

    def test_an_expired_timer_stops_the_worker(self):
        watchdog, exits = _watchdog()
        watchdog.arm("t1", "task", 10)
        FakeTimer.started[0].fire()

        assert exits == [True]

    def test_disarming_an_unknown_task_is_harmless(self):
        watchdog, _ = _watchdog()
        watchdog.disarm("never-armed")


class TestHardLimitLookup:
    def test_a_task_with_its_own_limit_uses_it(self):
        assert hard_limit_for(_task(time_limit=7800), _task().app.conf) == 7800

    def test_a_task_without_one_falls_back_to_the_global_limit(self):
        assert hard_limit_for(_task(time_limit=None), _task().app.conf) == 480


class TestPoolDetection:
    def test_solo_is_recognised_by_name_or_class(self):
        from celery.concurrency.solo import TaskPool

        assert is_solo_pool("solo") is True
        assert is_solo_pool(TaskPool) is True

    def test_prefork_is_not_solo(self):
        from celery.concurrency.prefork import TaskPool

        assert is_solo_pool("prefork") is False
        assert is_solo_pool(TaskPool) is False


class TestWorkerWiring:
    def test_prefork_worker_installs_no_watchdog(self):
        with patch.object(solo_watchdog, "install") as install:
            solo_watchdog.on_worker_setup(instance=SimpleNamespace(pool_cls="prefork"))

        install.assert_not_called()

    def test_solo_worker_installs_the_watchdog(self):
        with patch.object(solo_watchdog, "install") as install:
            solo_watchdog.on_worker_setup(instance=SimpleNamespace(pool_cls="solo"))

        install.assert_called_once()

    def test_the_setting_switches_it_off(self):
        with patch.object(solo_watchdog.settings, "CELERY_SOLO_WATCHDOG_ENABLED", False), patch.object(
            solo_watchdog, "install"
        ) as install:
            solo_watchdog.on_worker_setup(instance=SimpleNamespace(pool_cls="solo"))

        install.assert_not_called()

    def test_task_start_and_end_arm_and_disarm(self):
        watchdog, _ = _watchdog()
        solo_watchdog.install(watchdog)

        solo_watchdog.on_task_start(task_id="t1", task=_task())
        assert FakeTimer.started[0].interval == 7800 + GRACE_SECONDS

        solo_watchdog.on_task_end(task_id="t1")
        assert FakeTimer.started[0].cancelled is True
