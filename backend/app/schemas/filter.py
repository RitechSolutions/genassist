from fastapi import Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from uuid import UUID

from app.core.utils.enums.conversation_topic_enum import ConversationTopic
from app.core.utils.enums.sentiment_enum import Sentiment
from app.core.utils.enums.sort_direction_enum import SortDirection
from app.core.utils.enums.sort_field_enum import SortField
from app.core.utils.enums.conversation_status_enum import ConversationStatus


class BaseFilterModel(BaseModel):
    skip: int = Field(
        0, ge=0, description="The number of rows to skip before returning results"
    )
    limit: int = Field(
        20, ge=1, le=100, description="The number of rows to return per page"
    )
    from_date: Optional[date] = Field(None, description="Start date (YYYY-MM-DD)")
    to_date: Optional[date] = Field(None, description="End date (YYYY-MM-DD)")
    operator_id: Optional[UUID] = Field(
        None, description="Operator who made the conversation"
    )
    order_by: Optional[SortField] = Field(
        SortField.CREATED_AT, description="Order by column name"
    )
    sort_direction: Optional[SortDirection] = Field(
        SortDirection.DESC, description="Order by direction"
    )


class ConversationFilter(BaseFilterModel):
    conversation_status: Optional[list[ConversationStatus]] = Field(
        Query(None, description="Conversation statuses")
    )
    conversation_topics: Optional[list[ConversationTopic]] = Field(
        Query(
            None,
        ),
        description="Conversation topics decided by llm",
    )
    sentiment: Optional[Sentiment] = Field(
        None, description="Sentiment of the conversation"
    )
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
    from_create_datetime_messages: Optional[datetime] = Field(
        None, description="Start datetime message was created"
    )
    to_create_datetime_messages: Optional[datetime] = Field(
        None, description="End datetime message was created"
    )


class ApiKeysFilter(BaseFilterModel):
    user_id: Optional[UUID] = Field(
        None, description="Agent who's user owns the api key"
    )


class RecordingFilter(BaseFilterModel):
    operator_id: Optional[UUID] = None
