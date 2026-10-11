from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.utils.enums.issue_status_enum import IssueStatusCategory

IssueStatusColor = Literal["amber", "blue", "purple", "teal", "emerald", "zinc", "red", "orange", "sky", "pink"]
ISSUE_STATUS_KEY_PATTERN = r"^[a-z][a-z0-9_]{1,49}$"
RESERVED_ISSUE_STATUS_KEYS = frozenset({"all"})

IssueStatusLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class IssueStatusRead(BaseModel):
    id: UUID
    key: str
    label: str
    category: IssueStatusCategory
    position: int
    color: str
    is_active: int

    model_config = ConfigDict(from_attributes=True)


class IssueStatusCreate(BaseModel):
    key: str = Field(..., pattern=ISSUE_STATUS_KEY_PATTERN)
    label: IssueStatusLabel
    category: IssueStatusCategory
    color: IssueStatusColor

    @field_validator("key")
    @classmethod
    def key_not_reserved(cls, value: str) -> str:
        if value in RESERVED_ISSUE_STATUS_KEYS:
            raise ValueError(f'"{value}" is reserved')
        return value


class IssueStatusEdit(BaseModel):
    label: Optional[IssueStatusLabel] = None
    category: Optional[IssueStatusCategory] = None
    color: Optional[IssueStatusColor] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)


class IssueStatusOrder(BaseModel):
    keys: list[str] = Field(..., min_length=1)
