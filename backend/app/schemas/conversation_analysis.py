from dataclasses import dataclass
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict


class ConversationAnalysisBase(BaseModel):
    conversation_id: UUID = Field(default_factory=uuid4)
    topic: str
    summary: str
    negative_sentiment: int
    positive_sentiment: int
    neutral_sentiment: int
    tone: str
    customer_satisfaction: int
    operator_knowledge: int
    resolution_rate: int
    llm_analyst_id: UUID
    efficiency: int
    response_time: int
    quality_of_service: int


class ConversationAnalysisCreate(ConversationAnalysisBase):
    pass


class ConversationAnalysisRead(ConversationAnalysisBase):
    id: Optional[UUID] = None

    model_config = ConfigDict(
        from_attributes = True
    )


# class AnalysisResult(BaseModel):
#     summary: str
#     title: str
#     customer_speaker: str
#     kpi_metrics: Dict[str, int]  # Example: {"Response Time": 8, "Customer Satisfaction": 9}
    
@dataclass
class AnalysisResult:
    summary: str
    title: str
    customer_speaker: str
    kpi_metrics: Dict[str, int]  # Example: {"Response Time": 8, "Customer Satisfaction": 9}

