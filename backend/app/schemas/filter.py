from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from uuid import UUID

class BaseFilterModel(BaseModel):
<<<<<<< HEAD
    skip: int = Field(0, ge=0)
    limit: int = Field(10, ge=1, le=100)
    from_date: Optional[date] = Field(None, description="Start date (YYYY-MM-DD)")
    to_date: Optional[date] = Field(None, description="End date (YYYY-MM-DD)")
=======
    skip: int = Field(0, ge=0, description="The number of rows to skip before returning results")
    limit: int = Field(10, ge=1, le=100, description="The number of rows to return per page")
    from_date: Optional[date] = Field(None, description="Start date (YYYY-MM-DD)")
    to_date: Optional[date] = Field(None, description="End date (YYYY-MM-DD)")
    operator_id: Optional[UUID] = Field(None, description="Operator who made the conversation")
>>>>>>> development



class ConversationFilter(BaseFilterModel):
    conversation_status: Optional[str] = None
    minimum_hostility_score: Optional[int] = None
<<<<<<< HEAD
=======

class ApiKeysFilter(BaseFilterModel):
    user_id: Optional[UUID] = Field(None, description="Agent who's user owns the api key")

>>>>>>> development
    
    
class RecordingFilter(BaseFilterModel):
    operator_id: Optional[UUID] = None

