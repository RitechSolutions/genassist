from typing import Optional
from uuid import UUID
from datetime import datetime

from app.core.utils.date_time_utils import previous_period
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from app.db.models.recording import RecordingModel
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.agent import AgentModel
from app.schemas.recording import RecordingCreate

# Metric definitions: (raw_key, display_key, scale_factor)
# KPIs are stored as 0-10 in the DB (scale 10 → 0-100%), sentiments as 0-100 (scale 1).
_METRICS = [
    ("customer_satisfaction", "Customer Satisfaction", 10),
    ("resolution_rate",       "Resolution Rate",       10),
    ("positive_sentiment",    "Positive Sentiment",     1),
    ("neutral_sentiment",     "Neutral Sentiment",      1),
    ("negative_sentiment",    "Negative Sentiment",     1),
    ("efficiency",            "Efficiency",             10),
    ("response_time",         "Response Time",          10),
    ("quality_of_service",    "Quality of Service",     10),
]

_METRIC_KEYS = [m[0] for m in _METRICS]
_DISPLAY_KEY_MAP = {m[0]: m[1] for m in _METRICS}
_SCALE_MAP = {m[0]: m[2] for m in _METRICS}

_EMPTY_RAW_METRICS = {k: 0 for k in _METRIC_KEYS} | {"total_analyzed_audios": 0}


def scale_raw_metrics(averages: dict[str, float | None], total: int) -> dict:
    """Scale DB averages to 0-100 display values using each metric's scale factor."""
    return {
        k: round((averages.get(k) or 0) * _SCALE_MAP[k])
        for k in _METRIC_KEYS
    } | {"total_analyzed_audios": total}


def format_raw_metrics(raw: dict) -> dict:
    """Convert raw numeric metrics (0-100) to the formatted display response."""
    result = {_DISPLAY_KEY_MAP[k]: f"{raw[k]}%" for k in _METRIC_KEYS}
    result["total_analyzed_audios"] = raw["total_analyzed_audios"]
    return result


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
            *[func.avg(getattr(ConversationAnalysisModel, k)) for k in _METRIC_KEYS],
        )
        query = self._apply_filters(query, from_date, to_date, agent_id)
        result = await self.db.execute(query)

        row = result.one()
        total_files = row[0]

        if total_files == 0:
            return dict(_EMPTY_RAW_METRICS)

        averages = dict(zip(_METRIC_KEYS, row[1:]))
        return scale_raw_metrics(averages, total_files)


    async def get_metrics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
    ):
        raw = await self._get_raw_metrics(from_date, to_date, agent_id)
        return format_raw_metrics(raw)

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
                "current": format_raw_metrics(current_raw),
                "previous": None,
                "deltas": None,
            }

        prev_from, prev_to = previous_period(from_date, to_date)
        previous_raw = await self._get_raw_metrics(prev_from, prev_to, agent_id)

        # Compute deltas (percentage-point difference) — exclude neutral_sentiment
        delta_keys = [k for k in _METRIC_KEYS if k != "neutral_sentiment"]
        deltas = {
            _DISPLAY_KEY_MAP[k]: current_raw[k] - previous_raw[k]
            for k in delta_keys
        }

        return {
            "current": format_raw_metrics(current_raw),
            "previous": format_raw_metrics(previous_raw),
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
