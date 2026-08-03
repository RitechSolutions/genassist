from typing import Optional
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
                                   conversation_duration: int,
                                   previous_analysis: Optional[ConversationAnalysisRead] = None):
        """Fold a conversation's analysis into the operator's running averages.

        Fresh analysis (``previous_analysis is None``): count this as a new call —
        increment ``call_count``, add ``conversation_duration``, and fold the metrics
        into the averages.

        Replacement (``previous_analysis`` supplied): the conversation was already
        counted, so keep ``call_count`` and ``total_duration`` fixed and only swap the
        old metric contribution for the new one in each average.
        """

        # Update operator_statistics
        existing_stats = await self.get_by_operator_id(operator_id)
        if not existing_stats:
            existing_stats = await self.create(
                operator_id=operator_id)

        # A replacement can only adjust averages that already include the prior call.
        is_replacement = previous_analysis is not None and existing_stats.call_count > 0

        if is_replacement:
            count = existing_stats.call_count
            new_call_count = count
            updated_total_duration = existing_stats.total_duration

            def swap(current_avg, attr):
                # Remove the previous analysis's contribution, add the new one.
                new_sum = (current_avg * count
                           - getattr(previous_analysis, attr)
                           + getattr(conversation_analysis, attr))
                return new_sum / count
        else:
            count = existing_stats.call_count
            new_call_count = count + 1
            updated_total_duration = existing_stats.total_duration + conversation_duration

            def swap(current_avg, attr):
                # Fold the new analysis in as an additional call.
                new_sum = current_avg * count + getattr(conversation_analysis, attr)
                return new_sum / new_call_count

        updated_avg_positive = swap(existing_stats.avg_positive_sentiment, "positive_sentiment")
        updated_avg_negative = swap(existing_stats.avg_negative_sentiment, "negative_sentiment")
        updated_avg_neutral = swap(existing_stats.avg_neutral_sentiment, "neutral_sentiment")
        updated_avg_response_time = swap(existing_stats.avg_response_time, "response_time")
        updated_avg_resolution_rate = swap(existing_stats.avg_resolution_rate, "resolution_rate")
        updated_avg_customer_satisfaction = swap(existing_stats.avg_customer_satisfaction, "customer_satisfaction")
        updated_avg_quality_of_service = swap(existing_stats.avg_quality_of_service, "quality_of_service")

        updated_avg_score = calculate_rating_score(positive_percentage=updated_avg_positive,
                                           negative_percentage=updated_avg_negative, neutral_percentage=updated_avg_neutral,)

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