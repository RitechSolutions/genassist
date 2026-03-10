from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
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

    async def _get_raw_metrics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
    ) -> dict:
        """Return numeric metric averages (already scaled to 0-100 for display)."""
        query = select(
            func.count(ConversationAnalysisModel.id),
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
            return {
                "customer_satisfaction": 0, "resolution_rate": 0,
                "positive_sentiment": 0, "neutral_sentiment": 0, "negative_sentiment": 0,
                "efficiency": 0, "response_time": 0, "quality_of_service": 0,
                "total_analyzed_audios": 0,
            }

        return {
            "customer_satisfaction": round((avg_customer_satisfaction or 0) * 10),
            "resolution_rate": round((avg_resolution_rate or 0) * 10),
            "positive_sentiment": round(avg_positive or 0),
            "neutral_sentiment": round(avg_neutral or 0),
            "negative_sentiment": round(avg_negative or 0),
            "efficiency": round((avg_efficiency or 0) * 10),
            "response_time": round((avg_response_time or 0) * 10),
            "quality_of_service": round((avg_quality_of_service or 0) * 10),
            "total_analyzed_audios": total_files,
        }

    @staticmethod
    def _format_raw_metrics(raw: dict) -> dict:
        """Convert raw numeric metrics to the formatted string response."""
        return {
            "Customer Satisfaction": f"{raw['customer_satisfaction']}%",
            "Resolution Rate": f"{raw['resolution_rate']}%",
            "Positive Sentiment": f"{raw['positive_sentiment']}%",
            "Neutral Sentiment": f"{raw['neutral_sentiment']}%",
            "Negative Sentiment": f"{raw['negative_sentiment']}%",
            "Efficiency": f"{raw['efficiency']}%",
            "Response Time": f"{raw['response_time']}%",
            "Quality of Service": f"{raw['quality_of_service']}%",
            "total_analyzed_audios": raw["total_analyzed_audios"],
        }

    async def get_metrics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
    ):
        raw = await self._get_raw_metrics(from_date, to_date, agent_id)
        return self._format_raw_metrics(raw)

    async def get_metrics_with_comparison(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
    ) -> dict:
        """Return current metrics, previous-period metrics, and deltas."""
        current_raw = await self._get_raw_metrics(from_date, to_date, agent_id)

        if from_date is None or to_date is None:
            return {
                "current": self._format_raw_metrics(current_raw),
                "previous": None,
                "deltas": None,
            }

        duration = to_date - from_date
        prev_to = from_date - timedelta(days=1)
        prev_from = prev_to - duration
        previous_raw = await self._get_raw_metrics(prev_from, prev_to, agent_id)

        # Compute deltas (percentage-point difference)
        delta_keys = [
            "customer_satisfaction", "resolution_rate", "positive_sentiment",
            "negative_sentiment", "efficiency", "response_time", "quality_of_service",
        ]
        # Map raw keys to display keys
        display_key_map = {
            "customer_satisfaction": "Customer Satisfaction",
            "resolution_rate": "Resolution Rate",
            "positive_sentiment": "Positive Sentiment",
            "negative_sentiment": "Negative Sentiment",
            "efficiency": "Efficiency",
            "response_time": "Response Time",
            "quality_of_service": "Quality of Service",
        }
        deltas = {
            display_key_map[k]: current_raw[k] - previous_raw[k]
            for k in delta_keys
        }

        return {
            "current": self._format_raw_metrics(current_raw),
            "previous": self._format_raw_metrics(previous_raw),
            "deltas": deltas,
        }


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
                func.avg(ConversationAnalysisModel.efficiency).label("efficiency"),
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
                "efficiency": round(float(row.efficiency or 0) * 10, 2),
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
