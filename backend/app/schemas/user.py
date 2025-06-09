from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, constr, ConfigDict
from typing import Optional
from typing import Annotated
from datetime import datetime
from app.schemas.api_key import ApiKeyBase
from app.schemas.operator_auth import OperatorAuth
from app.schemas.role import RoleRead



class UserTypeBase(BaseModel):
    name: str = Field(..., min_length=4, max_length=255, description="User type name")
    model_config = ConfigDict(
        from_attributes = True
    )


class UserTypeCreate(UserTypeBase):
    pass


class UserTypeRead(UserTypeBase):
    id: UUID = Field(..., description="User unique ID")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes = True
    )


class UserTypeUpdate(BaseModel):
    name: Optional[str] = Field(..., min_length=4, max_length=255, description="User type name")


# Base schema (shared attributes)
class UserBase(BaseModel):
    username: Annotated[str, constr(min_length=8, max_length=20)]
    email: EmailStr
    password: Annotated[str, constr(min_length=8, max_length=20)]
    is_active: int = 1  # Default value


# Used for user creation (excludes ID, timestamps)
class UserCreate(UserBase):
    role_ids: list[UUID] = Field(..., description="Roles IDs")
    user_type_id: UUID


class UserRead(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    is_active: int
    roles: list[RoleRead] = []
    user_type: Optional[UserTypeRead] = None
    api_keys: Optional[list[ApiKeyBase]] = []
    force_upd_pass_date: Optional[datetime] = Field(None,
                                                    description="Date when we force updating password date on login")

    model_config = ConfigDict(
        from_attributes = True
    )

class UserReadAuth(UserRead):
    permissions: Optional[list[str]] = Field([], description="Permissions needed for authorization")
    operator: Optional[OperatorAuth] = Field(None, description="Operator needed for authorization")

    model_config = ConfigDict(
        from_attributes = True
    )

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    is_active: int | None = None
    password: str | None = None
    user_type_id: UUID | None = None
    role_ids: list[UUID] | None = None
    notes: str | None = None


