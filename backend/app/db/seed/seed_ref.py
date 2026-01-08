import asyncio
from datetime import datetime
import io
import os
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
from app.schemas.recording import RecordingCreate
from app.core.config.settings import settings
from app.services.agent_tool import ToolService
from app.schemas.agent_tool import ToolConfigBase
from app.services.agent_knowledge import KnowledgeBaseService
from app.schemas.agent_knowledge import KBCreate, KBRead
from app.schemas.datasource import DataSourceCreate
from app.services.datasources import DataSourceService
from app.services.app_settings import AppSettingsService
from app.schemas.app_settings import AppSettingsCreate

# Import agent seeding functions from separate module
from app.db.seed.seed_agents import (
    seed_demo_agent,
    seed_gen_agent,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

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


# ============================================================================
# Decoupled Seed Functions
# ============================================================================

async def seed_roles_and_permissions(session: AsyncSession) -> dict:
    """Seed roles and permissions into the database.

    Returns:
        Dictionary containing role models keyed by role names.
    """
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

    return {
        'admin': admin_role,
        'supervisor': supervisor_role,
        'operator': operator_role,
        'api': api_role,
        'agent': agent_role
    }


async def seed_user_types(session: AsyncSession) -> dict:
    """Seed user types into the database.

    Returns:
        Dictionary containing user type models keyed by type names.
    """
    console_user_type = UserTypeModel(name='console')
    interactive_user_type = UserTypeModel(name='interactive')
    session.add_all([console_user_type, interactive_user_type])
    await session.commit()

    return {
        'console': console_user_type,
        'interactive': interactive_user_type
    }


async def seed_users(session: AsyncSession, user_types: dict, roles: dict) -> dict:
    """Seed users into the database.

    Args:
        session: Database session
        user_types: Dictionary of user types
        roles: Dictionary of roles

    Returns:
        Dictionary containing user models keyed by usernames.
    """

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin = UserModel(username='admin', email='admin@genassist.ritech.io', is_active=1,
                      hashed_password=pwd_context.hash('genadmin'), user_type_id=user_types['interactive'].id,
                      id=seed_test_data.admin_user_id,
                      force_upd_pass_date=shift_datetime(
                          unit="months", amount=3)
                      )
    supervisor = UserModel(username='supervisor1', email='supervisor1@genassist.ritech.io', is_active=1,
                           hashed_password=pwd_context.hash('gensupervisor1'), user_type_id=user_types['interactive'].id,
                           force_upd_pass_date=shift_datetime(
                               unit="months", amount=3)
                           )
    operator = UserModel(id=UUID(seed_test_data.operator_user_id), username='operator1',
                         email='operator1@genassist.ritech.io',
                         is_active=1,
                         hashed_password=pwd_context.hash('genoperator1'), user_type_id=user_types['interactive'].id,
                         force_upd_pass_date=shift_datetime(
                             unit="months", amount=3)
                         )
    apiuser = UserModel(username='apiuser1', email='apiuser1@genassist.ritech.io', is_active=1,
                        hashed_password=pwd_context.hash('genapiuser1'), user_type_id=user_types['console'].id,
                        force_upd_pass_date=shift_datetime(
                            unit="months", amount=3)
                        )

    transcribe_operator_user = UserModel(id=UUID(seed_test_data.transcribe_operator_user_id), username='transcribeoperator1',
                                         email='transcribeoperator1@genassist.ritech.io',
                                         is_active=1,
                                         hashed_password=pwd_context.hash('gentranscribeoperator1'), user_type_id=user_types['console'].id,
                                         force_upd_pass_date=shift_datetime(
                                             unit="months", amount=3)
                                         )

    # Assign roles to users
    admin.user_roles.append(UserRoleModel(role=roles['admin']))
    supervisor.user_roles.append(UserRoleModel(role=roles['supervisor']))
    operator.user_roles.append(UserRoleModel(role=roles['operator']))
    apiuser.user_roles.append(UserRoleModel(role=roles['api']))
    transcribe_operator_user.user_roles.append(
        UserRoleModel(role=roles['operator']))

    session.add_all([admin, supervisor, operator,
                    apiuser, transcribe_operator_user])
    await session.commit()

    return {
        'admin': admin,
        'supervisor': supervisor,
        'operator': operator,
        'apiuser': apiuser,
        'transcribe_operator': transcribe_operator_user
    }


async def seed_data_sources(session: AsyncSession) -> dict:
    """Seed data sources into the database.

    Returns:
        Dictionary containing data source models keyed by names.
    """
    # Seed s3 DataSource
    s3_data_source = DataSourceModel(id=UUID(seed_test_data.data_source_id), name="s3 contracts small", source_type="S3",
                                     connection_data={
        "bucket_name": os.environ.get("AWS_S3_TEST_BUCKET"),
        "region": os.environ.get("AWS_REGION"),
        "access_key": encrypt_key(os.environ.get("AWS_ACCESS_KEY_ID")),
        "secret_key": encrypt_key(os.environ.get("AWS_SECRET_ACCESS_KEY")),
        "prefix": "contracts-small/"
    }, is_active=1)

    # Seed s3 AUDIO DataSource
    s3_audio_data_source = DataSourceModel(id=UUID(seed_test_data.transcribe_data_source_id), name="s3 audio files to transcribe", source_type="S3",
                                           connection_data={
        "bucket_name": os.environ.get("AWS_S3_TEST_BUCKET"),
        "region": os.environ.get("AWS_REGION"),
        "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
        "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "prefix": "sample-recordings/"
    }, is_active=1)
    session.add_all([s3_data_source, s3_audio_data_source])

    await session.commit()

    return {
        's3': s3_data_source,
        's3_audio': s3_audio_data_source
    }


async def seed_customer(session: AsyncSession):
    """Seed customer into the database."""
    customer = CustomerModel(source_ref="default",
                             full_name="default", external_id="default")
    session.add(customer)
    await session.commit()


async def seed_llm_providers(session: AsyncSession) -> dict:
    """Seed LLM providers into the database.

    Returns:
        Dictionary containing LLM provider models keyed by names.
    """
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

    return {
        'openai': llm_provider,
        'gpt_oss': local_llm_provider_gpt_oss,
        'llama': local_llm_provider_llama,
        'vllm_llama': local_llm_provider_vllm_llama
    }


async def seed_llm_analysts(session: AsyncSession, llm_provider):
    """Seed LLM analysts into the database.

    Args:
        session: Database session
        llm_provider: LLM provider model
    """
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


async def seed_operators(session: AsyncSession) -> dict:
    """Seed operators into the database.

    Returns:
        Dictionary containing operator models keyed by names.
    """
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

    return {
        'main': operator,
        'transcribe': transcribe_operator,
        'zendesk': zen_operator
    }


async def seed_api_keys(session: AsyncSession, admin_user, admin_role):
    """Seed API keys into the database.

    Args:
        session: Database session
        admin_user: Admin user model
        admin_role: Admin role model
    """
    api_key = ApiKeyModel(key_val=encrypt_key('test123'), name='test key',
                          hashed_value=hash_api_key('test123'),
                          is_active=1, user_id=admin_user.id)
    api_key.api_key_roles.append(ApiKeyRoleModel(role=admin_role))
    session.add(api_key)
    await session.commit()


async def seed_app_settings(session: AsyncSession, injector: Injector) -> None:
    """Seed all app settings into the database.

    Args:
        session: Database session
        injector: Dependency injection container
    """
    app_settings_service: AppSettingsService = injector.get(AppSettingsService)
    logger.info("Seeding app settings...")

    # Define all app settings grouped by service
    all_settings = {
        "Zendesk": {
            "zendesk_subdomain": settings.ZENDESK_SUBDOMAIN,
            "zendesk_email": settings.ZENDESK_EMAIL,
            "zendesk_api_token": settings.ZENDESK_API_TOKEN
        },
        "WhatsApp": {
            "whatsapp_token": settings.WHATSAPP_TOKEN
        },
        "Gmail": {
            "gmail_client_id": settings.GMAIL_CLIENT_ID,
            "gmail_client_secret": settings.GMAIL_CLIENT_SECRET,
        },
        "Microsoft": {
            "microsoft_client_id": settings.MICROSOFT_CLIENT_ID,
            "microsoft_client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "microsoft_tenant_id": settings.MICROSOFT_TENANT_ID
        },
        "Slack": {
            "slack_bot_token": settings.SLACK_TOKEN,
            "slack_signing_secret": settings.SLACK_SIGNING_SECRET
        }
    }

    success_count = 0
    error_count = 0

    for service_name, service_settings in all_settings.items():
        try:
            # Check if all required values are present
            missing_values = {k: v for k,
                              v in service_settings.items() if not v}
            if missing_values:
                logger.warning(
                    f"Missing {service_name} settings: {list(missing_values.keys())}")
                error_count += 1
                continue

            # Create one setting per service type with all values in a JSONB object
            item = AppSettingsCreate(
                name=f"{service_name} Integration",
                type=service_name,
                values=service_settings,
                description=f"{service_name} integration settings",
                is_active=1
            )

            await app_settings_service.create(item)
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to seed {service_name} settings: {e}")
            error_count += 1

    # Commit only after all items are created
    if success_count > 0:
        await session.commit()
        logger.info(
            f"Successfully seeded {success_count} app settings. {error_count} failed.")
    else:
        logger.warning("No app settings were seeded successfully.")


# ============================================================================
# Main Seed Function (Backward Compatibility)
# ============================================================================

async def seed_data(session: AsyncSession, injector: Injector):
    """Seeds initial data into the database.

    This function maintains backward compatibility and orchestrates all seed operations.
    Individual seed operations can be called independently for more granular control.
    """
    # Seed roles and permissions
    roles = await seed_roles_and_permissions(session)

    # Seed user types
    user_types = await seed_user_types(session)

    # Seed users
    users = await seed_users(session, user_types, roles)

    # Seed data sources
    data_sources = await seed_data_sources(session)

    # Seed customer
    await seed_customer(session)

    # Seed LLM providers
    llm_providers = await seed_llm_providers(session)

    # Seed LLM analysts
    await seed_llm_analysts(session, llm_providers['openai'])

    # Seed operators
    await seed_operators(session)

    # Seed API keys
    await seed_api_keys(session, users['admin'], roles['admin'])

    # Seed knowledge base
    product_docs = await seed_knowledge_base(session, users['admin'].id, injector)
    gen_assist_kb = await seed_knowledge_base_for_gen_agent(session, users['admin'].id, injector)
    db_kb = await seed_knowledge_base_for_sql_database(session, users['admin'].id, injector)
    await seed_knowledge_base_for_s3(session, users['admin'].id, data_sources['s3'], injector)

    # Seed agents
    await seed_demo_agent(session, roles['agent'], injector, [product_docs], users['admin'].id)
    await seed_gen_agent(session, roles['agent'], injector, [product_docs, gen_assist_kb, db_kb], users['admin'].id)

    # Seed common workflows (commented out)
    # await seed_zendesk_agent(session, roles['agent'], injector, [product_docs, gen_assist_kb, db_kb], users['admin'].id)
    # await seed_slack_agent(session, roles['agent'], injector, [product_docs, gen_assist_kb, db_kb], users['admin'].id)
    # await seed_whatsapp_agent(session, roles['agent'], injector, [product_docs, gen_assist_kb, db_kb], users['admin'].id)
    # await seed_gmail_agent(session, roles['agent'], injector, [product_docs, gen_assist_kb, db_kb], users['admin'].id)
    # await seed_hr_cv_agent(session, roles['agent'], injector, [], users['admin'].id)

    # Seed app settings
    await seed_app_settings(session, injector)

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

    # Check if knowledge base already exists
    kb_name = "Product Documentation"
    all_kbs = await kb_service.get_all()
    existing_kb = next((kb for kb in all_kbs if kb.name == kb_name), None)

    if existing_kb:
        logger.info(
            f"Knowledge base '{kb_name}' already exists, skipping creation.")
        return existing_kb

    # Example knowledge base item for product documentation
    product_docs = KBCreate(
        name=kb_name,
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
            "graph_db": {"enabled": False},
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

    # Check if knowledge base already exists
    kb_name = "GenAssist OpenAPI Schema"
    all_kbs = await kb_service.get_all()
    existing_kb = next((kb for kb in all_kbs if kb.name == kb_name), None)

    if existing_kb:
        logger.info(
            f"Knowledge base '{kb_name}' already exists, skipping creation.")
        return existing_kb

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
        name=kb_name,
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
            "graph_db": {"enabled": False},
            "light_rag": {"enabled": False},
        },
    )

    kb = await kb_service.create(openapi_item)
    await session.commit()

    logger.debug("Genassist Knowledge base seeding complete.")
    return kb


async def seed_knowledge_base_for_sql_database(
    session: AsyncSession,
    created_by: UUID,
    injector: Injector,
) -> KBRead:
    ds_service: DataSourceService = injector.get(DataSourceService)
    kb_service: KnowledgeBaseService = injector.get(KnowledgeBaseService)
    logger.info("Seeding SQL database knowledge base...")

    # Check if knowledge base already exists
    kb_name = "Genassist SQL Database Knowledge Base"
    all_kbs = await kb_service.get_all()
    existing_kb = next((kb for kb in all_kbs if kb.name == kb_name), None)

    if existing_kb:
        logger.info(
            f"Knowledge base '{kb_name}' already exists, skipping creation.")
        return existing_kb

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
        name=kb_name,
        description="Connects to a PostgreSQL database to retrieve information",
        type="database",
        content="This knowledge base connects to a PostgreSQL database to retrieve information about conversations and operators.",
        rag_config={
            "enabled": False,
            "vector_db": {"enabled": False},
            "graph_db": {"enabled": False},
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

    # Check if knowledge base already exists
    kb_name = "S3 contracts Knowledge Base - small"
    all_kbs = await kb_service.get_all()
    existing_kb = next((kb for kb in all_kbs if kb.name == kb_name), None)

    if existing_kb:
        logger.info(
            f"Knowledge base '{kb_name}' already exists, skipping creation.")
        return existing_kb

    kb = KBCreate(
        name=kb_name,
        description="Connects to an S3 bucket to retrieve information",
        type="s3",
        content="This knowledge base connects to an S3 bucket to retrieve information about contracts.",
        rag_config={
            "enabled": True,
            "vector_db": {"enabled": True},
            "graph_db": {"enabled": False},
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
