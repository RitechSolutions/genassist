import base64
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from injector import inject
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.auth.utils import verify_password
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.api_key import ApiKeyInternal
from app.schemas.user import UserReadAuth
from app.services.api_keys import ApiKeysService
from app.services.users import UserService

logger = logging.getLogger(__name__)


def _load_pem_from_env(env_var: str) -> Optional[str]:
    """Load a PEM key from ``<env_var>`` (inline) or ``<env_var>_PATH`` (file)."""
    value = os.environ.get(env_var)
    if value:
        # Allow PEMs stored as single-line env vars with literal "\n" escapes.
        return value.replace("\\n", "\n")
    path = os.environ.get(f"{env_var}_PATH")
    if path:
        with open(path, "r") as fh:
            return fh.read()
    return None


def _b64url_uint(value: int) -> str:
    """Encode a non-negative integer as unpadded base64url (RFC 7518 §2)."""
    byte_len = (value.bit_length() + 7) // 8 or 1
    return (
        base64.urlsafe_b64encode(value.to_bytes(byte_len, "big"))
        .rstrip(b"=")
        .decode("ascii")
    )


@inject
class AuthService:
    def __init__(self):

        self.algorithm = os.environ.get("JWT_ALGORITHM", "RS256")
        self.access_token_expire_minutes = 60
        self.refresh_token_expire_days = 2

        self._private_key_pem = _load_pem_from_env("JWT_PRIVATE_KEY")
        self._public_key_pem = _load_pem_from_env("JWT_PUBLIC_KEY")
        self._kid_cache: Optional[str] = None

    def _require_signing_key(self) -> str:
        if not self._private_key_pem:
            raise RuntimeError(
                "JWT_PRIVATE_KEY (or JWT_PRIVATE_KEY_PATH) must be configured "
                "to sign tokens."
            )
        return self._private_key_pem

    def _require_verifying_key(self) -> str:
        if not self._public_key_pem:
            raise RuntimeError(
                "JWT_PUBLIC_KEY (or JWT_PUBLIC_KEY_PATH) must be configured "
                "to verify tokens."
            )
        return self._public_key_pem

    @property
    def verifying_key(self) -> str:
        """Public PEM used to verify signatures. Raises if not configured."""
        return self._require_verifying_key()

    @property
    def kid(self) -> str:
        if self._kid_cache is None:
            override = os.environ.get("JWT_KEY_ID")
            self._kid_cache = override or self._compute_kid(self._require_verifying_key())
        return self._kid_cache

    @staticmethod
    def _compute_kid(public_key_pem: str) -> str:
        # RFC 7638 JWK thumbprint: SHA-256 over the canonical JWK, base64url-encoded.
        # Stable across restarts as long as the public key is unchanged.
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise RuntimeError("JWT public key must be RSA.")
        numbers = public_key.public_numbers()
        jwk = {"e": _b64url_uint(numbers.e), "kty": "RSA", "n": _b64url_uint(numbers.n)}
        canonical = json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()
        return (
            base64.urlsafe_b64encode(hashlib.sha256(canonical).digest())
            .rstrip(b"=")
            .decode("ascii")
        )

    def public_jwk(self) -> dict[str, Any]:
        """Return the public verifying key as a JWK (for the JWKS endpoint)."""
        public_key = serialization.load_pem_public_key(
            self._require_verifying_key().encode()
        )
        numbers = public_key.public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": self.algorithm,
            "kid": self.kid,
            "n": _b64url_uint(numbers.n),
            "e": _b64url_uint(numbers.e),
        }

    def _encode(self, payload: dict) -> str:
        return jwt.encode(
            payload,
            self._require_signing_key(),
            algorithm=self.algorithm,
            headers={"kid": self.kid},
        )

    def _decode(self, token: str) -> dict:
        return jwt.decode(
            token, self._require_verifying_key(), algorithms=[self.algorithm]
        )

    async def _get_redis(self):
        from app.dependencies.injector import injector
        from app.dependencies.dependency_injection import RedisString

        return injector.get(RedisString)

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        try:
            to_encode = data.copy()
            expire = datetime.now(timezone.utc) + (
                expires_delta or timedelta(minutes=self.access_token_expire_minutes)
            )
            to_encode.update({"exp": expire, "typ": "access"})
            return self._encode(to_encode)
        except Exception as error:
            raise AppException(
                error_key=ErrorKey.ERROR_CREATE_TOKEN,
                error_detail="Error while creating access token",
                error_obj=error,
                status_code=401,
            )

    def create_refresh_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(days=self.refresh_token_expire_days)
        )
        to_encode.update({
            "exp": expire,
            "typ": "refresh",
            "jti": str(uuid.uuid4()),
        })
        return self._encode(to_encode)

    async def decode_jwt(self, token: str, expected_typ: str = "access") -> UserReadAuth:
        """Decode and validate a JWT, enforcing the ``typ`` claim.

        Args:
            token: The raw JWT string.
            expected_typ: Required value of the ``typ`` claim
                          (``"access"`` or ``"refresh"``).
        """
        try:
            payload = self._decode(token)

            # --- typ enforcement ---------------------------------------------------
            # Tokens minted before the typ claim was added will not have it.
            # Accept those for backward compatibility, but reject tokens whose typ
            # is present but does not match (e.g. an access token used on /refresh).
            token_typ = payload.get("typ")
            if token_typ is not None and token_typ != expected_typ:
                raise AppException(
                    status_code=401,
                    error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                    error_detail=f"Token type '{token_typ}' not accepted on this endpoint",
                )

            # --- Revocation check (refresh tokens only) ----------------------------
            jti = payload.get("jti")
            if expected_typ == "refresh" and jti:
                if await self._is_token_revoked(jti):
                    raise AppException(
                        status_code=401,
                        error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                        error_detail="Refresh token has been revoked",
                    )

            username = payload.get("sub")
            user_id = payload.get("user_id")

            if username is None or user_id is None:
                raise AppException(
                    status_code=401,
                    error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                    error_detail="JWT error: Username is None",
                )

            from app.dependencies.injector import injector

            user_service = injector.get(UserService)
            user: UserReadAuth | None = await user_service.get_by_id_for_auth(user_id)

            if user is None or not user.is_active:
                logger.warning("User not found or inactive: user_id=%s", user_id)
                raise AppException(error_key=ErrorKey.INVALID_USER, status_code=401)

            if user.force_upd_pass_date and user.force_upd_pass_date < datetime.now(
                timezone.utc
            ):
                raise AppException(
                    error_key=ErrorKey.FORCE_PASSWORD_UPDATE, status_code=401
                )

            return user
        except AppException:
            raise
        except ExpiredSignatureError as error:
            raise AppException(
                status_code=401,
                error_key=ErrorKey.EXPIRED_TOKEN,
                error_detail=f"Expired token: {error}",
            )
        except InvalidTokenError as error:
            raise AppException(
                status_code=401,
                error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                error_detail=f"JWT error: {error}",
                error_obj=error,
            )
        except RuntimeError as error:
            # Signing/verifying material is missing or invalid. This is a server
            # config issue, not a credential issue — return 503 so the frontend
            # does not interpret it as 401 (refresh-token loop) or 500 (retry).
            logger.exception("JWT verification unavailable: %s", error)
            raise AppException(
                status_code=503,
                error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                error_detail="Authentication temporarily unavailable, Runtime Error",
                error_obj=error,
            )

    # --- Refresh-token revocation ----------------------------------------------

    _REVOKED_PREFIX = "revoked_jti:"

    async def _is_token_revoked(self, jti: str) -> bool:
        """Check whether a refresh-token JTI has been revoked."""
        try:
            redis = await self._get_redis()
            return bool(await redis.exists(f"{self._REVOKED_PREFIX}{jti}"))
        except Exception:
            logger.warning("Redis unavailable for revocation check — allowing token")
            return False

    async def revoke_refresh_token(self, token: str) -> None:
        """Revoke a refresh token by storing its JTI in Redis.

        The key TTL matches the token's remaining lifetime so entries
        auto-expire and don't accumulate indefinitely.
        """
        try:
            payload = self._decode(token)
            jti = payload.get("jti")
            if not jti:
                return

            exp = payload.get("exp")
            ttl = int(exp - datetime.now(timezone.utc).timestamp()) if exp else self.refresh_token_expire_days * 86400
            if ttl <= 0:
                return  # already expired, nothing to revoke

            redis = await self._get_redis()
            await redis.setex(f"{self._REVOKED_PREFIX}{jti}", ttl, "1")
        except Exception:
            logger.warning("Failed to revoke refresh token — Redis may be unavailable")

    async def authenticate_api_key(self, api_key: str) -> ApiKeyInternal:
        """Authenticate and return API key object if valid."""
        from app.dependencies.injector import injector

        api_keys_service = injector.get(ApiKeysService)
        api_key = await api_keys_service.validate_and_get_api_key(api_key)
        if (
            api_key.user.force_upd_pass_date
            and api_key.user.force_upd_pass_date < datetime.now(timezone.utc)
        ):
            raise AppException(
                error_key=ErrorKey.FORCE_PASSWORD_UPDATE, status_code=401
            )
        return api_key

    async def authenticate_user(self, username_or_email: str, password: str):
        """Authenticate user by username or email and password."""
        from app.dependencies.injector import injector

        user_service = injector.get(UserService)
        user = await user_service.get_by_username_or_email(
            username_or_email, throw_not_found=False
        )
        # Check by email if not found by username
        if not user:
            raise AppException(
                error_key=ErrorKey.INVALID_USERNAME_OR_PASSWORD,
                status_code=401,
            )

        if not user.is_active:
            raise AppException(error_key=ErrorKey.INVALID_USER, status_code=401)

        if user.user_type.name == "console":
            raise AppException(error_key=ErrorKey.INVALID_USER_CONSOLE, status_code=401)

        if not verify_password(password, user.hashed_password):
            raise AppException(
                error_key=ErrorKey.INVALID_USERNAME_OR_PASSWORD,
                status_code=401,
            )

        return user

    def create_guest_token(
        self,
        tenant_id: str,
        agent_id: str,
        conversation_id: str,
        user_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a guest JWT token with limited permissions for conversation updates.
        This token is scoped to a specific tenant, agent, conversation, and user_id.
        The user_id comes from the API key used to start the conversation.
        """
        try:
            from app.core.permissions.constants import Permissions as P

            to_encode = {
                "sub": f"guest:{conversation_id}",
                "user_id": user_id,  # User ID from the API key used to start conversation
                "type": "guest",
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "permissions": [
                    P.Conversation.UPDATE_IN_PROGRESS
                ],  # Limited permission
            }
            expire = datetime.now(timezone.utc) + (
                expires_delta or timedelta(hours=24)
            )  # Default 24 hours for guest tokens
            to_encode.update({"exp": expire})
            return self._encode(to_encode)
        except Exception as error:
            raise AppException(
                error_key=ErrorKey.ERROR_CREATE_TOKEN,
                error_detail="Error while creating guest token",
                error_obj=error,
                status_code=401,
            )

    async def decode_guest_token(self, token: str) -> dict:
        """
        Decode a guest JWT token and return its payload.
        Returns dict with tenant_id, agent_id, conversation_id, user_id, and permissions.
        """
        try:
            payload = self._decode(token)
            token_type = payload.get("type")

            if token_type != "guest":
                raise AppException(
                    status_code=401,
                    error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                    error_detail="Token is not a guest token",
                )

            return {
                "tenant_id": payload.get("tenant_id"),
                "agent_id": payload.get("agent_id"),
                "conversation_id": payload.get("conversation_id"),
                "user_id": payload.get("user_id"),  # User ID from API key
                "permissions": payload.get("permissions", []),
            }
        except ExpiredSignatureError as error:
            raise AppException(
                status_code=401,
                error_key=ErrorKey.EXPIRED_TOKEN,
                error_detail=f"Expired token: {error}",
            )
        except InvalidTokenError as error:
            raise AppException(
                status_code=401,
                error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                error_detail=f"JWT error: {error}",
                error_obj=error,
            )
        except RuntimeError as error:
            logger.exception("Guest JWT verification unavailable: %s", error)
            raise AppException(
                status_code=503,
                error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                error_detail="Authentication temporarily unavailable, Runtime Error",
                error_obj=error,
            )
