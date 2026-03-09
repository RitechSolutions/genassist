from typing import Optional
from uuid import UUID
from datetime import datetime
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from app.db.models.recording import RecordingModel
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.agent import AgentModel
from app.schemas.recording import RecordingCreate

@inject
class RecordingsRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _apply_filters(
        query,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
        conversation_already_joined: bool = False,
    ):
        """Apply common ConversationModel/AgentModel joins and date filters to a query."""
        if not conversation_already_joined:
            query = query.join(
                ConversationModel,
                ConversationAnalysisModel.conversation_id == ConversationModel.id,
            )
        if agent_id is not None:
            query = query.join(
                AgentModel,
                AgentModel.operator_id == ConversationModel.operator_id,
            ).where(AgentModel.id == agent_id)
        if from_date is not None:
            query = query.where(ConversationModel.conversation_date >= from_date)
        if to_date is not None:
            query = query.where(ConversationModel.conversation_date <= to_date)
        return query

    @staticmethod
    def get_default_metrics() -> dict:
        """Return default metrics values when no analyzed audio files exist."""
        return {
            "Customer Satisfaction": "0%",
            "Resolution Rate": "0%",
            "Positive Sentiment": "0%",
            "Neutral Sentiment": "0%",
            "Negative Sentiment": "0%",
            "Efficiency": "0%",
            "Response Time": "0%",
            "Quality of Service": "0%",
            "total_analyzed_audios": 0,
        }

    def _format_metrics(
        self,
        total_files: int,
        avg_customer_satisfaction: Optional[float],
        avg_resolution_rate: Optional[float],
        avg_positive: Optional[float],
        avg_neutral: Optional[float],
        avg_negative: Optional[float],
        avg_efficiency: Optional[float],
        avg_response_time: Optional[float],
        avg_quality_of_service: Optional[float],
    ) -> dict:
        """Format metrics values into the response dictionary."""
        return {
            "Customer Satisfaction": f"{round((avg_customer_satisfaction or 0) * 10)}%",
            "Resolution Rate": f"{round((avg_resolution_rate or 0) * 10)}%",
            "Positive Sentiment": f"{round(avg_positive or 0)}%",
            "Neutral Sentiment": f"{round(avg_neutral or 0)}%",
            "Negative Sentiment": f"{round(avg_negative or 0)}%",
            "Efficiency": f"{round((avg_efficiency or 0) * 10)}%",
            "Response Time": f"{round((avg_response_time or 0) * 10)}%",
            "Quality of Service": f"{round((avg_quality_of_service or 0) * 10)}%",
            "total_analyzed_audios": total_files,
        }

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

    async def get_metrics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
    ):
        # TODO fetch from operators instead
        # Aggregate sums and counts directly from the DB
        query = select(
            func.count(ConversationAnalysisModel.id),  # total_files
            func.avg(ConversationAnalysisModel.customer_satisfaction),
            func.avg(ConversationAnalysisModel.resolution_rate),
            func.avg(ConversationAnalysisModel.positive_sentiment),
            func.avg(ConversationAnalysisModel.neutral_sentiment),
            func.avg(ConversationAnalysisModel.negative_sentiment),
            func.avg(ConversationAnalysisModel.efficiency),
            func.avg(ConversationAnalysisModel.response_time),
            func.avg(ConversationAnalysisModel.quality_of_service),
        )
        query = self._apply_filters(query, from_date, to_date, agent_id)
        result = await self.db.execute(query)

        (
            total_files,
            avg_customer_satisfaction,
            avg_resolution_rate,
            avg_positive,
            avg_neutral,
            avg_negative,
            avg_efficiency,
            avg_response_time,
            avg_quality_of_service,
        ) = result.one()

        if total_files == 0:
            return self.get_default_metrics()

        return self._format_metrics(
            total_files,
            avg_customer_satisfaction,
            avg_resolution_rate,
            avg_positive,
            avg_neutral,
            avg_negative,
            avg_efficiency,
            avg_response_time,
            avg_quality_of_service,
        )


    async def get_metrics_per_day(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Return daily averages for key KPI metrics (0-10 scale, multiplied by 10 for %)."""
        day_col = cast(ConversationModel.conversation_date, Date).label("day")
        query = (
            select(
                day_col,
                func.avg(ConversationAnalysisModel.customer_satisfaction).label("satisfaction"),
                func.avg(ConversationAnalysisModel.quality_of_service).label("quality_of_service"),
                func.avg(ConversationAnalysisModel.resolution_rate).label("resolution_rate"),
            )
            .join(
                ConversationModel,
                ConversationAnalysisModel.conversation_id == ConversationModel.id,
            )
            .group_by(day_col)
            .order_by(day_col)
        )
        query = self._apply_filters(
            query, from_date, to_date, agent_id, conversation_already_joined=True
        )

        rows = (await self.db.execute(query)).all()
        return [
            {
                "date": str(row.day),
                "satisfaction": round(float(row.satisfaction or 0) * 10, 2),
                "quality_of_service": round(float(row.quality_of_service or 0) * 10, 2),
                "resolution_rate": round(float(row.resolution_rate or 0) * 10, 2),
            }
            for row in rows
        ]

    async def find_by_id(self, rec_id: UUID):
        return await self.db.get(RecordingModel, rec_id)

    async def recording_exists(self , original_filename: str ,data_source_id: UUID):
        stmt = select(RecordingModel).where(
            RecordingModel.original_filename == original_filename,
            RecordingModel.data_source_id == data_source_id
        )
        records_found = await self.db.execute(stmt)
        first_record_or_none = records_found.scalars().first()
        if first_record_or_none:
            return True
        else:
            return False
