from fastapi import WebSocket, Query, WebSocketException, Depends
from schemas.auth import AuthenticatedUser
from auth.token_verifier import AuthenticationError


def require_authenticated_user(required_permissions: list[str]):
    """
    Factory that returns a dependency callable for WebSocket authentication.

    Usage:
        dependencies=[Depends(require_authenticated_user(["perm1", "perm2"]))]
    """

    async def _dependency(
        websocket: WebSocket,
        access_token: str | None = Query(default=None),
        api_key: str | None = Query(default=None),
    ) -> AuthenticatedUser:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("WS auth dependency called, access_token=%s, api_key=%s", bool(access_token), bool(api_key))

        if not websocket:
            raise WebSocketException(code=4401, reason="WebSocket not found")

        if not access_token and not api_key:
            raise WebSocketException(code=4401, reason="Missing credentials")

        verifier = websocket.app.state.verifier
        tenant_id = websocket.query_params.get("x-tenant-id") or "master"

        try:
            return await verifier.verify(
                access_token,
                api_key,
                required_permissions,
                tenant_id,
            )
        except AuthenticationError as exc:
            # Close the WebSocket with an auth-specific code before route handler runs
            raise WebSocketException(code=4401, reason=exc.detail)

    return Depends(_dependency)
