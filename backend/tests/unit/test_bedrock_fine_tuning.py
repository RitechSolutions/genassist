"""
Unit tests for Bedrock (Amazon Nova) fine-tuning functionality.

boto3 is stubbed, so these run without any AWS access.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.bedrock_fine_tuning import (
    BedrockFineTuningService,
    NOVA_FINE_TUNABLE_MODELS,
    NOVA_SCHEMA_VERSION,
)
from app.repositories.bedrock_fine_tuning import BedrockFineTuningRepository
from app.services.open_ai_fine_tuning import OpenAIFineTuningService
from app.services.app_settings import AppSettingsService
from app.schemas.bedrock_fine_tuning import CreateBedrockFineTuningJobRequest
from app.core.utils.enums.bedrock_fine_tuning_enum import BedrockJobStatus
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.config.settings import file_storage_settings


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=BedrockFineTuningRepository)


@pytest.fixture
def mock_openai_service():
    return MagicMock(spec=OpenAIFineTuningService)


@pytest.fixture
def mock_app_settings_service():
    svc = AsyncMock(spec=AppSettingsService)
    # Default: no override row present -> service falls back to the code default.
    svc.get_by_type_and_name.return_value = None
    return svc


@pytest.fixture
def bedrock_service(mock_repository, mock_openai_service, mock_app_settings_service):
    """BedrockFineTuningService with mocked boto3 clients + config."""
    original_role = file_storage_settings.BEDROCK_FINE_TUNING_ROLE_ARN
    file_storage_settings.BEDROCK_FINE_TUNING_ROLE_ARN = "arn:aws:iam::123:role/ft"

    service = BedrockFineTuningService(
        repository=mock_repository,
        openai_service=mock_openai_service,
        app_settings_service=mock_app_settings_service,
    )
    service.bucket = "test-bucket"
    service._bedrock_client = MagicMock()
    service._s3_client = MagicMock()
    try:
        yield service
    finally:
        file_storage_settings.BEDROCK_FINE_TUNING_ROLE_ARN = original_role


@pytest.mark.asyncio
async def test_get_fine_tunable_models_fallback(bedrock_service):
    """No App Settings override row -> returns the code default."""
    result = await bedrock_service.get_fine_tunable_models()
    assert result == NOVA_FINE_TUNABLE_MODELS
    assert all("nova" in m for m in NOVA_FINE_TUNABLE_MODELS)


@pytest.mark.asyncio
async def test_get_fine_tunable_models_db_override(bedrock_service, mock_app_settings_service):
    """App Settings row overrides the default list without a deploy."""
    override = MagicMock()
    override.values = {"models": ["amazon.nova-pro-v1:0:300k", "amazon.nova-new-v1:0"]}
    mock_app_settings_service.get_by_type_and_name.return_value = override

    result = await bedrock_service.get_fine_tunable_models()

    assert result == ["amazon.nova-pro-v1:0:300k", "amazon.nova-new-v1:0"]
    mock_app_settings_service.get_by_type_and_name.assert_awaited_once_with(
        "Other", "BedrockFineTunableModels"
    )


@pytest.mark.asyncio
async def test_get_fine_tunable_models_malformed_falls_back(bedrock_service, mock_app_settings_service):
    """A row with no/empty models list falls back to the default."""
    override = MagicMock()
    override.values = {"models": []}
    mock_app_settings_service.get_by_type_and_name.return_value = override

    result = await bedrock_service.get_fine_tunable_models()
    assert result == NOVA_FINE_TUNABLE_MODELS


@pytest.mark.asyncio
async def test_upload_training_data_success(bedrock_service):
    s3_uri = await bedrock_service.upload_training_data(b'{"a": 1}', "train.jsonl")

    assert s3_uri.startswith("s3://test-bucket/bedrock-fine-tuning/training/")
    assert s3_uri.endswith("-train.jsonl")
    bedrock_service._s3_client.put_object.assert_called_once()
    kwargs = bedrock_service._s3_client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Body"] == b'{"a": 1}'


@pytest.mark.asyncio
async def test_upload_training_data_not_configured(bedrock_service):
    bedrock_service.bucket = None
    with pytest.raises(AppException) as exc:
        await bedrock_service.upload_training_data(b"x", "t.jsonl")
    assert exc.value.error_key == ErrorKey.ERROR_BEDROCK_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_create_fine_tuning_job_success(bedrock_service, mock_repository):
    bedrock_service._bedrock_client.create_model_customization_job = MagicMock(
        return_value={"jobArn": "arn:aws:bedrock:us-east-1:123:model-customization-job/abc"}
    )
    mock_repository.create_job_record.return_value = MagicMock()

    request = CreateBedrockFineTuningJobRequest(
        training_data_s3_uri="s3://test-bucket/train.jsonl",
        base_model_id="amazon.nova-micro-v1:0:128k",
        hyperparameters={"epochCount": 2},
        suffix="support",
    )
    await bedrock_service.create_fine_tuning_job(request)

    call = bedrock_service._bedrock_client.create_model_customization_job.call_args.kwargs
    assert call["baseModelIdentifier"] == "amazon.nova-micro-v1:0:128k"
    assert call["customizationType"] == "FINE_TUNING"
    assert call["roleArn"] == "arn:aws:iam::123:role/ft"
    assert call["trainingDataConfig"] == {"s3Uri": "s3://test-bucket/train.jsonl"}
    # Hyperparameters must be stringified for Bedrock
    assert call["hyperParameters"] == {"epochCount": "2"}

    saved = mock_repository.create_job_record.call_args.kwargs
    assert saved["status"] == BedrockJobStatus.IN_PROGRESS
    assert saved["base_model_id"] == "amazon.nova-micro-v1:0:128k"


@pytest.mark.asyncio
async def test_create_fine_tuning_job_not_configured(bedrock_service):
    bedrock_service.bucket = None
    request = CreateBedrockFineTuningJobRequest(
        training_data_s3_uri="s3://x/y.jsonl",
        base_model_id="amazon.nova-micro-v1:0:128k",
    )
    with pytest.raises(AppException) as exc:
        await bedrock_service.create_fine_tuning_job(request)
    assert exc.value.error_key == ErrorKey.ERROR_BEDROCK_NOT_CONFIGURED


def test_build_nova_jsonl_entry_format(bedrock_service):
    import json

    agent_msg = MagicMock()
    agent_msg.id = "m2"
    agent_msg.sequence_number = 2
    user_msg = MagicMock()
    user_msg.id = "m1"
    user_msg.sequence_number = 1
    user_msg.speaker = "customer"
    user_msg.text = "How do I reset my password?"

    log = MagicMock()
    log.transcript_message_id = "m2"
    log.raw_response = json.dumps({"row_agent_response": {"output": "Click 'Forgot password'."}})

    entry = bedrock_service._build_nova_jsonl_entry(
        log, [user_msg, agent_msg], "You are a support agent."
    )

    assert entry["schemaVersion"] == NOVA_SCHEMA_VERSION
    assert entry["system"] == [{"text": "You are a support agent."}]
    assert entry["messages"][0] == {"role": "user", "content": [{"text": "How do I reset my password?"}]}
    assert entry["messages"][1] == {"role": "assistant", "content": [{"text": "Click 'Forgot password'."}]}


def test_build_nova_jsonl_entry_skips_when_no_output(bedrock_service):
    import json

    agent_msg = MagicMock()
    agent_msg.id = "m2"
    agent_msg.sequence_number = 2
    log = MagicMock()
    log.transcript_message_id = "m2"
    log.raw_response = json.dumps({"row_agent_response": {"output": ""}})

    assert bedrock_service._build_nova_jsonl_entry(log, [agent_msg], "sys") is None
