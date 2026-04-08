import json
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.conversation_topic_enum import ConversationTopic
from app.core.utils.enums.sentiment_enum import Sentiment
from app.core.utils.enums.sort_direction_enum import SortDirection
from app.core.utils.enums.sort_field_enum import SortField


class BaseFilterModel(BaseModel):
    skip: int = Field(0, ge=0, description="The number of rows to skip before returning results")
    limit: int = Field(20, ge=1, le=100, description="The number of rows to return per page")
    from_date: Optional[date] = Field(None, description="Start date (YYYY-MM-DD)")
    to_date: Optional[datetime] = Field(None, description="End datetime (YYYY-MM-DD 23:59)")
    operator_id: Optional[UUID] = Field(None, description="Operator who made the conversation")
    order_by: Optional[SortField] = Field(SortField.CREATED_AT, description="Order by column name")
    sort_direction: Optional[SortDirection] = Field(SortDirection.DESC, description="Order by direction")


class UserListFilter(BaseFilterModel):
    deleted_only: bool = Field(False, description="Return only soft-deleted users")


class ConversationFilter(BaseFilterModel):
    conversation_status: Optional[list[ConversationStatus]] = Field(Query(None, description="Conversation statuses"))
    conversation_topics: Optional[list[ConversationTopic]] = Field(
        Query(
            None,
        ),
        description="Conversation topics decided by llm",
    )
    sentiment: Optional[Sentiment] = Field(None, description="Sentiment of the conversation")
    agent_id: Optional[UUID] = Field(None, description="Filter by agent ID")
    customer_satisfaction_min: Optional[int] = Field(None, ge=0, le=10, description="Min customer satisfaction score")
    customer_satisfaction_max: Optional[int] = Field(None, ge=0, le=10, description="Max customer satisfaction score")
    quality_of_service_min: Optional[int] = Field(None, ge=0, le=10, description="Min quality of service score")
    quality_of_service_max: Optional[int] = Field(None, ge=0, le=10, description="Max quality of service score")
    resolution_rate_min: Optional[int] = Field(None, ge=0, le=10, description="Min resolution rate score")
    resolution_rate_max: Optional[int] = Field(None, ge=0, le=10, description="Max resolution rate score")
    efficiency_min: Optional[int] = Field(None, ge=0, le=10, description="Min efficiency score")
    efficiency_max: Optional[int] = Field(None, ge=0, le=10, description="Max efficiency score")
    hostility_positive_max: Optional[int] = Field(
        None,
        ge=0,
        le=30,
        description="Sentiment intervals to decide based on hostility score if a live "
        "conversation should be considered neutral, positive or negative",
    )
    hostility_neutral_max: Optional[int] = Field(
        None,
        ge=0,
        le=49,
        description="Sentiment intervals to decide based on hostility score if a live "
        "conversation should be considered neutral, positive or negative",
    )

    minimum_hostility_score: Optional[int] = None
    include_messages: Optional[bool] = Field(True)
    customer_id: Optional[UUID] = Field(None, description="Customer ID")
    exclude_empty: Optional[bool] = Field(None, description="Exclude conversations with zero word count")
    from_create_datetime_messages: Optional[datetime] = Field(None, description="Start datetime message was created")
    to_create_datetime_messages: Optional[datetime] = Field(None, description="End datetime message was created")
    workflow_id: Optional[UUID] = Field(None, description="Filter conversations by the workflow used by the agent")
    id_suffix: Optional[str] = Field(None, description="Filter conversations by the last N characters of the UUID")
    custom_attributes: Optional[str] = Field(
        None,
        description='JSON-encoded custom attribute filters, e.g. {"region": "Germany"}',
    )

    @property
    def custom_attributes_dict(self) -> dict[str, str] | None:
        if not self.custom_attributes:
            return None
        try:
            parsed = json.loads(self.custom_attributes)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None


class ApiKeysFilter(BaseFilterModel):
    user_id: Optional[UUID] = Field(None, description="Agent who's user owns the api key")


class RecordingFilter(BaseFilterModel):
    operator_id: Optional[UUID] = None


class AgentResponseLogFilter(BaseModel):
    conversation_id: UUID
    node_type: Optional[str] = Field(None, description="Filter by node type found in state.nodeExecutionStatus[*].type")
