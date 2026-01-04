import decimal
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, condecimal, field_serializer, field_validator, ConfigDict


class OperatorStatisticsBase(BaseModel):
    """Shared attributes for Operator Statistics"""
    avg_positive_sentiment: int = Field(..., alias="positive", ge=0, le=100, description="Positive sentiment score ("
                                                                                       "0-100)%")
    avg_neutral_sentiment: int = Field(..., alias="neutral", ge=0, le=100, description="Neutral sentiment score (0-100)%")
    avg_negative_sentiment: int = Field(..., ge=0, alias="negative",le=100, description="Negative sentiment score (0-100)%")
    total_duration: int = Field(..., alias="totalCallDuration", description="Total call duration")
    score: condecimal(max_digits=5, decimal_places=2) = decimal.Decimal("0.00")
    call_count: int = Field(..., ge=0, alias="callCount",description="Number of calls made by the agent")
    avg_customer_satisfaction: condecimal(max_digits=5, decimal_places=2) = decimal.Decimal("0.00")
    avg_resolution_rate: condecimal(max_digits=5, decimal_places=2) = decimal.Decimal("0.00")
    avg_response_time: condecimal(max_digits=5, decimal_places=2) = decimal.Decimal("0.00")
    avg_quality_of_service: condecimal(max_digits=5, decimal_places=2) = decimal.Decimal("0.00")


class OperatorStatisticsRead(OperatorStatisticsBase):
    """Used for returning OperatorRead Statistics"""
    id: UUID = Field(default_factory=uuid4)

    @field_serializer("total_duration")
    def convert_seconds_to_hhmmss(self, value: int) -> str:
        """Convert seconds back to HH:MM:SS for frontend"""
        return str(timedelta(seconds=value))

    @field_serializer("avg_customer_satisfaction", "avg_resolution_rate", "avg_response_time", "avg_quality_of_service")
    def multiply_kpi_by_10(self, value: decimal.Decimal, _info) -> str:
        """Multiply KPI scores by 10 and round to 2 decimals for frontend display"""
        return f"{round(float(value) * 10, 2)}%"


    model_config = ConfigDict(
            from_attributes=True,  # Equivalent to `orm_mode = True` in Pydantic v2
            populate_by_name=True  # When we return a database model it is automatically mapped according to alias
            )


class OperatorStatisticsCreate(OperatorStatisticsBase):
    """Used when creating Operator Statistics"""
    id: Optional[UUID] = None

    @field_validator("total_duration", mode="before")
    @classmethod
    def convert_hhmmss_to_seconds(cls, value: str) -> int:
        """Convert HH:MM:SS format to seconds for storage"""
        try:
            h, m, s = map(int, value.split(":"))
            return h * 3600 + m * 60 + s
        except ValueError:
            raise ValueError("total_call_duration must be in HH:MM:SS format")
