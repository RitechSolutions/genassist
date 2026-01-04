# import pytest
# from unittest.mock import AsyncMock, MagicMock
# from uuid import uuid4
# from app.services.agent_config import AgentConfigService
# from app.repositories.base_repository import BaseRepository
# from app.schemas.agent_config import AgentConfig
#
# @pytest.fixture
# def mock_repository():
#     return AsyncMock(spec=BaseRepository[AgentConfig])
#
# @pytest.fixture
# def agent_config_service(mock_repository):
#     return AgentConfigService(repository=mock_repository)
#
# @pytest.fixture
# def sample_agent_config_data():
#     return {
#         "id": str(uuid4()),
#         "name": "test_agent",
#         "description": "Test agent description",
#         "provider": "openai",
#         "model": "gpt-3.5-turbo",
#         "system_prompt": "Test system prompt",
#         "knowledge_base_ids": [],
#         "tool_ids": [],
#         "settings": {},
#         "is_active": True
#     }
#
# @pytest.mark.asyncio
# async def test_get_all_agent_configs(agent_config_service, mock_repository):
#     # Setup
#     mock_configs = [
#         MagicMock(
#             id=str(uuid4()),
#             name=f"agent{i}",
#             description=f"Description {i}",
#             provider="openai",
#             model="gpt-3.5-turbo",
#             system_prompt=f"System prompt {i}",
#             knowledge_base_ids=[],
#             tool_ids=[],
#             settings={},
#             is_active=True
#         )
#         for i in range(3)
#     ]
#     mock_repository.get_all.return_value = mock_configs
#
#     # Execute
#     result = await agent_config_service.get_all()
#
#     # Assert
#     mock_repository.get_all.assert_called_once()
#     assert result == mock_configs
#
# @pytest.mark.asyncio
# async def test_get_agent_config_by_id_success(agent_config_service, mock_repository, sample_agent_config_data):
#     # Setup
#     config_id = sample_agent_config_data["id"]
#     mock_config = MagicMock(**sample_agent_config_data)
#     mock_repository.get_by_id.return_value = mock_config
#
#     # Execute
#     result = await agent_config_service.get_by_id(config_id)
#
#     # Assert
#     mock_repository.get_by_id.assert_called_once_with(config_id)
#     assert result == mock_config
#
# @pytest.mark.asyncio
# async def test_get_agent_config_by_id_not_found(agent_config_service, mock_repository):
#     # Setup
#     config_id = str(uuid4())
#     mock_repository.get_by_id.return_value = None
#
#     # Execute
#     result = await agent_config_service.get_by_id(config_id)
#
#     # Assert
#     mock_repository.get_by_id.assert_called_once_with(config_id)
#     assert result is None
#
# @pytest.mark.asyncio
# async def test_create_agent_config_success(agent_config_service, mock_repository, sample_agent_config_data):
#     # Setup
#     agent_config = AgentConfig(**sample_agent_config_data)
#     mock_result = MagicMock()
#     for key, value in sample_agent_config_data.items():
#         setattr(mock_result, key, value)
#     mock_repository.create.return_value = mock_result
#
#     # Execute
#     result = await agent_config_service.create(agent_config)
#
#     # Assert
#     mock_repository.create.assert_called_once_with(agent_config)
#     assert result.id == sample_agent_config_data["id"]
#     assert result.name == sample_agent_config_data["name"]
#     assert result.description == sample_agent_config_data["description"]
#     assert result.provider == sample_agent_config_data["provider"]
#     assert result.model == sample_agent_config_data["model"]
#     assert result.system_prompt == sample_agent_config_data["system_prompt"]
#
# @pytest.mark.asyncio
# async def test_update_agent_config_success(agent_config_service, mock_repository, sample_agent_config_data):
#     # Setup
#     config_id = sample_agent_config_data["id"]
#     updated_data = sample_agent_config_data.copy()
#     updated_data["name"] = "updated_agent"
#     updated_data["description"] = "Updated description"
#     updated_data["system_prompt"] = "Updated system prompt"
#     updated_data["is_active"] = False
#
#     agent_config = AgentConfig(**updated_data)
#     mock_result = MagicMock()
#     for key, value in updated_data.items():
#         setattr(mock_result, key, value)
#     mock_repository.update.return_value = mock_result
#
#     # Execute
#     result = await agent_config_service.update(config_id, agent_config)
#
#     # Assert
#     mock_repository.update.assert_called_once_with(config_id, agent_config)
#     assert result.id == config_id
#     assert result.name == updated_data["name"]
#     assert result.description == updated_data["description"]
#     assert result.system_prompt == updated_data["system_prompt"]
#     assert result.is_active == updated_data["is_active"]
#
# @pytest.mark.asyncio
# async def test_delete_agent_config_success(agent_config_service, mock_repository):
#     # Setup
#     config_id = str(uuid4())
#     mock_repository.delete.return_value = True
#
#     # Execute
#     result = await agent_config_service.delete(config_id)
#
#     # Assert
#     mock_repository.delete.assert_called_once_with(config_id)
#     assert result is True