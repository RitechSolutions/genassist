"""Beat leader lock and scheduler-loop heartbeat."""
import time
from unittest.mock import MagicMock, patch

import pytest
import redis

from app.tasks import beat_leader
from app.tasks.beat_leader import BeatLeaderLock, install_tick_heartbeat


class FakeRedis:
    """Just enough of SET NX EX and the compare-and-expire script."""

    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def eval(self, script, numkeys, key, token, ttl):
        return 1 if self.store.get(key) == token else 0

    def release(self, key):
        self.store.pop(key, None)


def _lock(client, token="beat-a", **overrides):
    return BeatLeaderLock(client, token, ttl_seconds=60, sleep=lambda _: None, **overrides)


class TestLeaderLock:
    def test_first_beat_becomes_leader_immediately(self):
        client = FakeRedis()
        _lock(client).wait_until_leader()
        assert client.store[beat_leader.LEADER_KEY] == "beat-a"

    def test_second_beat_stands_by_until_the_lock_is_released(self):
        client = FakeRedis()
        _lock(client, "beat-a").wait_until_leader()
        waits = []

        def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 3:
                client.release(beat_leader.LEADER_KEY)

        BeatLeaderLock(client, "beat-b", ttl_seconds=60, sleep=sleep).wait_until_leader()

        assert len(waits) == 3
        assert client.store[beat_leader.LEADER_KEY] == "beat-b"

    def test_redis_errors_while_waiting_are_retried(self):
        client = MagicMock()
        client.set.side_effect = [redis.ConnectionError("down"), True]

        _lock(client).wait_until_leader()

        assert client.set.call_count == 2

    def test_leader_renews_its_own_lock(self):
        client = FakeRedis()
        lock = _lock(client, step_down=MagicMock())
        lock.wait_until_leader()

        assert lock.renew_once() is True
        lock._step_down.assert_not_called()

    def test_losing_the_lock_stops_this_scheduler(self):
        client = FakeRedis()
        step_down = MagicMock()
        lock = _lock(client, "beat-a", step_down=step_down)
        lock.wait_until_leader()
        client.store[beat_leader.LEADER_KEY] = "beat-b"

        assert lock.renew_once() is False
        step_down.assert_called_once()

    def test_renewal_survives_a_redis_error(self):
        client = MagicMock()
        client.eval.side_effect = redis.ConnectionError("down")
        step_down = MagicMock()

        assert _lock(client, step_down=step_down).renew_once() is True
        step_down.assert_not_called()


class TestTickHeartbeat:
    def test_every_tick_refreshes_the_heartbeat_and_still_ticks(self, tmp_path):
        heartbeat = tmp_path / "beat_heartbeat"
        scheduler = MagicMock()
        scheduler.tick.return_value = 5.0
        install_tick_heartbeat(scheduler, str(heartbeat))

        before = int(time.time())
        assert scheduler.tick() == 5.0

        assert int(heartbeat.read_text()) >= before
        assert not (tmp_path / "beat_heartbeat.tmp").exists()

    def test_heartbeat_write_failure_does_not_break_the_tick(self, tmp_path):
        scheduler = MagicMock()
        scheduler.tick.return_value = 1.0
        install_tick_heartbeat(scheduler, str(tmp_path / "missing-dir" / "heartbeat"))

        assert scheduler.tick() == 1.0


class TestBeatInitHook:
    def test_hook_installs_heartbeat_and_waits_for_leadership(self):
        service = MagicMock()
        lock = MagicMock()
        with patch.object(beat_leader, "install_tick_heartbeat") as heartbeat, patch.object(
            beat_leader, "_redis_client"
        ), patch.object(beat_leader, "BeatLeaderLock", return_value=lock), patch.object(
            beat_leader.settings, "CELERY_BEAT_LEADER_LOCK_ENABLED", True
        ):
            beat_leader.on_beat_init(sender=service)

        heartbeat.assert_called_once_with(service.scheduler)
        lock.wait_until_leader.assert_called_once()
        lock.start_renewal_thread.assert_called_once()

    def test_lock_can_be_disabled_by_setting(self):
        service = MagicMock()
        with patch.object(beat_leader, "install_tick_heartbeat"), patch.object(
            beat_leader, "BeatLeaderLock"
        ) as lock_cls, patch.object(beat_leader.settings, "CELERY_BEAT_LEADER_LOCK_ENABLED", False):
            beat_leader.on_beat_init(sender=service)

        lock_cls.assert_not_called()


@pytest.mark.parametrize("ttl", [30, 60, 120])
def test_standby_polls_more_often_than_the_lock_expires(ttl):
    waits = []
    client = FakeRedis()
    client.store[beat_leader.LEADER_KEY] = "someone-else"

    def sleep(seconds):
        waits.append(seconds)
        client.release(beat_leader.LEADER_KEY)

    BeatLeaderLock(client, "me", ttl_seconds=ttl, sleep=sleep).wait_until_leader()

    assert waits == [ttl / 6]
