# app/auth/jwt_dependencies.py
import os
from fastapi.security import HTTPBearer, APIKeyHeader
from fastapi import Depends, HTTPException, status, Header,  Security
from jose import jwt, JWTError, ExpiredSignatureError
from app.core.tenant_scope import get_tenant_context

security = HTTPBearer()

JWT_SECRET = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"

# to fix apperance in Swagger -
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)

def validate_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header missing",
        )
    return api_key



def encode_jwt(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    

def verify_plugin_stst(
    credentials=Depends(security),
    api_key: str = Depends(validate_api_key),
):
    payload = decode_jwt(credentials.credentials)

    if payload.get("scope") != "chat":
        raise HTTPException(status_code=403, detail="Invalid scope")

    if payload.get("aud") != "conversation-api":
        raise HTTPException(status_code=403, detail="Invalid audience")

    if payload.get("api_key") != api_key:
        raise HTTPException(status_code=403, detail="API key mismatch")

    return payload