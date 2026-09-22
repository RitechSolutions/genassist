"""
Guards for the Celery beat scheduler.

Beat has no leader election, so several replicas dispatch every scheduled task
several times. A Redis lock lets one replica dispatch while the others stand by
and take over if it disappears. A heartbeat written from the scheduler loop
itself lets a liveness probe tell a frozen scheduler from a healthy one.
"""

import logging
import os
import signal
import socket
import threading
import time
from typing import Callable, Optional

import redis
from celery.signals import beat_init

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

LEADER_KEY = "{celery}beat-leader"
HEARTBEAT_FILE = os.environ.get("CELERY_BEAT_HEARTBEAT_FILE", "/tmp/celery_beat_heartbeat")
# A loop that has not ticked for this long is frozen; its lock must be allowed to expire
STALE_SCHEDULER_SECONDS = 600

_RENEW_IF_OWNER = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


def _terminate_self() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


class TickMonitor:
    """Remembers when the scheduler loop last ticked."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.last_tick_at = clock()

    def record_tick(self) -> None:
        self.last_tick_at = self._clock()

    def is_alive(self, max_stale_seconds: int = STALE_SCHEDULER_SECONDS) -> bool:
        return self._clock() - self.last_tick_at < max_stale_seconds


class BeatLeaderLock:
    """Hold a Redis lock while this beat dispatches; other replicas wait as standbys."""

    def __init__(
        self,
        client,
        token: str,
        ttl_seconds: int,
        sleep: Callable[[float], None] = time.sleep,
        step_down: Callable[[], None] = _terminate_self,
        loop_is_alive: Callable[[], bool] = lambda: True,
    ):
        self._client = client
        self._token = token
        self._ttl = ttl_seconds
        self._sleep = sleep
        self._step_down = step_down
        self._loop_is_alive = loop_is_alive

    def try_acquire(self) -> bool:
        return bool(self._client.set(LEADER_KEY, self._token, nx=True, ex=self._ttl))

    def renew(self) -> bool:
        return bool(self._client.eval(_RENEW_IF_OWNER, 1, LEADER_KEY, self._token, self._ttl))

    def still_owner(self) -> bool:
        return self._client.get(LEADER_KEY) == self._token

    def wait_until_leader(self) -> None:
        while True:
            try:
                if self.try_acquire():
                    logger.info("This beat holds the leader lock and will dispatch")
                    return
                logger.info("Another beat holds the leader lock; standing by")
            except redis.RedisError as exc:
                logger.warning("Beat leader lock check failed: %s", exc)
            heartbeat_while_standing_by()
            self._sleep(self._ttl / 6)

    def start_renewal_thread(self) -> None:
        thread = threading.Thread(target=self.renew_forever, name="beat-leader", daemon=True)
        thread.start()

    def renew_forever(self) -> None:
        while True:
            self._sleep(self._ttl / 3)
            if not self.renew_once():
                return

    def renew_once(self) -> bool:
        """Renew while the loop is alive; a frozen loop lets the lock expire instead."""
        try:
            if self._loop_is_alive():
                owned = self.renew()
            else:
                logger.warning("Scheduler loop is stale; not renewing the beat leader lock")
                owned = self.still_owner()
        except redis.RedisError as exc:
            logger.warning("Beat leader lock renewal failed: %s", exc)
            return True
        if owned:
            return True
        logger.critical("Beat leader lock was lost; stopping this scheduler")
        self._step_down()
        return False


def write_heartbeat(path: str = HEARTBEAT_FILE) -> None:
    """Write the current time atomically so a probe never reads a half-written file."""
    temporary = f"{path}.tmp"
    with open(temporary, "w") as handle:
        handle.write(str(int(time.time())))
    os.replace(temporary, path)


def heartbeat_while_standing_by() -> None:
    """A healthy standby never ticks, so it must satisfy the liveness probe itself."""
    try:
        write_heartbeat()
    except OSError as exc:
        logger.warning("Beat heartbeat write failed: %s", exc)


def install_tick_heartbeat(
    scheduler, path: str = HEARTBEAT_FILE, monitor: Optional[TickMonitor] = None
) -> TickMonitor:
    """Record and publish every scheduler tick, from the loop that can freeze."""
    monitor = monitor or TickMonitor()
    original_tick = scheduler.tick

    def tick(*args, **kwargs):
        monitor.record_tick()
        try:
            write_heartbeat(path)
        except OSError as exc:
            logger.warning("Beat heartbeat write failed: %s", exc)
        return original_tick(*args, **kwargs)

    scheduler.tick = tick
    return monitor


def _redis_client():
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=settings.CELERY_REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.CELERY_REDIS_SOCKET_CONNECT_TIMEOUT,
        socket_keepalive=True,
        health_check_interval=30,
    )


def _token() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


@beat_init.connect
def on_beat_init(sender=None, **kwargs):
    monitor = install_tick_heartbeat(sender.scheduler)
    if not settings.CELERY_BEAT_LEADER_LOCK_ENABLED:
        return
    lock = BeatLeaderLock(
        _redis_client(),
        _token(),
        settings.CELERY_BEAT_LEADER_LOCK_TTL_SECONDS,
        loop_is_alive=monitor.is_alive,
    )
    lock.wait_until_leader()
    monitor.record_tick()
    lock.start_renewal_thread()
