from typing import Optional
from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.recording import RecordingModel
from app.db.models.conversation import ConversationAnalysisModel
from app.schemas.recording import RecordingCreate

@inject
class RecordingsRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db


    async def save_recording(self, rec_path, recording_create: RecordingCreate):
        new_recording = RecordingModel(
                file_path=rec_path,
                operator_id=recording_create.operator_id,
                recording_date=recording_create.recording_date,
                data_source_id=recording_create.data_source_id,
                original_filename=recording_create.original_filename
                )

        self.db.add(new_recording)
        await self.db.commit()
        await self.db.refresh(new_recording)  #  Reload object with DB-assigned values

        return new_recording

    async def get_metrics(self):
        # TODO fetch from operators instead
        # Aggregate sums and counts directly from the DB
        result = await self.db.execute(
            select(
                func.count(ConversationAnalysisModel.id),  # total_files
                func.avg(ConversationAnalysisModel.customer_satisfaction),
                func.avg(ConversationAnalysisModel.operator_knowledge),
                func.avg(ConversationAnalysisModel.resolution_rate),
                func.avg(ConversationAnalysisModel.positive_sentiment),
                func.avg(ConversationAnalysisModel.neutral_sentiment),
                func.avg(ConversationAnalysisModel.negative_sentiment),
                func.avg(ConversationAnalysisModel.efficiency),
                func.avg(ConversationAnalysisModel.response_time),
                func.avg(ConversationAnalysisModel.quality_of_service),
            )
        )

        (
            total_files,
            avg_customer_satisfaction,
            avg_operator_knowledge,
            avg_resolution_rate,
            avg_positive,
            avg_neutral,
            avg_negative,
            avg_efficiency,
            avg_response_time,
            avg_quality_of_service,
        ) = result.one()

        if total_files == 0:
            raise AppException(ErrorKey.NO_ANALYZED_AUDIO, status_code=404)

        return {
            "Customer Satisfaction": f"{round((avg_customer_satisfaction or 0) * 10, 2)}%",
            "Resolution Rate": f"{round((avg_resolution_rate or 0) * 10, 2)}%",
            "Positive Sentiment": f"{round(avg_positive or 0, 2)}%",
            "Neutral Sentiment": f"{round(avg_neutral or 0, 2)}%",
            "Negative Sentiment": f"{round(avg_negative or 0, 2)}%",
            "Efficiency": f"{round((avg_efficiency or 0) * 10, 2)}%",
            "Response Time": f"{round((avg_response_time or 0) * 10, 2)}%",
            "Quality of Service": f"{round((avg_quality_of_service or 0) * 10, 2)}%",
            "total_analyzed_audios": total_files,
        }


    async def find_by_id(self, rec_id: UUID):
        return await self.db.get(RecordingModel, rec_id)

    async def recording_exists(self , original_filename: str ,data_source_id: UUID):
        filter = select(RecordingModel).where(
            RecordingModel.original_filename == original_filename,
            RecordingModel.data_source_id == data_source_id
        )
        records_found = await self.db.execute(filter)
        first_record_or_none = records_found.scalars().first()
        if first_record_or_none:
            return True
        else:
            return False
