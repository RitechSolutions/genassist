from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from app.schemas.operator_auth import OperatorAuth
from app.schemas.role import RoleRead


class UserAuth(BaseModel):
    id: UUID
    operator: Optional[OperatorAuth] = None
    # roles: list[RoleRead] = Field([], exclude=True)
    # permissions: list[str] = Field([], exclude=True)


    model_config = ConfigDict(
        from_attributes = True
    )