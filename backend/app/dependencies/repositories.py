from app.db.session import AsyncSessionLocal
from app.repositories.agent import AgentRepository


# TODO remove not needed
# async def get_llm_analyst_service(db=Depends(get_db)) -> LlmAnalystService:
#     llm_provider_repository = LlmProviderRepository(db)
#     analyst_repo = LlmAnalystRepository(db)
#     return LlmAnalystService(repository=analyst_repo, llm_provider_repository=llm_provider_repository)
#
# async def get_llm_provider_service(db=Depends(get_db)) -> LlmProviderService:
#     provider_repo = LlmProviderRepository(db)
#     return LlmProviderService(repository=provider_repo)
#
# async def get_operator_service(db=Depends(get_db)) -> OperatorService:
#     operator_repo = OperatorRepository(db=db)
#     conversation_repo = ConversationRepository(db=db)
#     return OperatorService(operator_repo=operator_repo, conversation_repo=conversation_repo)
#
# def get_operator_statistics_service(db=Depends(get_db)) -> OperatorStatisticsService:
#     operator_stats_repo = OperatorStatisticsRepository(db=db)
#     return OperatorStatisticsService(repository=operator_stats_repo)
#
#
# def get_conversation_analysis_service(db: AsyncSession = Depends(get_db)) -> ConversationAnalysisService:
#     repository = ConversationAnalysisRepository(db)
#     return ConversationAnalysisService(repository)
#
#
# async def get_conversation_service(
#     db: AsyncSession = Depends(get_db),
#     analyst_svc: LlmAnalystService = Depends(get_llm_analyst_service),
#     operator_svc: OperatorService = Depends(get_operator_service),
#     conversation_analysis_svc: ConversationAnalysisService = Depends(get_conversation_analysis_service),
# ) -> ConversationService:
#     """FastAPI dependency that gives a fully‑wired service per HTTP request."""
#     conversation_repo: ConversationRepository = ConversationRepository(db)
#
#     return ConversationService(
#             conversation_repo=conversation_repo,
#             gpt_kpi_analyzer_service=get_gpt_kpi_analyzer(),
#             conversation_analysis_service=conversation_analysis_svc,
#             operator_statistics_service=operator_svc,
#             llm_analyst_service=analyst_svc,
#             )
#
#
#
# async def get_recording_service(
#     db: AsyncSession = Depends(get_db),
#     analyst_svc: LlmAnalystService = Depends(get_llm_analyst_service),
#     operator_svc: OperatorService = Depends(get_operator_service),
#     conversation_svc: ConversationService = Depends(get_conversation_service),
#     analysis_svc: ConversationAnalysisService = Depends(get_conversation_analysis_service),
#     operator_statistics_svc: OperatorStatisticsService = Depends(get_operator_statistics_service),
# ) -> AudioService:
#     rec_repo = RecordingsRepository(db)
#     return AudioService(
#             recording_repo=rec_repo,
#             conversation_service=conversation_svc,
#             conversation_analysis_service=analysis_svc,
#             operator_statistics_service=operator_statistics_svc,
#             operator_service=operator_svc,
#             speaker_separator_service=get_speaker_separator(),
#             gpt_kpi_analyzer_service=get_gpt_kpi_analyzer(),
#             gpt_question_answerer_service=get_question_answerer_service(),
#             llm_analyst_service=analyst_svc,
#             )

async def create_agent_repository() -> AgentRepository:
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        return agent_repo
