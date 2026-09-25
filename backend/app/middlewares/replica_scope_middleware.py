"""
Marks HTTP request scopes as eligible for read-replica routing.

Plain ASGI rather than BaseHTTPMiddleware so it observes every scope type. Only
HTTP scopes are marked: a websocket scope lives for the whole connection, so a
read session resolved there would hold a replica connection until disconnect.
Unmarked scopes fall back to the writer, which is the safe direction.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from app.db.read_routing import allow_replica_reads, reset_replica_reads


class ReplicaScopeMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = allow_replica_reads()
        try:
            await self.app(scope, receive, send)
        finally:
            reset_replica_reads(token)
