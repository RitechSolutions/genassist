from datetime import datetime, timezone
import io
import os
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from uuid import UUID
import logging
from app.auth.utils import hash_api_key
from app.core.utils.date_time_utils import shift_datetime
from app.core.utils.encryption_utils import encrypt_key
from app.db.models import AgentModel
from app.db.models.api_key import ApiKeyModel
from app.db.models.api_key_role import ApiKeyRoleModel
from app.db.models.customer import CustomerModel
from app.db.models.datasource import DataSourceModel
from app.db.models.llm import LlmAnalystModel, LlmProvidersModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.permission import PermissionModel
from app.db.models.role import RoleModel
from app.db.models.role_permission import RolePermissionModel
from app.db.models.user import UserModel
from app.db.models.user_role import UserRoleModel
from app.db.models.user_type import UserTypeModel
from app.db.seed.seed_data_config import seed_test_data
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.repositories.agent import AgentRepository
from app.repositories.user_types import UserTypesRepository
from app.repositories.users import UserRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.agent import AgentCreate
from app.schemas.recording import RecordingCreate
from app.core.config.settings import settings
from app.schemas.workflow import WorkflowCreate
from app.services.audio import AudioService
from app.repositories.recordings import RecordingsRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.repositories.operator_statistics import OperatorStatisticsRepository
from app.repositories.operators import OperatorRepository
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.services.conversations import ConversationService
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.operator_statistics import OperatorStatisticsService
from app.services.operators import OperatorService
from app.services.llm_analysts import LlmAnalystService
from app.dependencies.agents import get_speaker_separator, get_gpt_kpi_analyzer, \
    get_question_answerer_service
from app.repositories.tool import ToolRepository
from app.services.agent_tool import ToolService
from app.schemas.agent_tool import ToolConfigBase
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.agent_knowledge import KnowledgeBaseService
from app.schemas.agent_knowledge import KBCreate
from app.services.agent_config import AgentConfigService
from app.repositories.file_repository import FileRepository
from app.services.workflow import WorkflowService

logger = logging.getLogger(__name__)

def create_crud_permissions(resource: str, description_template: str = "Allows {action} {resource} data"):
    """Helper function to generate CRUD permissions for a resource."""
    actions = ["create", "read", "update", "delete"]
    return [
        PermissionModel(
            name=f"{action}:{resource}",
            is_active=True,
            description=description_template.format(action=action, resource=resource.replace('_', ' '))
        )
        for action in actions
    ]


async def seed_data(session: AsyncSession):
    """Seeds initial data into the database."""
    from app import settings

    # Create roles
    admin_role = RoleModel(name='admin', role_type="external", is_active=1)
    supervisor_role = RoleModel(name='supervisor', role_type="external", is_active=1)
    operator_role = RoleModel(name='operator', role_type="internal", is_active=1)
    api_role = RoleModel(name='api', role_type="external", is_active=1)
    agent_role = RoleModel(name='ai agent', role_type="internal", is_active=1)

    # Create CRUD permissions
    user_permissions = create_crud_permissions("user")
    user_type_permissions = create_crud_permissions("user_type")
    role_permissions = create_crud_permissions("role")
    role_prm_permissions = create_crud_permissions("role_permission")
    prm_permissions = create_crud_permissions("permission")
    apikey_permissions = create_crud_permissions("api_key")
    llm_analyst_permissions = create_crud_permissions("llm_analyst")
    llm_provider_permissions = create_crud_permissions("llm_provider")
    operator_permissions = create_crud_permissions("operator")
    data_sources_permissions = create_crud_permissions("data_source")
    metrics_permissions = create_crud_permissions("metrics")
    recording_permissions = create_crud_permissions("recording")
    conversation_permissions = create_crud_permissions("conversation")

    audit_log_permissions = create_crud_permissions("audit_log")
    conversation_in_progress_permissions = create_crud_permissions("in_progress_conversation")
    app_settings_permissions = create_crud_permissions("app_settings")
    feature_flag_permissions = create_crud_permissions("feature_flag")

    takeover_supervisor_permission = PermissionModel(name='takeover_in_progress_conversation',
                                                     description='Allow takeover of in progress conversation.',
                                                     is_active=True)

    # Create non-CRUD permissions
    non_standard_crud_permissions = [
        takeover_supervisor_permission,
        PermissionModel(name='create:analyze_recording', description='Allow analysis and transcription of audio record.', is_active=True),
        PermissionModel(name='create:ask_question', description='Allow asking questions to LLM.', is_active=True),
        PermissionModel(name='create:upload_transcript', description='Allow transcript upload.', is_active=True),
        PermissionModel(name='read:files', description='Allow reading files.', is_active=True),
        PermissionModel(name='*', description='Allow everything', is_active=True),
        ]

    # Assign all permissions to admin
    for permission in (
            user_permissions + user_type_permissions + role_prm_permissions + prm_permissions + apikey_permissions + recording_permissions +
            conversation_permissions + llm_analyst_permissions + llm_provider_permissions + operator_permissions +
            data_sources_permissions + role_permissions + audit_log_permissions +
            conversation_in_progress_permissions + metrics_permissions +
            non_standard_crud_permissions + app_settings_permissions + feature_flag_permissions
    ):
        admin_role.role_permissions.append(RolePermissionModel(permission=permission))

    # Assign supervisor permissions
    for permission in operator_permissions:
        if permission.name in ("read:operator", "update:operator"):
            supervisor_role.role_permissions.append(RolePermissionModel(permission=permission))

    supervisor_role.role_permissions.append(RolePermissionModel(permission=takeover_supervisor_permission))

    # Assign operator permissions
    for permission in operator_permissions:
        if permission.name == "read:operator":
            operator_role.role_permissions.append(RolePermissionModel(permission=permission))

    for permission in conversation_permissions:
        if permission.name == "read:conversation":
            operator_role.role_permissions.append(RolePermissionModel(permission=permission))

    # Assign api role permissions
    for permission in operator_permissions:
        if permission.name == "read:operator":
            api_role.role_permissions.append(RolePermissionModel(permission=permission))

    for permission in conversation_in_progress_permissions:
        if permission.name in ["create:in_progress_conversation", "update:in_progress_conversation", "read:in_progress_conversation"]:
            agent_role.role_permissions.append(RolePermissionModel(permission=permission))

    # Add all permissions and roles
    session.add_all(
        user_permissions + llm_analyst_permissions + llm_provider_permissions +
        operator_permissions + data_sources_permissions + non_standard_crud_permissions +
        app_settings_permissions + feature_flag_permissions +
        [admin_role, supervisor_role, operator_role, api_role, agent_role]
    )

    # Create user types
    console_user_type = UserTypeModel(name='console')
    interactive_user_type = UserTypeModel(name='interactive')
    session.add_all([console_user_type, interactive_user_type])
    await session.commit()

    # Create users
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin = UserModel(username='admin', email='admin@genassist.ritech.io', is_active=1,
                      hashed_password=pwd_context.hash('genadmin'), user_type_id=interactive_user_type.id,
                      id=seed_test_data.admin_user_id,
                      force_upd_pass_date=shift_datetime(unit="months", amount=3)
                      )
    supervisor = UserModel(username='supervisor1', email='supervisor1@genassist.ritech.io', is_active=1,
                           hashed_password=pwd_context.hash('gensupervisor1'), user_type_id=interactive_user_type.id,
                           force_upd_pass_date=shift_datetime(unit="months", amount=3)
                           )
    operator = UserModel(id=UUID(seed_test_data.operator_user_id), username='operator1',
                         email='operator1@genassist.ritech.io',
                         is_active=1,
                         hashed_password=pwd_context.hash('genoperator1'), user_type_id=interactive_user_type.id,
                         force_upd_pass_date=shift_datetime(unit="months", amount=3)
                         )
    apiuser = UserModel(username='apiuser1', email='apiuser1@genassist.ritech.io', is_active=1,
                        hashed_password=pwd_context.hash('genapiuser1'), user_type_id=console_user_type.id,
                        force_upd_pass_date=shift_datetime(unit="months", amount=3)
                        )

    # Assign roles to users
    admin.user_roles.append(UserRoleModel(role=admin_role))
    supervisor.user_roles.append(UserRoleModel(role=supervisor_role))
    operator.user_roles.append(UserRoleModel(role=operator_role))
    apiuser.user_roles.append(UserRoleModel(role=api_role))

    session.add_all([admin, supervisor, operator, apiuser])
    await session.commit()

    # Seed default DataSource
    data_source = DataSourceModel(id=UUID(seed_test_data.data_source_id),name="default", source_type="S3",
                                  connection_data={"bucket_name": "genassist-default-bucket"}, is_active=1)
    session.add(data_source)
    await session.commit()

    # Seed default Customer
    customer = CustomerModel(source_ref="default", full_name="default", external_id="default")
    session.add(customer)
    await session.commit()

    # Seed LLM provider
    llm_provider = LlmProvidersModel(
            id=UUID(seed_test_data.llm_provider_id),
            name='openai dev 1.0',
            llm_model_provider="openai",
            is_active=1,
            llm_model="gpt-4o",
            connection_data={
                "api_key": encrypt_key(settings.OPENAI_API_KEY),
                }
            )
    local_llm_provider = LlmProvidersModel(
            id=UUID(seed_test_data.local_llm_provider_id),
            name='mistral 7b local',
            llm_model_provider="ollama",
            is_active=1,
            llm_model="mistral:7b",
            connection_data={
                "url": "http://192.168.10.98:11434",
                }
            )
    session.add_all([llm_provider, local_llm_provider])
    await session.commit()

    # Seed LLM analyst speaker separator
    gpt_speaker_separator_llm_analyst = LlmAnalystModel(
        id=UUID(seed_test_data.llm_analyst_speaker_separator_id),
        name='gpt_speaker_separator_service prompt',
        llm_provider_id=llm_provider.id,
        prompt=seed_test_data.speaker_separation_llm_analyst_prompt,
        is_active=1
    )
    # Seed LLM analyst kpi analyzer
    gpt_kpi_analyzer_llm_analyst = LlmAnalystModel(
        id=UUID(seed_test_data.llm_analyst_kpi_analyzer_id),
        name='gpt_kpi_analyzer_service system prompt',
        llm_provider_id=llm_provider.id,
        prompt=seed_test_data.kpi_analyzer_system_prompt,
        is_active=1
    )
    # Seed LLM analyst hostility score
    in_progress_hostility_llm_analyst = LlmAnalystModel(
        id=UUID(seed_test_data.llm_analyst_in_progress_hostility_id),
        name='gpt_kpi_analyzer_service in progress hostility system prompt',
        llm_provider_id=llm_provider.id,
        prompt=seed_test_data.in_progress_hostility_system_prompt,
        is_active=1
    )
    session.add_all([gpt_speaker_separator_llm_analyst, gpt_kpi_analyzer_llm_analyst, in_progress_hostility_llm_analyst])

    await session.commit()

    # Seed operator statistics
    op_stats = OperatorStatisticsModel(
        avg_positive_sentiment=0, call_count=0,
        avg_negative_sentiment=0, avg_neutral_sentiment=0
    )
    session.add(op_stats)
    await session.commit()

    # Seed operator
    operator = OperatorModel(
        id=UUID(seed_test_data.operator_id),
        first_name='Operator',
        last_name='01',
        is_active=1,
        statistics_id=op_stats.id,
        user_id=seed_test_data.operator_user_id
        )
    session.add(operator)
    await session.commit()


    # Seed API key
    api_key = ApiKeyModel(key_val=encrypt_key('test123'), name='test key',
                          hashed_value=hash_api_key('test123'),
                          is_active=1, user_id=admin.id)
    api_key.api_key_roles.append(ApiKeyRoleModel(role=admin_role))
    session.add(api_key)
    await session.commit()

    # Seed tools
    currency_tool = await seed_tools(session, admin.id)

    # Seed knowledge base
    product_docs = await seed_knowledge_base(session, admin.id)

    # Seed agents
    await seed_agents(session, agent_role)

    # Seed conversation
    await create_conversation(session, operator, data_source, customer)

    logger.debug("Database seeding complete.")

async def seed_tools(session: AsyncSession, created_by: UUID):
    """Seed initial tools into the database."""
    tool_repo = ToolRepository(session)
    tool_service = ToolService(repository=tool_repo)

    # Example API tool for currency conversion
    currency_tool = ToolConfigBase(
        name="convert_currency",
        description="Convert amount from one currency to another",
        type="api",
        api_config={
            "endpoint": "https://api.exchangerate-api.com/v4/latest",
            "method": "GET",
            "headers": {
                "Content-Type": "application/json"
            },
            "query_params": {
                "base": "${from_currency}"
            }
        },
        parameters_schema={
            "from_currency": {
                "type": "string",
                "description": "Currency code to convert from (e.g., USD)",
                "required": True
            },
            "to_currency": {
                "type": "string",
                "description": "Currency code to convert to (e.g., EUR)",
                "required": True
            },
            "amount": {
                "type": "number",
                "description": "Amount to convert",
                "required": True
            }
        }
    )

    # Create tools
    res = await tool_service.create(currency_tool)
    await session.commit()

    logger.debug("Tools seeding complete.")
    return res

async def create_conversation(session: AsyncSession, operator: OperatorModel, data_source: DataSourceModel, customer: CustomerModel):
    metadata = RecordingCreate(
            operator_id=operator.id,
            transcription_model_name=settings.DEFAULT_WHISPER_MODEL,
            llm_analyst_speaker_separator_id=None,
            llm_analyst_kpi_analyzer_id=None,
            recorded_at=datetime.now(),
            data_source_id=data_source.id,
            customer_id=customer.id,
            )

    dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__),"../../.."))
    filename = dir_path+'/tests/integration/audio/tech-support.mp3'
    contents = open(filename, "rb").read()

    headers = {'content-type': "audio/mp3"}
    file = UploadFile(file=io.BytesIO(contents), filename="test.mp3", headers=headers)

    # Initialize all required repositories
    recording_repo = RecordingsRepository(session)
    conversation_repo = ConversationRepository(session)
    conversation_analysis_repo = ConversationAnalysisRepository(session)
    operator_statistics_repo = OperatorStatisticsRepository(session)
    operator_repo = OperatorRepository(session)
    llm_analyst_repo = LlmAnalystRepository(session)
    llm_provider_repo = LlmProviderRepository(session)

    # Initialize all required services
    llm_analyst_service = LlmAnalystService(repository=llm_analyst_repo, llm_provider_repository=llm_provider_repo)
    operator_service = OperatorService(operator_repository=operator_repo, conversation_repository=conversation_repo)
    conversation_analysis_service = ConversationAnalysisService(repository=conversation_analysis_repo)
    operator_statistics_service = OperatorStatisticsService(repository=operator_statistics_repo)
    conversation_service = ConversationService(conversation_repo=conversation_repo,
                                               gpt_kpi_analyzer_service=get_gpt_kpi_analyzer(),
                                               conversation_analysis_service=conversation_analysis_service,
                                               operator_statistics_service=operator_statistics_service,
                                               llm_analyst_service=llm_analyst_service)

    # Initialize AudioService with all dependencies
    service = AudioService(
        recording_repo=recording_repo,
        conversation_service=conversation_service,
        conversation_analysis_service=conversation_analysis_service,
        operator_statistics_service=operator_statistics_service,
        operator_service=operator_service,
        speaker_separator_service=get_speaker_separator(),
        gpt_kpi_analyzer_service=get_gpt_kpi_analyzer(),
        gpt_question_answerer_service=get_question_answerer_service(),
        llm_analyst_service=llm_analyst_service
    )

    await service.process_recording(file, metadata)

async def seed_knowledge_base(session: AsyncSession, created_by: UUID):
    """Seed initial knowledge base items into the database."""
    kb_repo = KnowledgeBaseRepository(session)
    kb_service = KnowledgeBaseService(repository=kb_repo)

    # Example knowledge base item for product documentation
    product_docs = KBCreate(
        name="Product Documentation",
        description="Technical documentation for our products",
        type="text",
        source="internal",
        content="""Product Documentation

1. Core Features
- Real-time audio processing
- AI-powered transcription
- Speaker diarization
- Sentiment analysis
- Custom reporting

2. System Requirements
- Operating System: Windows 10+, macOS 10.15+, Linux
- RAM: 8GB minimum, 16GB recommended
- Storage: 20GB free space
- Internet connection required

3. API Integration
- RESTful API endpoints
- WebSocket support for real-time updates
- OAuth 2.0 authentication
- Rate limiting: 100 requests per minute

4. Security Features
- End-to-end encryption
- Role-based access control
- Audit logging
- Data retention policies

5. Support Resources
- Online documentation
- API reference
- Sample code repositories
- Technical support portal""",
        file_path=None,
        file_type="text",
        file=None,
        vector_store={"config": "default"},
        rag_config={
            "enabled": True,
            "vector_db": {"enabled": True},
            "graph_db": {"enabled": False},
            "light_rag": {"enabled": False}
        }
    )

    # Create knowledge base items
    res = await kb_service.create(product_docs)
    await session.commit()

    logger.debug("Knowledge base seeding complete.")
    return res

async def seed_agents(session: AsyncSession, agent_role: RoleModel):
    """Seed initial agents into the database."""
    # Initialize the agent config service with file repository
    opService = OperatorService(operator_repository=OperatorRepository(session),
                                conversation_repository=ConversationRepository(session),
                                user_repository=UserRepository(session),
                                user_types_repository=UserTypesRepository(session))


    
    workflow_service = WorkflowService(repository=WorkflowRepository(session)) 
    workflow = WorkflowCreate(
        name="Support Assistant",
        description="AI assistant specialized in providing product support and answering customer queries",
        nodes=[{"id": "b517909e-5d23-4d95-84c3-e175fc36e5a9", "data": {"label": "Chat Input", "handlers": [{"id": "output", "type": "source", "compatibility": "text"}], "placeholder": "Type a message..."}, "type": "chatInputNode", "width": 300, "height": 93, "position": {"x": 81.65653220098523, "y": 253.38376194958948}, "selected": False, "positionAbsolute": {"x": 81.65653220098523, "y": 253.38376194958948}}, {"id": "a0277bf8-0a3a-4ab7-8040-5f0570311622", "data": {"label": "Chat Output", "handlers": [{"id": "input", "type": "target", "compatibility": "text"}], "messages": []}, "type": "chatOutputNode", "width": 300, "height": 93, "dragging": False, "position": {"x": 1421.283752237165, "y": 253.39783185667665}, "selected": False, "positionAbsolute": {"x": 1421.283752237165, "y": 253.39783185667665}}, {"id": "d04bff89-3be3-4804-a08c-f5bfd719fa17", "data": {"label": "Prompt Template", "handlers": [{"id": "output", "type": "source", "compatibility": "text"}, {"id": "input_user_query", "type": "target", "compatibility": "text"}], "template": "Please configure Agent Workflow before using it! \n\nYour query: {{user_query}}", "includeHistory": False}, "type": "promptNode", "width": 400, "height": 261, "dragging": False, "position": {"x": 682.6322125384895, "y": 171.07247471791806}, "selected": False, "positionAbsolute": {"x": 682.6322125384895, "y": 171.07247471791806}}],
        edges=[{"id": "reactflow__edge-b517909e-5d23-4d95-84c3-e175fc36e5a9output-d04bff89-3be3-4804-a08c-f5bfd719fa17input_user_query", "source": "b517909e-5d23-4d95-84c3-e175fc36e5a9", "target": "d04bff89-3be3-4804-a08c-f5bfd719fa17", "sourceHandle": "output", "targetHandle": "input_user_query"}, {"id": "reactflow__edge-d04bff89-3be3-4804-a08c-f5bfd719fa17output-a0277bf8-0a3a-4ab7-8040-5f0570311622input", "source": "d04bff89-3be3-4804-a08c-f5bfd719fa17", "target": "a0277bf8-0a3a-4ab7-8040-5f0570311622", "sourceHandle": "output", "targetHandle": "input"}],
        version="1.0"
    )
    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="Support Assistant",
        description="AI assistant specialized in providing product support and answering customer queries",
        is_active=False,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?", "What are queries?"],
    )
    config_service = AgentConfigService(repository=AgentRepository(session),
                                        operator_service=opService,
                                        workflow_service=workflow_service,
                                        user_types_repository=UserTypesRepository(session),
                                        db=session)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id, user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('agent123'),
                            hashed_value=hash_api_key('agent123'),
                            name='test agent key',
                            is_active=1, user_id=full_agent.operator.user.id,)
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()

    logger.debug("Agents seeding complete.")
