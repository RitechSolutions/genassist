from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class AgentSecuritySettingsBase(BaseModel):
    token_based_auth: bool = Field(
        default=False,
        description=(
            "If true, requires JWT token for conversation updates "
            "instead of API key."
        ),
    )
    token_expiration_minutes: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "JWT token expiration time in minutes. " "If null, uses global default."
        ),
    )
    cors_allowed_origins: Optional[str] = Field(
        None,
        description=(
            "Comma-separated list of allowed CORS origins. "
            "If null, uses global default."
        ),
    )
    rate_limit_conversation_start_per_minute: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Rate limit for conversation start per minute. "
            "If null, uses global default."
        ),
    )
    rate_limit_conversation_start_per_hour: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Rate limit for conversation start per hour. "
            "If null, uses global default."
        ),
    )
    rate_limit_conversation_update_per_minute: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Rate limit for conversation update per minute. "
            "If null, uses global default."
        ),
    )
    rate_limit_conversation_update_per_hour: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Rate limit for conversation update per hour. "
            "If null, uses global default."
        ),
    )
    recaptcha_enabled: Optional[bool] = Field(
        None,
        description=(
            "Enable reCAPTCHA for this agent. " "If null, uses global default."
        ),
    )
    recaptcha_project_id: Optional[str] = Field(
        None,
        max_length=200,
        description=("reCAPTCHA project ID. " "If null, uses global default."),
    )
    recaptcha_site_key: Optional[str] = Field(
        None,
        max_length=200,
        description=("reCAPTCHA site key. " "If null, uses global default."),
    )
    recaptcha_min_score: Optional[str] = Field(
        None,
        max_length=10,
        description=(
            "reCAPTCHA minimum score (0.0-1.0). " "If null, uses global default."
        ),
    )
    gcp_svc_account: Optional[str] = Field(
        None,
        description=(
            "GCP service account JSON in base64. " "If null, uses global default."
        ),
    )
    model_config = ConfigDict(from_attributes=True)


class AgentSecuritySettingsCreate(AgentSecuritySettingsBase):
    pass


class AgentSecuritySettingsUpdate(BaseModel):
    token_based_auth: Optional[bool] = None
    token_expiration_minutes: Optional[int] = Field(None, ge=1)
    cors_allowed_origins: Optional[str] = None
    rate_limit_conversation_start_per_minute: Optional[int] = Field(None, ge=1)
    rate_limit_conversation_start_per_hour: Optional[int] = Field(None, ge=1)
    rate_limit_conversation_update_per_minute: Optional[int] = Field(None, ge=1)
    rate_limit_conversation_update_per_hour: Optional[int] = Field(None, ge=1)
    recaptcha_enabled: Optional[bool] = None
    recaptcha_project_id: Optional[str] = None
    recaptcha_site_key: Optional[str] = None
    recaptcha_min_score: Optional[str] = None
    gcp_svc_account: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AgentSecuritySettingsRead(AgentSecuritySettingsBase):
    id: UUID
    agent_id: UUID
    model_config = ConfigDict(from_attributes=True)
