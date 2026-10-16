from uuid import UUID
from fastapi import Depends
from fastapi_injector import Injected
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.topic_settings import DEFAULT_TOPIC_SPECS, TopicSpec, configured_topic_specs, merge_topic_specs
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.llm import LlmAnalyst, LlmAnalystCreate, LlmAnalystUpdate
from app.schemas.topic_options import TopicOption, TopicOptionsRead

@inject
class LlmAnalystService:
    def __init__(self, repository: LlmAnalystRepository, llm_provider_repository: LlmProviderRepository  = Injected(LlmProviderRepository),
                 conversation_analysis_repository: ConversationAnalysisRepository = Injected(ConversationAnalysisRepository)):
        self.repository = repository
        self.llm_provider_repository = llm_provider_repository
        self.conversation_analysis_repository = conversation_analysis_repository

    async def create(self, data: LlmAnalystCreate):
        # Check if the LLM provider exists
        obj = await self.llm_provider_repository.get_by_id(data.llm_provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.LLM_PROVIDER_NOT_FOUND, status_code=404)
        
        llm_analyst =  await self.repository.create(data)
        model = await self.repository.get_by_id(llm_analyst.id, include_inactive=True)
        return model

    async def get_by_id(self, llm_analyst_id: UUID, include_inactive: bool = False,
                        throw_not_found: bool = True) -> LlmAnalyst:
        obj = await self._read_by_id(llm_analyst_id, include_inactive=include_inactive,
                                     throw_not_found=throw_not_found)
        return obj

    async def _read_by_id(self, llm_analyst_id: UUID, include_inactive: bool = False,
                          throw_not_found: bool = True) -> LlmAnalyst:
        obj = await self.repository.get_by_id(llm_analyst_id, include_inactive=include_inactive)
        if not obj and throw_not_found:
            if not include_inactive and await self.repository.get_by_id(llm_analyst_id,
                                                                        include_inactive=True):
                raise AppException(error_key=ErrorKey.LLM_ANALYST_INACTIVE, status_code=409)
            raise AppException(error_key=ErrorKey.LLM_ANALYST_NOT_FOUND, status_code=404)
        return obj

    async def get_all(self):
        models = await self.repository.get_all()
        return models

    async def get_topic_options(self) -> TopicOptionsRead:
        """Topics of the active analysts, then any others still stored on finalized conversations"""
        analysts = await self.get_all()
        configured = merge_topic_specs(configured_topic_specs(a.settings) for a in analysts if a.is_active == 1)
        stored = [
            TopicSpec(topic, (subtopic,) if subtopic else ())
            for topic, subtopic in await self.conversation_analysis_repository.list_distinct_topics()
        ]
        specs = merge_topic_specs([configured or list(DEFAULT_TOPIC_SPECS), stored])
        return TopicOptionsRead(topics=[TopicOption(name=s.name, subtopics=list(s.subtopics)) for s in specs])

    async def update(self, llm_analyst_id: UUID, data: LlmAnalystUpdate):
        obj = await self._read_by_id(llm_analyst_id, include_inactive=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        model = await self.repository.update(obj)
        return model

    async def delete(self, llm_analyst_id: UUID):
        obj = await self._read_by_id(llm_analyst_id, include_inactive=True)
        await self.repository.delete(obj)
        return {"message": f"LlmAnalyst with ID {llm_analyst_id} has been deleted."}
