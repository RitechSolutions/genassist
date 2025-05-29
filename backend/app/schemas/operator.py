from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
<<<<<<< HEAD

from app.schemas.conversation import ConversationRead
from app.schemas.operator_statistics import OperatorStatisticsRead, OperatorStatisticsCreate

=======
from app.schemas.conversation import ConversationRead
from app.schemas.operator_statistics import OperatorStatisticsRead, OperatorStatisticsCreate
from app.schemas.user_minimal import UserCreateMinimal, UserReadMinimal
>>>>>>> development


class OperatorBase(BaseModel):
    """Shared attributes for Operators"""
    first_name: str = Field(..., min_length=2, alias="firstName", description="First name of the agent")
    last_name: str = Field(..., min_length=2, alias="lastName", description="Last name of the agent")
    avatar: Optional[bytes] = None
    user: UserCreateMinimal


class OperatorCreate(OperatorBase):
    """Used when creating a new Operator with statistics"""
    operator_statistics: OperatorStatisticsCreate  # Embedded in request

class OperatorRead(OperatorBase):
    """Used for returning Operator data with statistics"""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    updated_at: datetime
    operator_statistics: Optional[OperatorStatisticsRead] = None  # Only one statistics entry
    latest_conversation_analysis: Optional[ConversationRead] = None
    is_active: Optional[int] = 1

    model_config = ConfigDict(
            from_attributes = True,
            populate_by_name=True
            )

class OperatorReadAfterCreate(OperatorRead):
    user: UserReadMinimal