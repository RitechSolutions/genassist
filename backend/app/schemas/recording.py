from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class RecordingBase(BaseModel):
    operator_id: UUID
    data_source_id: UUID| None = None
    transcription_model_name: Optional[str] = None
    recording_date: datetime = Field(alias="recorded_at")
    customer_id: Optional[UUID] | None = None
    llm_analyst_kpi_analyzer_id: Optional[UUID] = None
    llm_analyst_speaker_separator_id: Optional[UUID] = None
    original_filename: Optional[str] = None

class RecordingCreate(RecordingBase):
    pass


class RecordingRead(RecordingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    recording_date: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes = True
    )
