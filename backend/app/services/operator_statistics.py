from uuid import UUID
from fastapi import Depends
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.operator_statistics import OperatorStatisticsRepository
from app.schemas.conversation_analysis import ConversationAnalysisRead
from app.schemas.operator_statistics import OperatorStatisticsRead
from app.core.utils.bi_utils import calculate_rating_score

@inject
class OperatorStatisticsService:

    def __init__(self, repository: OperatorStatisticsRepository):  # Auto-inject repository
        self.repository = repository

    async def get_by_operator_id(self, operator_id: UUID):
        model = await self.repository.get_by_operator_id(operator_id)
        if not model:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        return model

    async def create(self, operator_id: UUID):
        model = await self.repository.create(operator_id=operator_id)
        return model

    async def update(self, operator_id: UUID, **kwargs):
        model = await self.repository.update(operator_id=operator_id, **kwargs)
        return model


    async def update_from_analysis(self,
                                   conversation_analysis: ConversationAnalysisRead,
                                   operator_id: UUID,
                                   conversation_duration: int):

        # Update operator_statistics
        existing_stats = await self.get_by_operator_id(operator_id)
        if not existing_stats:
            existing_stats = await self.create(
                operator_id=operator_id)

        new_call_count = existing_stats.call_count + 1
        # Running average calculation (integer division for now, or float if needed)
        updated_avg_positive = (
                (existing_stats.avg_positive_sentiment * existing_stats.call_count + conversation_analysis.positive_sentiment)
                / new_call_count

        )
        updated_avg_negative = (
                (existing_stats.avg_negative_sentiment * existing_stats.call_count + conversation_analysis.negative_sentiment)
                / new_call_count

        )
        updated_avg_neutral = (
                (existing_stats.avg_neutral_sentiment * existing_stats.call_count + conversation_analysis.neutral_sentiment)
                / new_call_count

        )
        updated_avg_response_time = (
                (existing_stats.avg_response_time * existing_stats.call_count + conversation_analysis.response_time)
                / new_call_count

        )
        updated_avg_resolution_rate = (
                (existing_stats.avg_resolution_rate * existing_stats.call_count + conversation_analysis.resolution_rate)
                / new_call_count

        )
        updated_avg_customer_satisfaction = (
                (
                        existing_stats.avg_customer_satisfaction * existing_stats.call_count + conversation_analysis.customer_satisfaction)
                / new_call_count

        )
        updated_avg_quality_of_service = (
                (
                        existing_stats.avg_quality_of_service * existing_stats.call_count + conversation_analysis.quality_of_service)
                / new_call_count

        )
        updated_avg_score = calculate_rating_score(positive_percentage=updated_avg_positive,
                                           negative_percentage=updated_avg_negative, neutral_percentage=updated_avg_neutral,)
        updated_total_duration = existing_stats.total_duration + conversation_duration

        await self.update(
                operator_id=operator_id,
                avg_positive_sentiment=updated_avg_positive,
                avg_negative_sentiment=updated_avg_negative,
                avg_neutral_sentiment=updated_avg_neutral,
                total_duration=updated_total_duration,
                call_count=new_call_count,
                avg_response_time=updated_avg_response_time,
                avg_resolution_rate=updated_avg_resolution_rate,
                avg_quality_of_service=updated_avg_quality_of_service,
                avg_customer_satisfaction=updated_avg_customer_satisfaction,
                score=updated_avg_score,
                )