"""S3 data sources work without an access key and secret key, using the server's AWS role."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config.settings import settings
from app.core.utils.s3_utils import (
    ONLY_ONE_KEY,
    SERVER_ROLE_NOT_ALLOWED,
    OnlyOneS3KeyError,
    S3Client,
    ServerRoleNotAllowedError,
    build_s3_client,
    s3_data_source_keys,
)
from app.schemas.datasource import DataSourceUpdate
from app.schemas.dynamic_form_schemas.data_source_schemas import DATA_SOURCE_SCHEMAS, s3_key_fields
from app.services.datasources import DataSourceService
from app.tasks import audio_tasks, kb_batch_tasks, s3_tasks

REGION = "us-east-1"
BUCKET = "acme-recordings"
KEY_SETTINGS = ("aws_access_key_id", "aws_secret_access_key", "aws_session_token")


def _client_settings(boto3_client: MagicMock) -> dict:
    return boto3_client.call_args.kwargs


def _fake_injector(**services):
    return SimpleNamespace(get=lambda service_class: services[service_class.__name__])


@pytest.fixture
def server_role_allowed():
    with patch.object(settings, "S3_DATA_SOURCES_USE_SERVER_ROLE", True):
        yield


@pytest.fixture
def server_role_not_allowed():
    with patch.object(settings, "S3_DATA_SOURCES_USE_SERVER_ROLE", False):
        yield


@pytest.mark.parametrize("empty", ["", None])
def test_empty_keys_are_left_out_so_the_server_role_is_used(empty):
    with patch("app.core.utils.s3_utils.boto3.client") as boto3_client:
        build_s3_client(empty, empty, REGION, empty)

    settings = _client_settings(boto3_client)
    assert not any(name in settings for name in KEY_SETTINGS)
    assert settings == {"region_name": REGION}


def test_typed_keys_are_still_sent():
    with patch("app.core.utils.s3_utils.boto3.client") as boto3_client:
        S3Client(BUCKET, "AKIAEXAMPLE", "example-secret", REGION)

    assert _client_settings(boto3_client) == {
        "region_name": REGION,
        "aws_access_key_id": "AKIAEXAMPLE",
        "aws_secret_access_key": "example-secret",
    }


def test_form_keys_are_optional_only_when_the_server_allows_its_own_access():
    allowed = {field.name: field.required for field in s3_key_fields(use_server_role=True)}
    not_allowed = {field.name: field.required for field in s3_key_fields(use_server_role=False)}

    assert allowed == {"access_key": False, "secret_key": False}
    assert not_allowed == {"access_key": True, "secret_key": True}


def test_form_by_default_requires_the_keys_as_before():
    fields = {field.name: field for field in DATA_SOURCE_SCHEMAS["S3"].fields}

    assert fields["access_key"].required and fields["access_key"].description == "Enter access key"
    assert fields["secret_key"].required and fields["secret_key"].description == "Enter secret key"


@pytest.mark.parametrize("connection_data", [{}, {"access_key": "", "secret_key": ""}])
def test_no_keys_are_refused_when_the_server_does_not_allow_its_own_access(server_role_not_allowed, connection_data):
    with pytest.raises(ServerRoleNotAllowedError):
        s3_data_source_keys(connection_data)


@pytest.mark.parametrize("connection_data", [{}, {"access_key": "", "secret_key": ""}])
def test_no_keys_mean_the_server_access_when_allowed(server_role_allowed, connection_data):
    assert s3_data_source_keys(connection_data) == (None, None)


def test_typed_keys_are_used_whatever_the_setting(server_role_not_allowed):
    assert s3_data_source_keys({"access_key": "AKIAEXAMPLE", "secret_key": "example-secret"}) == (
        "AKIAEXAMPLE",
        "example-secret",
    )


def test_test_connection_without_keys_explains_the_refusal(server_role_not_allowed):
    with patch("app.core.utils.s3_utils.boto3.client") as boto3_client:
        with pytest.raises(ServerRoleNotAllowedError, match="Enter the access key and secret key"):
            S3Client.test_connection({"bucket_name": BUCKET, "region": REGION, "access_key": "", "secret_key": ""})

    boto3_client.assert_not_called()


@pytest.mark.asyncio
async def test_sync_now_listing_with_empty_keys_uses_the_server_role():
    listed = {"Contents": [{"Key": "docs/a.txt", "Size": 4, "LastModified": datetime.now(timezone.utc)}]}
    with patch("app.core.utils.s3_utils.boto3.client") as boto3_client:
        boto3_client.return_value.list_objects_v2.return_value = listed
        result = await kb_batch_tasks.s3_list_source(api_key="", api_secret="", region=REGION, bucket_name=BUCKET, prefix="docs")

    assert [file["key"] for file in result["files"]] == ["docs/a.txt"]
    assert _client_settings(boto3_client) == {"region_name": REGION}


@pytest.mark.asyncio
async def test_sync_now_download_and_move_with_empty_keys_use_the_server_role():
    with patch("app.core.utils.s3_utils.boto3.client") as boto3_client:
        boto3_client.return_value.head_object.return_value = {"ContentLength": 4, "LastModified": datetime.now(timezone.utc)}
        await kb_batch_tasks.s3_download_file(api_key="", api_secret="", region=REGION, bucket_name=BUCKET, item="docs/a.txt")
        await kb_batch_tasks.s3_move_file(
            api_key="", api_secret="", region=REGION, bucket_name=BUCKET, item="docs/a.txt", destination="output/a.txt"
        )

    assert [call.kwargs for call in boto3_client.call_args_list] == [{"region_name": REGION}] * 2


def _data_source_without_keys(prefix: str):
    connection_data = {"region": REGION, "bucket_name": BUCKET, "prefix": prefix}
    return SimpleNamespace(id=uuid.uuid4(), name="Acme", source_type="S3", is_active=1, connection_data=connection_data)


def _s3_client_listing_nothing() -> MagicMock:
    s3_client_class = MagicMock()
    s3_client_class.return_value.list_files.return_value = {"files": []}
    return s3_client_class


def _scheduled_sync_services(data_source):
    kb = SimpleNamespace(
        id=uuid.uuid4(), name="Acme KB", sync_source_id=data_source.id, sync_schedule="* * * * *",
        last_synced=None, last_file_date=None,
    )
    services = _fake_injector(
        KnowledgeBaseService=SimpleNamespace(get_by_id=AsyncMock(return_value=kb), update=AsyncMock()),
        AgentRAGServiceManager=SimpleNamespace(get_document_ids=AsyncMock(return_value=[])),
        DataSourceService=SimpleNamespace(get_by_id=AsyncMock(return_value=data_source)),
    )
    return kb, services


@pytest.mark.asyncio
async def test_scheduled_sync_runs_when_the_keys_were_cleared(server_role_allowed):
    data_source = _data_source_without_keys("docs")
    kb, services = _scheduled_sync_services(data_source)
    s3_client_class = _s3_client_listing_nothing()

    with patch.object(s3_tasks, "injector", services), patch.object(s3_tasks, "S3Client", s3_client_class), \
            patch.object(s3_tasks, "KBCreate", lambda **fields: fields):
        result = await s3_tasks.import_s3_files_to_kb_async(kb_id=kb.id)

    assert result["datasources_processed"] == 1
    sent = s3_client_class.call_args.kwargs
    assert sent["aws_access_key_id"] is None and sent["aws_secret_access_key"] is None


@pytest.mark.asyncio
async def test_scheduled_sync_reports_a_refused_knowledge_base(server_role_not_allowed):
    data_source = _data_source_without_keys("docs")
    kb, services = _scheduled_sync_services(data_source)
    s3_client_class = _s3_client_listing_nothing()

    with patch.object(s3_tasks, "injector", services), patch.object(s3_tasks, "S3Client", s3_client_class):
        result = await s3_tasks.import_s3_files_to_kb_async(kb_id=kb.id)

    assert result["kbs_failed"] == 1
    assert result["errors"] == [f"Acme KB: {SERVER_ROLE_NOT_ALLOWED}"]
    s3_client_class.assert_not_called()


@pytest.mark.asyncio
async def test_transcription_skips_a_refused_data_source(server_role_not_allowed):
    data_source = _data_source_without_keys("audio")
    services = _fake_injector(
        DataSourceService=SimpleNamespace(get_by_id=AsyncMock(return_value=data_source)),
        AudioService=SimpleNamespace(),
    )
    s3_client_class = _s3_client_listing_nothing()

    with patch.object(audio_tasks, "injector", services), patch.object(audio_tasks, "S3Client", s3_client_class):
        await audio_tasks.transcribe_audio_files_async(ds_id=str(data_source.id))

    s3_client_class.assert_not_called()


@pytest.mark.asyncio
async def test_transcription_runs_when_the_keys_were_cleared(server_role_allowed):
    data_source = _data_source_without_keys("audio")
    services = _fake_injector(
        DataSourceService=SimpleNamespace(get_by_id=AsyncMock(return_value=data_source)),
        AudioService=SimpleNamespace(),
    )
    s3_client_class = _s3_client_listing_nothing()

    with patch.object(audio_tasks, "injector", services), patch.object(audio_tasks, "S3Client", s3_client_class):
        await audio_tasks.transcribe_audio_files_async(ds_id=str(data_source.id))

    s3_client_class.return_value.list_files.assert_called_once_with(prefix="audio")
    sent = s3_client_class.call_args.kwargs
    assert sent["aws_access_key_id"] is None and sent["aws_secret_access_key"] is None


async def _run_sync_now(data_source):
    kb = SimpleNamespace(
        id=uuid.uuid4(), name="Acme KB", type="s3", sync_source_id=data_source.id, sync_schedule=None,
        extra_metadata={}, rag_config={}, processing_filter=None,
    )
    kb_service = MagicMock()
    kb_service.get_by_id = AsyncMock(return_value=kb)
    ds_service = MagicMock()
    ds_service.get_by_id = AsyncMock(return_value=data_source)
    services = {kb_batch_tasks.KnowledgeBaseService: kb_service, kb_batch_tasks.DataSourceService: ds_service}
    list_source = AsyncMock()

    with patch.object(kb_batch_tasks, "injector") as fake_injector, patch.object(kb_batch_tasks, "s3_list_source", list_source):
        fake_injector.get.side_effect = lambda dependency: services.get(dependency, MagicMock())
        result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=str(kb.id))
    return result, list_source


@pytest.mark.asyncio
async def test_sync_now_shows_why_a_knowledge_base_without_keys_was_refused(server_role_not_allowed):
    result, list_source = await _run_sync_now(_data_source_without_keys("docs"))

    assert result["status"] == "error"
    assert result["message"] == SERVER_ROLE_NOT_ALLOWED
    list_source.assert_not_called()


def _data_source_with_only_the_access_key(prefix: str):
    data_source = _data_source_without_keys(prefix)
    data_source.connection_data["access_key"] = "AKIAEXAMPLE"
    return data_source


ONLY_ONE_KEY_CONNECTIONS = [{"access_key": "AKIAEXAMPLE"}, {"secret_key": "example-secret", "access_key": ""}]


@pytest.mark.parametrize("connection_data", ONLY_ONE_KEY_CONNECTIONS)
def test_only_one_key_asks_for_both_or_neither_when_the_server_access_is_allowed(server_role_allowed, connection_data):
    with pytest.raises(OnlyOneS3KeyError, match=ONLY_ONE_KEY):
        s3_data_source_keys(connection_data)


@pytest.mark.parametrize("connection_data", ONLY_ONE_KEY_CONNECTIONS)
def test_only_one_key_asks_for_both_keys_when_the_server_access_is_not_allowed(server_role_not_allowed, connection_data):
    with pytest.raises(ServerRoleNotAllowedError, match=SERVER_ROLE_NOT_ALLOWED):
        s3_data_source_keys(connection_data)


def test_test_connection_with_only_one_key_explains_the_refusal(server_role_allowed):
    connection_data = {"bucket_name": BUCKET, "region": REGION, "access_key": "AKIAEXAMPLE", "secret_key": ""}
    with patch("app.core.utils.s3_utils.boto3.client") as boto3_client:
        with pytest.raises(OnlyOneS3KeyError, match=ONLY_ONE_KEY):
            S3Client.test_connection(connection_data)

    boto3_client.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_sync_reports_a_knowledge_base_with_only_one_key(server_role_allowed):
    kb, services = _scheduled_sync_services(_data_source_with_only_the_access_key("docs"))
    s3_client_class = _s3_client_listing_nothing()

    with patch.object(s3_tasks, "injector", services), patch.object(s3_tasks, "S3Client", s3_client_class):
        result = await s3_tasks.import_s3_files_to_kb_async(kb_id=kb.id)

    assert result["kbs_failed"] == 1
    assert result["errors"] == [f"Acme KB: {ONLY_ONE_KEY}"]
    s3_client_class.assert_not_called()


@pytest.mark.asyncio
async def test_transcription_skips_a_data_source_with_only_one_key(server_role_allowed):
    data_source = _data_source_with_only_the_access_key("audio")
    services = _fake_injector(
        DataSourceService=SimpleNamespace(get_by_id=AsyncMock(return_value=data_source)),
        AudioService=SimpleNamespace(),
    )
    s3_client_class = _s3_client_listing_nothing()

    with patch.object(audio_tasks, "injector", services), patch.object(audio_tasks, "S3Client", s3_client_class):
        await audio_tasks.transcribe_audio_files_async(ds_id=str(data_source.id))

    s3_client_class.assert_not_called()


@pytest.mark.asyncio
async def test_sync_now_shows_why_a_knowledge_base_with_only_one_key_was_refused(server_role_allowed):
    result, list_source = await _run_sync_now(_data_source_with_only_the_access_key("docs"))

    assert result["status"] == "error"
    assert result["message"] == ONLY_ONE_KEY
    list_source.assert_not_called()


class _DataSourceRepository:
    def __init__(self, stored):
        self.stored = stored

    async def get_by_id(self, _datasource_id):
        return self.stored

    async def update(self, _datasource_id, update_data):
        for field, value in update_data.items():
            setattr(self.stored, field, value)
        return self.stored


@pytest.mark.asyncio
async def test_clearing_the_keys_resets_a_connected_status():
    stored = SimpleNamespace(
        connection_data={"access_key": "ENC-key", "secret_key": "ENC-secret", "region": REGION, "bucket_name": BUCKET},
        connection_status={"status": "Connected", "last_tested_at": "2026-11-17T10:00:00", "message": "ok"},
    )
    cleared = {"access_key": "", "secret_key": "", "region": REGION, "bucket_name": BUCKET}

    await DataSourceService(_DataSourceRepository(stored)).update(uuid.uuid4(), DataSourceUpdate(connection_data=cleared))

    assert "access_key" not in stored.connection_data and "secret_key" not in stored.connection_data
    assert stored.connection_status["status"] == "Untested"


@pytest.mark.asyncio
async def test_saving_unchanged_keys_keeps_the_status():
    connection = {"access_key": "ENC-key", "secret_key": "ENC-secret", "region": REGION, "bucket_name": BUCKET}
    connected = {"status": "Connected", "last_tested_at": "2026-11-17T10:00:00", "message": "ok"}
    stored = SimpleNamespace(connection_data=dict(connection), connection_status=dict(connected))

    await DataSourceService(_DataSourceRepository(stored)).update(uuid.uuid4(), DataSourceUpdate(connection_data=dict(connection)))

    assert stored.connection_status == connected
