from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from functools import lru_cache


@lru_cache
def get_socket_connection_manager() -> SocketConnectionManager:
    """FastAPI dependency – always returns the same singleton."""
    return SocketConnectionManager()
