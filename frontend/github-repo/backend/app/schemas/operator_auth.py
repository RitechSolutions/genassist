from pydantic import BaseModel, ConfigDict
from uuid import UUID


class OperatorAuth(BaseModel):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

