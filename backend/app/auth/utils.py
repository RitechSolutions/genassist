import re
import secrets
import hashlib
import string
import unicodedata

from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from passlib.context import CryptContext
from uuid import UUID
from starlette_context import context
from contextvars import ContextVar
from uuid import UUID
from typing import Optional

API_KEY_HEADER_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)  

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token",
                                     auto_error=False) 

socket_user_id: ContextVar[Optional[UUID]] = ContextVar("socket_user_id", default=None)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def has_permission(available, *required:  str) -> bool:
    return all([permission in available or "*" in available for permission in required])


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def generate_api_key(length: int = 40) -> str:
    return secrets.token_urlsafe(length)

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

def get_current_user_id() -> UUID:
    return socket_user_id.get() or (context.get("user_id") if context.exists() else None)

def get_current_operator_id() -> UUID:
    return context.get("operator_id") if context.exists() else None

def current_user_is_supervisor() -> bool:
     roles = context.get("user_roles") if context.exists() else None
     if roles:
         return "supervisor" in [role.name for role in roles]
     return False


def current_user_is_admin() -> bool:
    roles = context.get("user_roles") if context.exists() else None
    if roles:
        return "admin" in [role.name for role in roles]
    return False

def is_current_user_internal():
    roles = context.get("user_roles") if context.exists() else None
    if roles:
        internal_roles = ["admin", "operator", "supervisor"]
        return any(role.name in internal_roles for role in roles)
    return False

# def has_permission(user_or_api_key, required: str) -> bool:
#     return required in user_or_api_key.permissions or "*" in user_or_api_key.permissions


def generate_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def generate_unique_username(user_repository, first: str, last: str) -> str:
    # slugify → "brendon_shuke"
    base = unicodedata.normalize("NFKD", f"{first}_{last}") \
           .encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base).strip("_")
    candidate = base
    suffix = 1
    while await user_repository.get_by_username(candidate):
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def is_current_user_supervisor_or_admin():
    return current_user_is_supervisor() or current_user_is_admin()