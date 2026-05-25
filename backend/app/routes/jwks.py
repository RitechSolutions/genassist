from __future__ import annotations

from fastapi import APIRouter

from app.dependencies.injector import injector
from app.services.auth import AuthService

router = APIRouter()


@router.get("/.well-known/jwks.json")
async def jwks() -> dict:
    """JWKS for external platforms to verify tokens signed by this service.

    Returns the RSA public key in JWK Set format (RFC 7517). External consumers
    can fetch this and verify access / refresh / guest JWTs without ever
    holding any signing material.
    """
    auth = injector.get(AuthService)
    return {"keys": [auth.public_jwk()]}