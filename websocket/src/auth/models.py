from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    permissions: list[str]
    tenant_id: str
    token_exp: int | None = None  # Unix timestamp



class VerifyTokenRequest(BaseModel):
    access_token: Optional[str] = None
    api_key: Optional[str] = None
    required_permissions: list[str] = []
    tenant_id: str = "master"

class VerifyTokenResponse:
    user_id: str
    permissions: list[str]
    tenant_id: str
    token_exp: Optional[int] = None