from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
<<<<<<< HEAD
=======
from typing import Literal
>>>>>>> development

class RoleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    is_active: Optional[int] = Field(1, description="1 = active, 0 = inactive")
<<<<<<< HEAD
=======
    role_type: Optional[Literal["internal", "external"]] = Field("external",
                                                                 description="Used to filter roles that can be used "
                                                            "directly to create a user, or need to go to specific menu")
>>>>>>> development

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    is_active: Optional[int] = Field(None)
<<<<<<< HEAD

=======
    role_type: Optional[Literal["internal", "external"]] = Field(None)
>>>>>>> development

class RoleRead(RoleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes = True
    )