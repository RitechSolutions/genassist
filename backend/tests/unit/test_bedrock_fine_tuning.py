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
from app.core.utils.enums.bedrock_fine_tuning_enum import (
    BedrockDeploymentStatus,
    BedrockJobStatus,
)
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

    # Tenant context defaults to "master" in tests; training data must live under
    # the tenant's prefix or job creation is rejected.
    training_uri = "s3://test-bucket/bedrock-fine-tuning/training/master/train.jsonl"
    request = CreateBedrockFineTuningJobRequest(
        training_data_s3_uri=training_uri,
        base_model_id="amazon.nova-micro-v1:0:128k",
        hyperparameters={"epochCount": 2},
        suffix="support",
    )
    await bedrock_service.create_fine_tuning_job(request)

    call = bedrock_service._bedrock_client.create_model_customization_job.call_args.kwargs
    assert call["baseModelIdentifier"] == "amazon.nova-micro-v1:0:128k"
    assert call["customizationType"] == "FINE_TUNING"
    assert call["roleArn"] == "arn:aws:iam::123:role/ft"
    assert call["trainingDataConfig"] == {"s3Uri": training_uri}
    # Nova defaults are always sent (Bedrock requires hyperParameters), with the
    # user's value overriding the corresponding default; all values stringified.
    assert call["hyperParameters"] == {
        "epochCount": "1",
        "learningRate": "0.00001",
        "learningRateWarmupSteps": "10",
    }

    saved = mock_repository.create_job_record.call_args.kwargs
    assert saved["status"] == BedrockJobStatus.IN_PROGRESS
    assert saved["base_model_id"] == "amazon.nova-micro-v1:0:128k"


@pytest.mark.asyncio
async def test_create_fine_tuning_job_sends_default_hyperparameters(bedrock_service, mock_repository):
    """No hyperparameters supplied -> Nova defaults are still sent (Bedrock requires them)."""
    bedrock_service._bedrock_client.create_model_customization_job = MagicMock(
        return_value={"jobArn": "arn:aws:bedrock:us-east-1:123:model-customization-job/abc"}
    )
    mock_repository.create_job_record.return_value = MagicMock()

    request = CreateBedrockFineTuningJobRequest(
        training_data_s3_uri="s3://test-bucket/bedrock-fine-tuning/training/master/t.jsonl",
        base_model_id="amazon.nova-micro-v1:0:128k",
    )
    await bedrock_service.create_fine_tuning_job(request)

    call = bedrock_service._bedrock_client.create_model_customization_job.call_args.kwargs
    assert call["hyperParameters"] == {
        "epochCount": "2",
        "learningRate": "0.00001",
        "learningRateWarmupSteps": "10",
    }


@pytest.mark.asyncio
async def test_create_fine_tuning_job_rejects_foreign_s3_uri(bedrock_service):
    """A training URI outside the tenant's prefix must be rejected (cross-tenant guard)."""
    request = CreateBedrockFineTuningJobRequest(
        training_data_s3_uri="s3://test-bucket/bedrock-fine-tuning/training/other-tenant/x.jsonl",
        base_model_id="amazon.nova-micro-v1:0:128k",
    )
    with pytest.raises(AppException) as exc:
        await bedrock_service.create_fine_tuning_job(request)
    assert exc.value.error_key == ErrorKey.ERROR_BEDROCK_TRAINING_DATA_FORBIDDEN
    bedrock_service._bedrock_client.create_model_customization_job.assert_not_called()


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


@pytest.mark.asyncio
async def test_sync_deployment_active(bedrock_service, mock_repository):
    job = MagicMock()
    job.id = "job-1"
    job.deployment_arn = "arn:aws:bedrock:us-east-1:123:custom-model-deployment/x"
    bedrock_service._bedrock_client.get_custom_model_deployment = MagicMock(
        return_value={"status": "Active"}
    )

    await bedrock_service._sync_deployment(job)

    kwargs = mock_repository.update_deployment.call_args.kwargs
    assert kwargs["deployment_status"] == BedrockDeploymentStatus.ACTIVE
    assert kwargs["failure_message"] is None


@pytest.mark.asyncio
async def test_sync_deployment_failed_captures_message(bedrock_service, mock_repository):
    job = MagicMock()
    job.id = "job-1"
    job.deployment_arn = "arn:aws:bedrock:us-east-1:123:custom-model-deployment/x"
    bedrock_service._bedrock_client.get_custom_model_deployment = MagicMock(
        return_value={"status": "Failed", "failureMessage": "insufficient capacity"}
    )

    await bedrock_service._sync_deployment(job)

    kwargs = mock_repository.update_deployment.call_args.kwargs
    assert kwargs["deployment_status"] == BedrockDeploymentStatus.FAILED
    assert kwargs["failure_message"] == "insufficient capacity"


@pytest.mark.asyncio
async def test_sync_deployment_noop_without_arn(bedrock_service, mock_repository):
    job = MagicMock()
    job.deployment_arn = None
    bedrock_service._bedrock_client.get_custom_model_deployment = MagicMock()

    result = await bedrock_service._sync_deployment(job)

    assert result is job
    bedrock_service._bedrock_client.get_custom_model_deployment.assert_not_called()
    mock_repository.update_deployment.assert_not_awaited()


@pytest.mark.asyncio
async def test_undeploy_custom_model_success(bedrock_service, mock_repository):
    job = MagicMock()
    job.id = "job-1"
    job.deployment_arn = "arn:aws:bedrock:us-east-1:123:custom-model-deployment/x"
    mock_repository.get_job_by_id.return_value = job
    bedrock_service._bedrock_client.delete_custom_model_deployment = MagicMock()

    await bedrock_service.undeploy_custom_model("job-1")

    bedrock_service._bedrock_client.delete_custom_model_deployment.assert_called_once_with(
        customModelDeploymentIdentifier=job.deployment_arn
    )
    mock_repository.clear_deployment.assert_awaited_once_with(id=job.id)


@pytest.mark.asyncio
async def test_undeploy_custom_model_without_deployment_raises(bedrock_service, mock_repository):
    job = MagicMock()
    job.id = "job-1"
    job.deployment_arn = None
    mock_repository.get_job_by_id.return_value = job
    bedrock_service._bedrock_client.delete_custom_model_deployment = MagicMock()

    with pytest.raises(AppException) as exc:
        await bedrock_service.undeploy_custom_model("job-1")

    assert exc.value.error_key == ErrorKey.ERROR_UNDEPLOY_MODEL_BEDROCK
    bedrock_service._bedrock_client.delete_custom_model_deployment.assert_not_called()
    mock_repository.clear_deployment.assert_not_awaited()


def test_build_nova_jsonl_entry_skips_when_no_output(bedrock_service):
    import json

    agent_msg = MagicMock()
    agent_msg.id = "m2"
    agent_msg.sequence_number = 2
    log = MagicMock()
    log.transcript_message_id = "m2"
    log.raw_response = json.dumps({"row_agent_response": {"output": ""}})

    assert bedrock_service._build_nova_jsonl_entry(log, [agent_msg], "sys") is None


@pytest.mark.asyncio
async def test_list_training_files(bedrock_service):
    from datetime import datetime, timezone

    # Listing is scoped to the current tenant's prefix ("master" in tests).
    tenant_prefix = "bedrock-fine-tuning/training/master/"
    bedrock_service._s3_client.list_objects_v2 = MagicMock(
        return_value={
            "Contents": [
                {
                    "Key": tenant_prefix,  # prefix "folder" -> skipped
                    "Size": 0,
                    "LastModified": datetime(2026, 7, 1, tzinfo=timezone.utc),
                },
                {
                    "Key": f"{tenant_prefix}aaa-older.jsonl",
                    "Size": 2048,
                    "LastModified": datetime(2026, 7, 10, tzinfo=timezone.utc),
                },
                {
                    "Key": f"{tenant_prefix}bbb-newer.jsonl",
                    "Size": 4096,
                    "LastModified": datetime(2026, 7, 12, tzinfo=timezone.utc),
                },
            ]
        }
    )

    files = await bedrock_service.list_training_files()

    # Prefix "folder" entry is dropped; newest first.
    assert [f["filename"] for f in files] == ["bbb-newer.jsonl", "aaa-older.jsonl"]
    assert files[0]["s3_uri"] == f"s3://test-bucket/{tenant_prefix}bbb-newer.jsonl"
    assert files[0]["size"] == 4096
    bedrock_service._s3_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix=tenant_prefix
    )


def _nova_msg(msg_id, seq, speaker, text):
    m = MagicMock()
    m.id = msg_id
    m.sequence_number = seq
    m.speaker = speaker
    m.text = text
    return m


def _nova_log(transcript_message_id, output):
    log = MagicMock()
    log.transcript_message_id = transcript_message_id
    log._output = output
    return log


def test_build_nova_memory_jsonl_entry_multi_turn(bedrock_service):
    # The memory builder reads the assistant text via the OpenAI service helper.
    bedrock_service.openai_service._extract_steps_and_output = (
        lambda log: ([], log._output)
    )
    messages = [
        _nova_msg("m1", 1, "customer", "What's the return policy?"),
        _nova_msg("m2", 2, "agent", "30 days."),
        _nova_msg("m3", 3, "customer", "And last week's order?"),
        _nova_msg("m4", 4, "agent", "Still within 30 days."),
    ]
    logs = [_nova_log("m2", "30 days."), _nova_log("m4", "Still within 30 days.")]

    entry = bedrock_service._build_nova_memory_jsonl_entry(messages, logs, "You are helpful.")

    assert entry["schemaVersion"] == NOVA_SCHEMA_VERSION
    assert entry["system"] == [{"text": "You are helpful."}]
    roles = [m["role"] for m in entry["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert entry["messages"][2]["content"] == [{"text": "And last week's order?"}]
    assert entry["messages"][3]["content"] == [{"text": "Still within 30 days."}]


def test_build_nova_memory_jsonl_entry_merges_consecutive_and_trims(bedrock_service):
    # Nova needs strict alternation starting with user; consecutive same-role turns
    # are merged, and a trailing user turn (no answer after it) is dropped.
    bedrock_service.openai_service._extract_steps_and_output = (
        lambda log: ([], log._output)
    )
    messages = [
        _nova_msg("m1", 1, "customer", "Hi"),
        _nova_msg("m2", 2, "customer", "are you there?"),
        _nova_msg("m3", 3, "agent", "Yes!"),
        _nova_msg("m4", 4, "customer", "great, one more thing"),  # trailing user, trimmed
    ]
    logs = [_nova_log("m3", "Yes!")]

    entry = bedrock_service._build_nova_memory_jsonl_entry(messages, logs, "")

    assert "system" not in entry
    roles = [m["role"] for m in entry["messages"]]
    assert roles == ["user", "assistant"]
    assert entry["messages"][0]["content"] == [{"text": "Hi\nare you there?"}]
