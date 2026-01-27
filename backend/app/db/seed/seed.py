import asyncio
from datetime import datetime
import io
import json
import os
from typing import List
from fastapi import UploadFile
from pathlib import Path
from injector import Injector
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
from app.schemas.agent import AgentCreate
from app.schemas.recording import RecordingCreate
from app.core.config.settings import settings
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.agent_tool import ToolService
from app.schemas.agent_tool import ToolConfigBase
from app.services.agent_knowledge import KnowledgeBaseService
from app.schemas.agent_knowledge import KBCreate, KBRead
from app.services.agent_config import AgentConfigService
from app.services.workflow import WorkflowService
from app.schemas.datasource import DataSourceCreate
from app.services.datasources import DataSourceService
from app.services.app_settings import AppSettingsService
from app.schemas.app_settings import AppSettingsCreate

logger = logging.getLogger(__name__)


def create_crud_permissions(resource: str, description_template: str = "Allows {action} {resource} data"):
    """Helper function to generate CRUD permissions for a resource."""
    actions = ["create", "read", "update", "delete"]
    return [
        PermissionModel(
            name=f"{action}:{resource}",
            is_active=True,
            description=description_template.format(
                action=action, resource=resource.replace('_', ' '))
        )
        for action in actions
    ]


async def seed_data(session: AsyncSession, injector: Injector):
    """Seeds initial data into the database."""
    from app import settings

    # Create roles
    admin_role = RoleModel(name='admin', role_type="external", is_active=1)
    supervisor_role = RoleModel(
        name='supervisor', role_type="external", is_active=1)
    operator_role = RoleModel(
        name='operator', role_type="internal", is_active=1)
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
    conversation_in_progress_permissions = create_crud_permissions(
        "in_progress_conversation")
    app_settings_permissions = create_crud_permissions("app_settings")
    feature_flag_permissions = create_crud_permissions("feature_flag")

    takeover_supervisor_permission = PermissionModel(name='takeover_in_progress_conversation',
                                                     description='Allow takeover of in progress conversation.',
                                                     is_active=True)

    # Create non-CRUD permissions
    non_standard_crud_permissions = [
        takeover_supervisor_permission,
        PermissionModel(name='create:analyze_recording',
                        description='Allow analysis and transcription of audio record.', is_active=True),
        PermissionModel(name='create:ask_question',
                        description='Allow asking questions to LLM.', is_active=True),
        PermissionModel(name='create:upload_transcript',
                        description='Allow transcript upload.', is_active=True),
        PermissionModel(name='read:files',
                        description='Allow reading files.', is_active=True),
        PermissionModel(
            name='*', description='Allow everything', is_active=True),
    ]

    # Assign all permissions to admin
    for permission in (
            user_permissions + user_type_permissions + role_prm_permissions + prm_permissions + apikey_permissions + recording_permissions +
            conversation_permissions + llm_analyst_permissions + llm_provider_permissions + operator_permissions +
            data_sources_permissions + role_permissions + audit_log_permissions +
            conversation_in_progress_permissions + metrics_permissions +
            non_standard_crud_permissions + app_settings_permissions + feature_flag_permissions
    ):
        admin_role.role_permissions.append(
            RolePermissionModel(permission=permission))

    # Assign supervisor permissions
    for permission in operator_permissions:
        if permission.name in ("read:operator", "update:operator"):
            supervisor_role.role_permissions.append(
                RolePermissionModel(permission=permission))

    supervisor_role.role_permissions.append(
        RolePermissionModel(permission=takeover_supervisor_permission))

    # Assign operator permissions
    for permission in operator_permissions:
        if permission.name == "read:operator":
            operator_role.role_permissions.append(
                RolePermissionModel(permission=permission))

    for permission in conversation_permissions:
        if permission.name == "read:conversation":
            operator_role.role_permissions.append(
                RolePermissionModel(permission=permission))

    # Assign api role permissions
    for permission in operator_permissions:
        if permission.name == "read:operator":
            api_role.role_permissions.append(
                RolePermissionModel(permission=permission))

    for permission in conversation_in_progress_permissions:
        if permission.name in ["create:in_progress_conversation", "update:in_progress_conversation", "read:in_progress_conversation"]:
            agent_role.role_permissions.append(
                RolePermissionModel(permission=permission))

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

    # Create users - passwords from environment variables with secure defaults for development
    # In production, these should be set via environment variables
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    seed_admin_password = os.environ.get('SEED_ADMIN_PASSWORD', 'genadmin')
    seed_supervisor_password = os.environ.get('SEED_SUPERVISOR_PASSWORD', 'gensupervisor1')
    seed_operator_password = os.environ.get('SEED_OPERATOR_PASSWORD', 'genoperator1')
    seed_apiuser_password = os.environ.get('SEED_APIUSER_PASSWORD', 'genapiuser1')
    seed_transcribe_operator_password = os.environ.get('SEED_TRANSCRIBE_OPERATOR_PASSWORD', 'gentranscribeoperator1')

    # Seed usernames from environment variables with defaults for development
    seed_admin_username = os.environ.get('SEED_ADMIN_USERNAME', 'admin')
    seed_supervisor_username = os.environ.get('SEED_SUPERVISOR_USERNAME', 'supervisor1')
    seed_operator_username = os.environ.get('SEED_OPERATOR_USERNAME', 'operator1')
    seed_apiuser_username = os.environ.get('SEED_APIUSER_USERNAME', 'apiuser1')
    seed_transcribe_operator_username = os.environ.get('SEED_TRANSCRIBE_OPERATOR_USERNAME', 'transcribeoperator1')

    admin = UserModel(username=seed_admin_username, email='admin@genassist.ritech.io', is_active=1,
                      hashed_password=pwd_context.hash(seed_admin_password), user_type_id=interactive_user_type.id,
                      id=seed_test_data.admin_user_id,
                      force_upd_pass_date=shift_datetime(
                          unit="months", amount=3)
                      )
    supervisor = UserModel(username=seed_supervisor_username, email='supervisor1@genassist.ritech.io', is_active=1,
                           hashed_password=pwd_context.hash(seed_supervisor_password), user_type_id=interactive_user_type.id,
                           force_upd_pass_date=shift_datetime(
                               unit="months", amount=3)
                           )
    operator = UserModel(id=UUID(seed_test_data.operator_user_id), username=seed_operator_username,
                         email='operator1@genassist.ritech.io',
                         is_active=1,
                         hashed_password=pwd_context.hash(seed_operator_password), user_type_id=interactive_user_type.id,
                         force_upd_pass_date=shift_datetime(
                             unit="months", amount=3)
                         )
    apiuser = UserModel(username=seed_apiuser_username, email='apiuser1@genassist.ritech.io', is_active=1,
                        hashed_password=pwd_context.hash(seed_apiuser_password), user_type_id=console_user_type.id,
                        force_upd_pass_date=shift_datetime(
                            unit="months", amount=3)
                        )

    transcribe_operator_user = UserModel(id=UUID(seed_test_data.transcribe_operator_user_id), username=seed_transcribe_operator_username,
                                         email='transcribeoperator1@genassist.ritech.io',
                                         is_active=1,
                                         hashed_password=pwd_context.hash(seed_transcribe_operator_password), user_type_id=console_user_type.id,
                                         force_upd_pass_date=shift_datetime(
                                             unit="months", amount=3)
                                         )

    # Assign roles to users
    admin.user_roles.append(UserRoleModel(role=admin_role))
    supervisor.user_roles.append(UserRoleModel(role=supervisor_role))
    operator.user_roles.append(UserRoleModel(role=operator_role))
    apiuser.user_roles.append(UserRoleModel(role=api_role))
    transcribe_operator_user.user_roles.append(
        UserRoleModel(role=operator_role))

    session.add_all([admin, supervisor, operator,
                    apiuser, transcribe_operator_user])
    await session.commit()

    # # Seed s3 DataSource
    # s3_data_source = DataSourceModel(id=UUID(seed_test_data.data_source_id), name="s3 contracts small", source_type="S3",
    #                                  connection_data={
    #     "bucket_name": os.environ.get("AWS_S3_TEST_BUCKET"),
    #     "region": os.environ.get("AWS_REGION"),
    #     "access_key": encrypt_key(os.environ.get("AWS_ACCESS_KEY_ID")),
    #     "secret_key": encrypt_key(os.environ.get("AWS_SECRET_ACCESS_KEY")),
    #     "prefix": "contracts-small/"
    # }, is_active=1)

    # # Seed s3 AUDIO DataSource
    # s3_audio_data_source = DataSourceModel(id=UUID(seed_test_data.transcribe_data_source_id), name="s3 audio files to transcribe", source_type="S3",
    #                                        connection_data={
    #     "bucket_name": os.environ.get("AWS_S3_TEST_BUCKET"),
    #     "region": os.environ.get("AWS_REGION"),
    #     "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
    #     "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
    #     "prefix": "sample-recordings/"
    # }, is_active=1)
    # session.add_all([s3_data_source, s3_audio_data_source])

    # await session.commit()

    # Seed default Customer
    customer = CustomerModel(source_ref="default",
                             full_name="default", external_id="default")
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
    local_llm_provider_gpt_oss = LlmProvidersModel(
        id=UUID(seed_test_data.local_llm_provider_gpt_oss_id),
        name='gpt-oss',
        llm_model_provider="ollama",
        is_active=1,
        llm_model="gpt-oss:20b",
        connection_data={
            "base_url": "http://192.168.10.231:11434/",
        }
    )

    local_llm_provider_llama = LlmProvidersModel(
        id=UUID(seed_test_data.local_llm_provider_llama_id),
        name='Llama 3.3 70B 4Q',
        llm_model_provider="ollama",
        is_active=1,
        llm_model="llama3.3:70b-instruct-q4_K_M",
        connection_data={
            "base_url": "http://192.168.10.231:11434/",
        }
    )
    local_llm_provider_vllm_llama = LlmProvidersModel(
        id=UUID(seed_test_data.local_llm_provider_vllm_llama),
        name='Llama 3.1 8B custom',
        llm_model_provider="vllm",
        is_active=1,
        llm_model="./outputs/llama-3.1-8b-tool-calling/merged",
        connection_data={
            "base_url": "http://192.168.10.231:11434/",
        }
    )
    session.add_all([llm_provider, local_llm_provider_gpt_oss,
                    local_llm_provider_llama, local_llm_provider_vllm_llama])
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
    session.add_all([gpt_speaker_separator_llm_analyst,
                    gpt_kpi_analyzer_llm_analyst, in_progress_hostility_llm_analyst])

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

    # Seed Transcribe operator
    transcribe_operator = OperatorModel(
        id=UUID(seed_test_data.transcribe_operator_id),
        first_name='Transcribe',
        last_name='Operator 01',
        is_active=1,
        statistics_id=op_stats.id,
        user_id=seed_test_data.transcribe_operator_user_id
    )
    session.add(transcribe_operator)
    await session.commit()

    # Seed ZEN operator statistics
    zen_op_stats = OperatorStatisticsModel(
        avg_positive_sentiment=0, call_count=0,
        avg_negative_sentiment=0, avg_neutral_sentiment=0
    )
    session.add(zen_op_stats)
    await session.commit()

    # Seed Zendesk Operator
    zen_operator = OperatorModel(
        id=UUID(seed_test_data.zen_operator_id),
        first_name='Zendesk',
        last_name='Operator',
        is_active=1,
        statistics_id=zen_op_stats.id,
        user_id=seed_test_data.zen_operator_user_id
    )
    session.add(zen_operator)
    await session.commit()

    # Seed API key
    api_key = ApiKeyModel(key_val=encrypt_key('test123'), name='test key',
                          hashed_value=hash_api_key('test123'),
                          is_active=1, user_id=admin.id)
    api_key.api_key_roles.append(ApiKeyRoleModel(role=admin_role))
    session.add(api_key)
    await session.commit()

    # Seed tools
    # currency_tool = await seed_tools(session, admin.id, injector)

    # Seed knowledge base
    product_docs = await seed_knowledge_base(session, admin.id, injector)
    gen_assist_kb = await seed_knowledge_base_for_gen_agent(session, admin.id, injector)
    db_kb = await seed_knowledge_base_for_sql_database(session, admin.id, injector)
    # s3_kb = await seed_knowledge_base_for_s3(session, admin.id, s3_data_source, injector)

    # Seed agents
    await seed_demo_agent(session, agent_role, injector, [product_docs], admin.id)
    await seed_gen_agent(session, agent_role, injector, [product_docs, gen_assist_kb, db_kb], admin.id)

    # Seed common workflows
    # await seed_zendesk_agent(session, agent_role, injector, [product_docs, gen_assist_kb, db_kb], admin.id)
    # await seed_slack_agent(session, agent_role, injector, [product_docs, gen_assist_kb, db_kb], admin.id)
    # await seed_whatsapp_agent(session, agent_role, injector, [product_docs, gen_assist_kb, db_kb], admin.id)
    # await seed_gmail_agent(session, agent_role, injector, [product_docs, gen_assist_kb, db_kb], admin.id)
    # await seed_hr_cv_agent(session, agent_role, injector, [], admin.id)
    # Seed conversation
    # await create_conversation(session, operator, data_source, customer, injector)

    # Seed connection data
    await seed_connection_data_for_zendesk(session, admin.id, injector)
    await seed_connection_data_for_whatsapp(session, admin.id, injector)
    await seed_connection_data_for_gmail(session, admin.id, injector)
    await seed_connection_data_for_microsoft(session, admin.id, injector)
    await seed_connection_data_for_slack(session, admin.id, injector)

    logger.debug("Database seeding complete.")


async def seed_tools(session: AsyncSession, created_by: UUID, injector: Injector):
    """Seed initial tools into the database."""
    tool_service = injector.get(ToolService)

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


async def create_conversation(session: AsyncSession, operator: OperatorModel, data_source: DataSourceModel, customer: CustomerModel, injector: Injector):
    metadata = RecordingCreate(
        operator_id=operator.id,
        transcription_model_name=settings.DEFAULT_WHISPER_MODEL,
        llm_analyst_speaker_separator_id=None,
        llm_analyst_kpi_analyzer_id=None,
        recorded_at=datetime.now(),
        data_source_id=data_source.id,
        customer_id=customer.id,
    )

    dir_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "../../.."))
    filename = dir_path+'/tests/integration/audio/tech-support.mp3'
    contents = open(filename, "rb").read()

    headers = {'content-type': "audio/mp3"}
    file = UploadFile(file=io.BytesIO(contents),
                      filename="test.mp3", headers=headers)

    # await injector.get(AudioService).process_recording(file, metadata)


async def seed_knowledge_base(session: AsyncSession, created_by: UUID, injector: Injector):
    """Seed initial knowledge base items into the database."""
    kb_service = injector.get(KnowledgeBaseService)

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
        files=[],
        vector_store={"config": "default"},
        rag_config={
            "enabled": False,
            "vector_db": {"enabled": False},
            "light_rag": {"enabled": False}
        }
    )

    # Create knowledge base items
    res = await kb_service.create(product_docs)
    await session.commit()

    logger.debug("Product Knowledge base seeding complete.")
    return res


async def seed_knowledge_base_for_gen_agent(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> KBRead:
    open_api_path = Path(settings.OPENAPI_PATH)
    kb_service: KnowledgeBaseService = injector.get(KnowledgeBaseService)

    # ── 1️⃣  read the file in a worker thread ────────────────────────────
    if not open_api_path.exists():
        raise FileNotFoundError(
            "openapi.json not found. Did output_open_api() run before seeding?"
        )

    raw_json: str = await asyncio.to_thread(
        open_api_path.read_text, encoding="utf-8"
    )

    # ── 2️⃣  build the KB item ──────────────────────────────────────────
    openapi_item = KBCreate(
        name="GenAssist OpenAPI Schema",
        description="Generated OpenAPI spec for every backend route",
        type="text",                       # or "text" if your column is TEXT
        source="internal",
        content=raw_json,
        file_path=str(open_api_path),
        file_type="application/json",
        vector_store={"config": "default"},
        rag_config={
            "enabled": False,
            "vector_db": {"enabled": False},
            "light_rag": {"enabled": False},
        },
    )

    kb = await kb_service.create(openapi_item)
    await session.commit()

    logger.debug("Genassist Knowledge base seeding complete.")
    return kb


async def seed_demo_agent(session: AsyncSession, agent_role: RoleModel,  injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial agents into the database."""

    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/empty_assistant_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]
    wf_execution_state = sample_wf["executionState"]

    workflow = WorkflowCreate(name="Support Assistant",
                              description="AI assistant specialized in providing product support and answering customer queries",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              executionState=wf_execution_state,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="Support Assistant",
        description="AI assistant specialized in providing product support and answering customer queries",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?", "What are queries?"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)


    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
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


async def seed_gen_agent(session: AsyncSession, agent_role: RoleModel, injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial agents into the database."""

    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/genassist_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
    # print(f"JSON string after replacement: {json_str}")
    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]
    wf_execution_state = sample_wf["executionState"]

    workflow = WorkflowCreate(name="GenAgent Assistant Workflow",
                              description="AI assistant workflow specialized to provide information about genagent",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              executionState=wf_execution_state,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        id=seed_test_data.genassist_agent_id,
        name="Support Assistant for genassist",
        description="AI assistant specialized in providing information about genassist",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?",
                          "What endpoints does genagent have about metrics"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)


    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('genagent123'),
                            hashed_value=hash_api_key('genagent123'),
                            name='gen-agent default key',
                            is_active=1, user_id=full_agent.operator.user.id, )
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()

    logger.debug("Agents seeding complete.")


async def seed_zendesk_agent(session: AsyncSession, agent_role: RoleModel, injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial Zendesk agent into the database."""
    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/zendesk_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
    # print(f"JSON string after replacement: {json_str}")
    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]

    workflow = WorkflowCreate(name="Zendesk Agent Workflow",
                              description="AI assistant workflow specialized to send tickets in zendesk",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="Zendesk Agent",
        description="AI assistant specialized to send tickets in zendesk",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)

    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('zendesk123'),
                            hashed_value=hash_api_key('zendesk123'),
                            name='zendesk default key',
                            is_active=1, user_id=full_agent.operator.user.id, )
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()
    logger.debug("Zendesk Agent seeding complete.")


async def seed_slack_agent(session: AsyncSession, agent_role: RoleModel, injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial Slack agent into the database."""
    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/slack_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
    # print(f"JSON string after replacement: {json_str}")
    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]

    workflow = WorkflowCreate(name="Slack Agent Workflow",
                              description="AI assistant workflow specialized to send messages in slack",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="Slack Agent",
        description="AI assistant specialized to send messages in slack",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)

    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('slack123'),
                            hashed_value=hash_api_key('slack123'),
                            name='slack default key',
                            is_active=1, user_id=full_agent.operator.user.id, )
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()
    logger.debug("Slack Agent seeding complete.")


async def seed_whatsapp_agent(session: AsyncSession, agent_role: RoleModel, injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial WhatsApp agent into the database."""
    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/whatsapp_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
    # print(f"JSON string after replacement: {json_str}")
    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]

    workflow = WorkflowCreate(name="WhatsApp Agent Workflow",
                              description="AI assistant workflow specialized to send messages in WhatsApp",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="WhatsApp Agent",
        description="AI assistant specialized to send messages in WhatsApp",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)

    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('whatsapp123'),
                            hashed_value=hash_api_key('whatsapp123'),
                            name='whatsapp default key',
                            is_active=1, user_id=full_agent.operator.user.id, )
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()
    logger.debug("WhatsApp Agent seeding complete.")


async def seed_gmail_agent(session: AsyncSession, agent_role: RoleModel, injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial Gmail agent into the database."""
    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/gmail_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
    # print(f"JSON string after replacement: {json_str}")
    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]

    workflow = WorkflowCreate(name="Gmail Agent Workflow",
                              description="AI assistant workflow specialized to send emails in Gmail",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="Gmail Agent",
        description="AI assistant specialized to send emails in Gmail",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)

    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('gmail123'),
                            hashed_value=hash_api_key('gmail123'),
                            name='gmail default key',
                            is_active=1, user_id=full_agent.operator.user.id, )
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()
    logger.debug("Gmail Agent seeding complete.")


async def seed_hr_cv_agent(session: AsyncSession, agent_role: RoleModel, injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial HR CV agent into the database."""
    workflow_service = injector.get(WorkflowService)
    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/hr_cv_analyzer_wf_data.json'
    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
    # print(f"JSON string after replacement: {json_str}")
    sample_wf = json.loads(json_str)
    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]
    workflow = WorkflowCreate(name="HR CV Agent Workflow",
                              description="AI assistant workflow specialized to analyze CVs",
                              nodes=wf_nodes,
                              edges=wf_edges,
                              version="1.0")

    workflow_model = await workflow_service.create(workflow)

    support_agent = AgentCreate(
        name="HR-CV Analyzer Agent",
        description="AI assistant specialized to analyze CVs",
        is_active=True,
        welcome_message="Welcome, how may I help you?",
        possible_queries=["What can you do?"],
        workflow_id=workflow_model.id,
    )
    config_service = injector.get(AgentConfigService)
    # Create the agent configuration
    agent_model = await config_service.create(support_agent, user_id=owner_user_id)
    full_agent: AgentModel = await config_service.get_by_id_full(agent_model.id)

    workflow_update_data = WorkflowUpdate(name=workflow_model.name,
                                          description=workflow_model.description,
                                          nodes=wf_nodes,
                                          edges=wf_edges,
                                          user_id=owner_user_id,
                                          version=workflow_model.version,
                                          agent_id=full_agent.id)

    await workflow_service.update(workflow_model.id, workflow_update_data)

    await session.refresh(agent_role)
    urm = UserRoleModel(role_id=agent_role.id,
                        user_id=full_agent.operator.user.id)
    session.add(urm)
    await session.commit()

    agent_key = ApiKeyModel(key_val=encrypt_key('hr_cv123'),
                            hashed_value=hash_api_key('hr_cv123'),
                            name='hr-cv default key',
                            is_active=1, user_id=full_agent.operator.user.id, )
    agent_key.api_key_roles.append(ApiKeyRoleModel(role=agent_role))
    session.add(agent_key)

    await session.commit()
    logger.debug("HR CV Agent seeding complete.")


async def seed_knowledge_base_for_sql_database(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> KBRead:
    ds_service: DataSourceService = injector.get(DataSourceService)
    kb_service: KnowledgeBaseService = injector.get(KnowledgeBaseService)
    logger.info("Seeding SQL database knowledge base...")

    # 1. Build the sql datasource item
    sql_datasource = DataSourceCreate(
        name="Genassist Local SQL DataSource",
        source_type="Database",
        connection_data={
            "database_type": "postgresql",
            "database_host": settings.DB_HOST,
            "database_port": settings.DB_PORT,
            "database_name": settings.DB_NAME,
            "database_user": settings.DB_USER,
            "database_password": settings.DB_PASS,
            # "connection_string": f"postgresql://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}/{settings.DB_NAME}",
            "allowed_tables": ['conversations', 'operators']},
        is_active=1,
    )

    ds = await ds_service.create(sql_datasource)
    await session.commit()
    logger.info(f"Created SQL Data Source: {ds.id}")

    # 2. Build the sql knowledge base item
    sql_kb = KBCreate(
        name="Genassist SQL Database Knowledge Base",
        description="Connects to a PostgreSQL database to retrieve information",
        type="database",
        content="This knowledge base connects to a PostgreSQL database to retrieve information about conversations and operators.",
        rag_config={
            "enabled": False,
            "vector_db": {"enabled": False},
            "light_rag": {"enabled": False},
        },
        llm_provider_id=seed_test_data.llm_provider_id,
        sync_source_id=ds.id,
    )

    kb = await kb_service.create(sql_kb)
    await session.commit()

    logger.debug("Genassist SQL database knowledge base seeding complete.")
    return kb


async def seed_knowledge_base_for_s3(
    session: AsyncSession,
    created_by: UUID,
    s3_datasource: DataSourceModel,
    injector: Injector,
) -> KBRead:
    kb_service: KnowledgeBaseService = injector.get(KnowledgeBaseService)
    logger.info("Seeding S3 knowledge base...")

    kb = KBCreate(
        name="S3 contracts Knowledge Base - small",
        description="Connects to an S3 bucket to retrieve information",
        type="s3",
        content="This knowledge base connects to an S3 bucket to retrieve information about contracts.",
        rag_config={
            "enabled": True,
            "vector_db": {"enabled": True},
            "light_rag": {"enabled": False},
        },
        sync_source_id=s3_datasource.id,
        sync_schedule="0 0 * * *",  # every day at midnight
        sync_active=True,
    )

    kb = await kb_service.create(kb)
    await session.commit()

    logger.debug("Genassist S3 database knowledge base seeding complete.")
    return kb


async def seed_connection_data_for_zendesk(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> None:
    """Seed Zendesk connection data."""
    app_settings_service: AppSettingsService = injector.get(AppSettingsService)
    logger.info("Seeding Zendesk connection data...")

    zendesk_settings = {
        "zendesk_subdomain": settings.ZENDESK_SUBDOMAIN,
        "zendesk_email": settings.ZENDESK_EMAIL,
        "zendesk_api_token": settings.ZENDESK_API_TOKEN
    }

    try:
        # Check if all required values are present
        missing_values = {k: v for k, v in zendesk_settings.items() if not v}
        if missing_values:
            raise ValueError(
                f"Missing required Zendesk settings: {list(missing_values.keys())}")

        # Create one Zendesk setting with all values in a JSONB object
        item = AppSettingsCreate(
            name="Zendesk Integration",
            type="Zendesk",
            values=zendesk_settings,
            description="Zendesk integration settings",
            is_active=1
        )

        await app_settings_service.create(item)

        await session.commit()
        logger.info("Zendesk connection data seeded successfully.")

    except Exception as e:
        logger.error(f"Failed to seed Zendesk connection data: {e}")


async def seed_connection_data_for_whatsapp(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> None:
    """Seed WhatsApp connection data."""
    app_settings_service: AppSettingsService = injector.get(AppSettingsService)
    logger.info("Seeding WhatsApp connection data...")

    whatsapp_settings = {
        "whatsapp_token": settings.WHATSAPP_TOKEN
    }

    try:
        # Check if all required values are present
        missing_values = {k: v for k, v in whatsapp_settings.items() if not v}
        if missing_values:
            raise ValueError(
                f"Missing required WhatsApp settings: {list(missing_values.keys())}")

        # Create one WhatsApp setting with all values in a JSONB object
        item = AppSettingsCreate(
            name="WhatsApp Integration",
            type="WhatsApp",
            values=whatsapp_settings,
            description="WhatsApp integration settings",
            is_active=1
        )

        whatsapp_item = await app_settings_service.create(item)

        await session.commit()
        logger.info("WhatsApp connection data seeded successfully.")

    except Exception as e:
        logger.error(f"Failed to seed WhatsApp connection data: {e}")


async def seed_connection_data_for_gmail(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> None:
    """Seed Gmail connection data."""
    app_settings_service: AppSettingsService = injector.get(AppSettingsService)
    logger.info("Seeding Gmail connection data...")

    gmail_settings = {
        "gmail_client_id": settings.GMAIL_CLIENT_ID,
        "gmail_client_secret": settings.GMAIL_CLIENT_SECRET,
        # "gmail_refresh_token": settings.GMAIL_REFRESH_TOKEN
    }

    try:
        # Check if all required values are present
        missing_values = {k: v for k, v in gmail_settings.items() if not v}
        if missing_values:
            raise ValueError(
                f"Missing required Gmail settings: {list(missing_values.keys())}")

        # Create one Gmail setting with all values in a JSONB object
        item = AppSettingsCreate(
            name="Gmail Integration",
            type="Gmail",
            values=gmail_settings,
            description="Gmail integration settings",
            is_active=1
        )

        gmail_item = await app_settings_service.create(item)

        await session.commit()
        logger.info("Gmail connection data seeded successfully.")

    except Exception as e:
        logger.error(f"Failed to seed Gmail connection data: {e}")


async def seed_connection_data_for_microsoft(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> None:
    """Seed Microsoft connection data."""
    app_settings_service: AppSettingsService = injector.get(AppSettingsService)
    logger.info("Seeding Microsoft connection data...")

    microsoft_settings = {
        "microsoft_client_id": settings.MICROSOFT_CLIENT_ID,
        "microsoft_client_secret": settings.MICROSOFT_CLIENT_SECRET,
        "microsoft_tenant_id": settings.MICROSOFT_TENANT_ID
    }

    try:
        # Check if all required values are present
        missing_values = {k: v for k, v in microsoft_settings.items() if not v}
        if missing_values:
            raise ValueError(
                f"Missing required Microsoft settings: {list(missing_values.keys())}")

        # Create one Microsoft setting with all values in a JSONB object
        item = AppSettingsCreate(
            name="Microsoft Integration",
            type="Microsoft",
            values=microsoft_settings,
            description="Microsoft integration settings",
            is_active=1
        )

        microsoft_item = await app_settings_service.create(item)

        await session.commit()
        logger.info("Microsoft connection data seeded successfully.")

    except Exception as e:
        logger.error(f"Failed to seed Microsoft connection data: {e}")


async def seed_connection_data_for_slack(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> None:
    """Seed Slack connection data."""
    app_settings_service: AppSettingsService = injector.get(AppSettingsService)
    logger.info("Seeding Slack connection data...")

    slack_settings = {
        "slack_bot_token": settings.SLACK_TOKEN,
        "slack_signing_secret": settings.SLACK_SIGNING_SECRET
    }

    try:
        # Check if all required values are present
        missing_values = {k: v for k, v in slack_settings.items() if not v}
        if missing_values:
            raise ValueError(
                f"Missing required Slack settings: {list(missing_values.keys())}")

        # Create one Slack setting with all values in a JSONB object
        item = AppSettingsCreate(
            name="Slack Integration",
            type="Slack",
            values=slack_settings,
            description="Slack integration settings",
            is_active=1
        )

        await app_settings_service.create(item)

        await session.commit()
        logger.info("Slack connection data seeded successfully.")

    except Exception as e:
        logger.error(f"Failed to seed Slack connection data: {e}")
