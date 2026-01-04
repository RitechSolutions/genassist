import json
import os
from typing import List
from uuid import UUID
import logging
from injector import Injector
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.auth.utils import hash_api_key
from app.core.utils.encryption_utils import encrypt_key
from app.db.models import AgentModel
from app.db.models.api_key import ApiKeyModel
from app.db.models.api_key_role import ApiKeyRoleModel
from app.db.models.role import RoleModel
from app.db.models.user_role import UserRoleModel
from app.db.seed.seed_data_config import seed_test_data
from app.schemas.agent import AgentCreate
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.agent_config import AgentConfigService
from app.services.workflow import WorkflowService
from app.schemas.agent_knowledge import KBRead

logger = logging.getLogger(__name__)


async def seed_demo_agent(session: AsyncSession, agent_role: RoleModel,  injector: Injector, kbList: List[KBRead], owner_user_id: UUID):
    """Seed initial agents into the database."""

    workflow_service = injector.get(WorkflowService)

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/empty_assistant_wf_data.json'
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
        is_active=False,
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

    # Ensure the agent's operator user is in the current session
    await session.refresh(full_agent.operator, ["user"])
    await session.refresh(agent_role)

    # Create UserRoleModel with the agent's operator user
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
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
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
        is_active=False,
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

    # Ensure the agent's operator user is in the current session
    await session.refresh(full_agent.operator, ["user"])
    await session.refresh(agent_role)

    # Create UserRoleModel with the agent's operator user
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
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
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
        is_active=False,
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
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
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
        is_active=False,
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
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
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
        is_active=False,
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
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
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
        is_active=False,
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
    file_path = Path(filename)
    json_str = file_path.read_text()

    json_str = json_str.replace("KB_ID_LIST", ",".join(
        ["\""+str(kb.id)+"\"" for kb in kbList]))
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
        is_active=False,
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

