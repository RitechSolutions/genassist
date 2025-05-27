from pydantic import BaseModel, ConfigDict, EmailStr, Field
from uuid import UUID


class UserReadMinimal(BaseModel):
    id: UUID
    username: str
    password: str = Field(validation_alias="hashed_password")
    email: EmailStr

    model_config = ConfigDict(
        from_attributes = True
    )


class UserCreateMinimal(BaseModel):
    email: EmailStr
    model_config = ConfigDict(
        from_attributes = True
    )
