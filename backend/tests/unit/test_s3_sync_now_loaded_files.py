"""Sync Now on an S3 knowledge base loads only new or changed files and names them like the scheduled sync."""

import copy
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.data.s3_loaded_files import (
    LOADED_FILES_KEY,
    LoadedFiles,
    document_id,
    file_version,
    only_vector_store_enabled,
    replaced_document_id,
)

FIRST_UPLOAD = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
LATER_UPLOAD = FIRST_UPLOAD + timedelta(hours=1)
KB_ID = "kb-1"
VECTOR_ONLY = {"enabled": True, "vector": {"enabled": True, "chunk_size": 1000}}
VECTOR_WITH_OTHER_CHUNKS = {"enabled": True, "vector": {"enabled": True, "chunk_size": 500}}
VECTOR_AND_LEGRA = {"enabled": True, "vector": {"enabled": True}, "legra": {"enabled": True}}


def _listed(key, modified_at=FIRST_UPLOAD, size=4, etag=None):
    return {"key": key, "size": size, "last_modified": modified_at, "etag": etag}


def _loaded_files(listed_file, processing_mode="none", stored=True, recorded=True):
    stored_ids = [document_id(KB_ID, listed_file["key"])] if stored else []
    versions = {listed_file["key"]: file_version(listed_file, processing_mode)} if recorded else {}
    return LoadedFiles(KB_ID, stored_ids, versions, processing_mode)


def test_document_id_keeps_the_folder():
    assert document_id(KB_ID, "docs/2026/a.pdf") == "KB:kb-1#docs/2026/a.pdf"


def test_file_is_current_when_stored_and_unchanged():
    listed_file = _listed("docs/a.txt", etag='"abc"')

    assert _loaded_files(listed_file).is_current(listed_file)


@pytest.mark.parametrize(
    "changed_file",
    [
        _listed("docs/a.txt", modified_at=LATER_UPLOAD, etag='"abc"'),
        _listed("docs/a.txt", size=9, etag='"abc"'),
        _listed("docs/a.txt", etag='"def"'),
    ],
    ids=["modified later", "other size", "other content tag"],
)
def test_file_is_not_current_after_it_changed(changed_file):
    assert not _loaded_files(_listed("docs/a.txt", etag='"abc"')).is_current(changed_file)


def test_file_is_not_current_when_the_knowledge_base_does_not_hold_it():
    listed_file = _listed("docs/a.txt")

    assert not _loaded_files(listed_file, stored=False).is_current(listed_file)


def test_file_is_not_current_without_a_recorded_version():
    listed_file = _listed("docs/a.txt")

    assert not _loaded_files(listed_file, recorded=False).is_current(listed_file)


def test_file_is_not_current_after_the_processing_mode_changed():
    listed_file = _listed("docs/a.txt")
    loaded_with_another_mode = LoadedFiles(
        KB_ID, [document_id(KB_ID, "docs/a.txt")], {"docs/a.txt": file_version(listed_file, "none")}, "extract"
    )

    assert not loaded_with_another_mode.is_current(listed_file)


def test_file_without_a_modified_date_is_never_current():
    undated_file = {"key": "docs/a.txt", "size": 4}
    loaded_files = LoadedFiles(KB_ID, [document_id(KB_ID, "docs/a.txt")], {"docs/a.txt": "None|4|None|none"}, "none")
    loaded_files.remember(undated_file)

    assert not loaded_files.is_current(undated_file)
    assert loaded_files.versions_of([undated_file]) == {}


def test_versions_drop_files_gone_from_the_folder():
    kept, gone = _listed("docs/kept.txt"), _listed("docs/gone.txt")
    loaded_files = LoadedFiles(KB_ID, [], {}, "none")
    loaded_files.remember(kept)
    loaded_files.remember(gone)

    assert loaded_files.versions_of([kept]) == {"docs/kept.txt": file_version(kept, "none")}


def test_forgotten_file_has_no_version():
    listed_file = _listed("docs/a.txt")
    loaded_files = _loaded_files(listed_file)
    loaded_files.forget(listed_file)

    assert loaded_files.versions_of([listed_file]) == {}


@pytest.mark.parametrize(
    "file_key, listed_keys, expected",
    [
        ("docs/a.txt", ["docs/a.txt"], "KB:kb-1#a.txt"),
        ("docs/sub/my_chunk_1.txt", ["docs/sub/my_chunk_1.txt"], "KB:kb-1#my_chunk_1.txt"),
        ("a.txt", ["a.txt"], None),
        ("sub/a.txt", ["sub/a.txt", "a.txt"], None),
    ],
    ids=["file in a folder", "name containing _chunk_", "file without a folder", "another listed file's id"],
)
def test_replaced_document_id(file_key, listed_keys, expected):
    listed_ids = {document_id(KB_ID, key) for key in listed_keys}

    assert replaced_document_id(KB_ID, file_key, listed_ids) == expected


@pytest.mark.parametrize(
    "rag_config, expected",
    [
        (VECTOR_ONLY, True),
        (VECTOR_AND_LEGRA, False),
        ({"enabled": True, "vector": {"enabled": True}, "lightrag": {"enabled": True}}, False),
        ({"enabled": True, "vector": {"enabled": False}, "legra": {"enabled": True}}, False),
        ({"enabled": False, "vector": {"enabled": True}}, False),
        ({"vector": {"enabled": True}}, False),
        ({}, False),
        (None, False),
        ({"enabled": True, "vector": "not settings"}, False),
    ],
    ids=[
        "vector only", "vector and legra", "vector and lightrag", "legra only", "rag switched off",
        "no rag switch", "empty", "missing", "unreadable",
    ],
)
def test_only_vector_store_enabled(rag_config, expected):
    assert only_vector_store_enabled(rag_config) is expected


def test_legra_settings_are_read_not_treated_as_unreadable():
    from app.modules.data.service import AgentRAGService

    assert AgentRAGService.from_kb_config("", VECTOR_AND_LEGRA).config.get_legra_config() is not None


class _DataSourceReadFromTheDatabase:
    """A data source whose fields cannot be read after its session was rolled back, like a database object."""

    source_type = "s3"
    connection_data = {"bucket_name": "acme"}

    def __init__(self):
        self.session_rolled_back = False

    @property
    def name(self):
        if self.session_rolled_back:
            raise RuntimeError("the data source can no longer be read")
        return "S3 DS"


class _S3Folder:
    """A fake S3 folder, knowledge base store and KB row that the syncs run against."""

    def __init__(self, rag_config=VECTOR_ONLY, **extra_metadata):
        self.kb_id = uuid.uuid4()
        self.sync_source_id = uuid.uuid4()
        self.row = SimpleNamespace(
            type="s3",
            rag_config=copy.deepcopy(rag_config),
            sync_source_id=self.sync_source_id,
            urls=None,
            extra_metadata={"processing_mode": "none", "save_output_path": None, **extra_metadata},
        )
        self.files = {}
        self.etags = {}
        self.documents = {}
        self.downloaded = []
        self.moved = []
        self.events = []
        self.keys_the_store_refuses = set()
        self.keys_that_cannot_be_downloaded = set()
        self.row_exists = True
        self.row_save_error = None
        self.row_saves = 0
        self.after_the_sync_read_the_kb = None
        self.on_download = None

    def upload(self, key, text="text", modified_at=FIRST_UPLOAD, etag=None):
        self.files[key] = (text, modified_at)
        self.etags[key] = etag

    def id_of(self, key):
        return document_id(self.kb_id, key)

    def recorded_keys(self):
        return set(self.row.extra_metadata.get(LOADED_FILES_KEY) or {})

    def forget_calls(self):
        self.downloaded, self.events = [], []

    def added(self):
        return [doc_id for event, doc_id in self.events if event == "added"]

    def removed(self):
        return [doc_id for event, doc_id in self.events if event == "removed"]

    def _kb(self, **fields):
        from app.schemas.agent_knowledge import KBRead

        return KBRead(
            id=self.kb_id,
            name="S3 KB",
            type="s3",
            sync_source_id=self.sync_source_id,
            extra_metadata=copy.deepcopy(self.row.extra_metadata),
            rag_config=copy.deepcopy(self.row.rag_config),
            **fields,
        )

    def _rag_manager(self):
        rag_manager = MagicMock()
        rag_manager.get_document_ids = AsyncMock(side_effect=self._stored_document_ids)
        rag_manager.add_document = AsyncMock(side_effect=self._add_document)
        rag_manager.delete_document = AsyncMock(side_effect=self._delete_document)
        return rag_manager

    def _stored_document_ids(self, kb):
        if self.after_the_sync_read_the_kb:
            self.after_the_sync_read_the_kb()
        return list(self.documents)

    def _add_document(self, kb, doc_id, content, metadata, legra_finalize=False):
        file_key = doc_id.split("#", 1)[1]
        if file_key in self.keys_the_store_refuses:
            self.documents.pop(doc_id, None)
            return {"vector": False}
        self.documents[doc_id] = content
        self.events.append(("added", doc_id))
        return {"vector": True}

    def _delete_document(self, kb, doc_id):
        self.documents.pop(doc_id, None)
        self.events.append(("removed", doc_id))
        return {"vector": True}

    def _download(self, **kwargs):
        file_key = kwargs["item"]
        if file_key in self.keys_that_cannot_be_downloaded:
            raise RuntimeError("connection reset")
        self.downloaded.append(file_key)
        if self.on_download:
            self.on_download()
        return file_key

    def _extract(self, mode, file):
        return {"content": self.files[file][0], "file_name": file.split("/")[-1], "metadata": {}}

    def _move(self, **kwargs):
        self.moved.append(kwargs["item"])
        self.files.pop(kwargs["item"])

    def _current_row(self, kb_service, kb_id):
        if self.row_save_error:
            raise self.row_save_error
        return self.row if self.row_exists else None

    def _count_row_save(self, row):
        self.row_saves += 1
        return row

    async def sync_now(self):
        from app.tasks import kb_batch_tasks

        kb = self._kb()
        kb_service = MagicMock()
        kb_service.get_by_id = AsyncMock(return_value=kb)
        kb_service.repository.update = AsyncMock(side_effect=self._count_row_save)
        data_source = _DataSourceReadFromTheDatabase()
        ds_service = MagicMock()
        ds_service.get_by_id = AsyncMock(return_value=data_source)
        transactions = MagicMock()
        transactions.commit = AsyncMock()
        transactions.rollback = AsyncMock(side_effect=lambda: setattr(data_source, "session_rolled_back", True))
        services = {
            kb_batch_tasks.KnowledgeBaseService: kb_service,
            kb_batch_tasks.DataSourceService: ds_service,
            kb_batch_tasks.AgentRAGServiceManager: self._rag_manager(),
            kb_batch_tasks.TransactionManager: transactions,
        }
        listed_files = [
            {"key": key, "size": len(text), "last_modified": modified_at, "etag": self.etags.get(key)}
            for key, (text, modified_at) in sorted(self.files.items())
        ]
        with patch.object(kb_batch_tasks, "injector") as fake_injector, patch.object(
            kb_batch_tasks, "s3_list_source", AsyncMock(return_value={"files": listed_files})
        ), patch.object(kb_batch_tasks, "s3_download_file", AsyncMock(side_effect=self._download)), patch.object(
            kb_batch_tasks, "get_content_from_file", AsyncMock(side_effect=self._extract)
        ), patch.object(kb_batch_tasks, "s3_move_file", AsyncMock(side_effect=self._move)), patch.object(
            kb_batch_tasks, "_current_kb_row", AsyncMock(side_effect=self._current_row)
        ):
            fake_injector.get.side_effect = lambda dependency: services.get(dependency, MagicMock())
            return await kb_batch_tasks.batch_process_files_kb_async(kb_id=str(kb.id))

    async def scheduled_sync(self):
        from app.tasks import s3_tasks

        folder = self
        kb = self._kb(sync_schedule="* * * * *", sync_active=True)
        kb_service = MagicMock()
        kb_service.get_by_id = AsyncMock(return_value=kb)
        kb_service.update = AsyncMock()
        ds_service = MagicMock()
        ds_service.get_by_id = AsyncMock(return_value=SimpleNamespace(
            name="S3 DS", source_type="s3",
            connection_data={"prefix": "", "bucket_name": "acme", "access_key": "k", "secret_key": "s", "region": "us-east-1"},
        ))

        class FakeS3Client:
            def __init__(self, **_):
                pass

            def list_files(self, prefix=None):
                return {"files": [
                    {"key": key, "size": len(text), "last_modified": modified_at.strftime("%Y-%m-%dT%H:%M:%S%z")}
                    for key, (text, modified_at) in sorted(folder.files.items())
                ]}

            def download_file(self, key, local_path):
                with open(local_path, "w") as f:
                    f.write(folder.files[key][0])
                return True

        services = {
            s3_tasks.KnowledgeBaseService: kb_service,
            s3_tasks.DataSourceService: ds_service,
            s3_tasks.AgentRAGServiceManager: self._rag_manager(),
        }
        with patch.object(s3_tasks, "injector") as fake_injector, patch.object(s3_tasks, "S3Client", FakeS3Client):
            fake_injector.get.side_effect = lambda dependency: services[dependency]
            return await s3_tasks.import_s3_files_to_kb_async(kb_id=kb.id)


def _folder_with_two_files(rag_config=VECTOR_ONLY, **extra_metadata):
    folder = _S3Folder(rag_config, **extra_metadata)
    folder.upload("docs/a.txt")
    folder.upload("docs/b.txt")
    return folder


@pytest.mark.asyncio
async def test_first_sync_now_loads_every_file_under_its_full_path():
    folder = _folder_with_two_files()

    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt", "docs/b.txt"]
    assert set(folder.documents) == {folder.id_of("docs/a.txt"), folder.id_of("docs/b.txt")}
    assert folder.recorded_keys() == {"docs/a.txt", "docs/b.txt"}


@pytest.mark.asyncio
async def test_second_sync_now_reads_and_writes_nothing_when_nothing_changed():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.forget_calls()

    result = await folder.sync_now()

    assert folder.downloaded == []
    assert folder.added() == []
    assert folder.row_saves == 1
    assert "status" not in result


@pytest.mark.asyncio
async def test_sync_now_loads_only_a_new_file():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.forget_calls()
    folder.upload("docs/c.txt")

    await folder.sync_now()

    assert folder.downloaded == ["docs/c.txt"]
    assert folder.recorded_keys() == {"docs/a.txt", "docs/b.txt", "docs/c.txt"}


@pytest.mark.asyncio
async def test_sync_now_loads_a_changed_file_again():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.forget_calls()
    folder.upload("docs/a.txt", text="new text", modified_at=LATER_UPLOAD)

    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt"]
    assert folder.documents[folder.id_of("docs/a.txt")] == "new text"


@pytest.mark.asyncio
async def test_sync_now_loads_a_file_rewritten_with_the_same_date_and_size():
    folder = _S3Folder()
    folder.upload("docs/a.txt", text="rate 1.5", etag='"first"')
    await folder.sync_now()
    folder.forget_calls()
    folder.upload("docs/a.txt", text="rate 2.5", etag='"second"')

    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt"]
    assert folder.documents[folder.id_of("docs/a.txt")] == "rate 2.5"


@pytest.mark.asyncio
async def test_sync_now_loads_every_file_again_after_the_processing_mode_changed():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.forget_calls()
    folder.row.extra_metadata["processing_mode"] = "extract"

    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt", "docs/b.txt"]


@pytest.mark.asyncio
async def test_sync_now_loads_files_again_when_the_knowledge_base_lost_them():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.forget_calls()
    folder.documents.clear()

    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt", "docs/b.txt"]


@pytest.mark.asyncio
async def test_knowledge_base_with_a_second_store_loads_every_file_on_every_sync():
    folder = _folder_with_two_files(rag_config=VECTOR_AND_LEGRA)
    await folder.sync_now()
    folder.forget_calls()

    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt", "docs/b.txt"]
    assert folder.recorded_keys() == set()
    assert folder.row_saves == 0


@pytest.mark.asyncio
async def test_file_that_failed_to_load_is_reported_and_tried_again():
    folder = _folder_with_two_files()
    folder.keys_the_store_refuses = {"docs/a.txt"}

    result = await folder.sync_now()

    assert result["status"] == "error"
    assert result["message"].startswith("1 file(s) could not be loaded")
    assert folder.recorded_keys() == {"docs/b.txt"}

    folder.forget_calls()
    folder.keys_the_store_refuses = set()
    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt"]


@pytest.mark.asyncio
async def test_changed_file_that_failed_to_load_is_no_longer_recorded():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.upload("docs/a.txt", text="new text", modified_at=LATER_UPLOAD)
    folder.keys_the_store_refuses = {"docs/a.txt"}

    await folder.sync_now()

    assert folder.recorded_keys() == {"docs/b.txt"}


@pytest.mark.asyncio
async def test_files_loaded_before_a_run_stopped_are_skipped_on_the_next_run():
    folder = _folder_with_two_files()
    folder.upload("docs/c.txt")
    folder.keys_that_cannot_be_downloaded = {"docs/b.txt"}

    with pytest.raises(RuntimeError, match="connection reset"):
        await folder.sync_now()

    assert folder.recorded_keys() == {"docs/a.txt"}

    folder.forget_calls()
    folder.keys_that_cannot_be_downloaded = set()
    await folder.sync_now()

    assert folder.downloaded == ["docs/b.txt", "docs/c.txt"]


@pytest.mark.asyncio
async def test_file_removed_from_the_folder_is_dropped_from_the_record_but_kept_in_the_knowledge_base():
    folder = _folder_with_two_files()
    await folder.sync_now()
    del folder.files["docs/b.txt"]

    await folder.sync_now()

    assert folder.recorded_keys() == {"docs/a.txt"}
    assert folder.id_of("docs/b.txt") in folder.documents


@pytest.mark.asyncio
async def test_old_file_name_document_is_removed_before_the_file_is_stored_under_its_full_path():
    folder = _S3Folder()
    folder.upload("docs/a.txt")
    old_document_id = f"KB:{folder.kb_id}#a.txt"
    folder.documents[old_document_id] = "stored by an earlier sync"

    await folder.sync_now()

    assert folder.events == [("removed", old_document_id), ("added", folder.id_of("docs/a.txt"))]
    assert set(folder.documents) == {folder.id_of("docs/a.txt")}


@pytest.mark.asyncio
async def test_old_file_name_document_is_also_replaced_in_a_knowledge_base_with_a_second_store():
    folder = _S3Folder(rag_config=VECTOR_AND_LEGRA)
    folder.upload("docs/a.txt")
    old_document_id = f"KB:{folder.kb_id}#a.txt"
    folder.documents[old_document_id] = "stored by an earlier sync"

    await folder.sync_now()

    assert folder.events == [("removed", old_document_id), ("added", folder.id_of("docs/a.txt"))]


@pytest.mark.asyncio
async def test_document_of_a_file_without_a_folder_is_kept_when_a_same_named_file_in_a_folder_is_loaded():
    folder = _S3Folder()
    folder.upload("a.txt", text="top level")
    await folder.sync_now()
    folder.forget_calls()
    folder.upload("sub/a.txt", text="in a folder")

    await folder.sync_now()

    assert folder.downloaded == ["sub/a.txt"]
    assert folder.documents == {folder.id_of("a.txt"): "top level", folder.id_of("sub/a.txt"): "in a folder"}


@pytest.mark.asyncio
async def test_settings_saved_during_a_sync_are_kept():
    folder = _folder_with_two_files()
    folder.on_download = lambda: folder.row.extra_metadata.update(processing_filter="*.pdf")

    await folder.sync_now()

    assert folder.row.extra_metadata["processing_filter"] == "*.pdf"
    assert folder.recorded_keys() == {"docs/a.txt", "docs/b.txt"}


@pytest.mark.asyncio
async def test_record_wiped_during_a_sync_is_written_again():
    folder = _folder_with_two_files()
    await folder.sync_now()
    folder.forget_calls()
    folder.after_the_sync_read_the_kb = lambda: folder.row.extra_metadata.pop(LOADED_FILES_KEY, None)

    await folder.sync_now()

    assert folder.downloaded == []
    assert folder.recorded_keys() == {"docs/a.txt", "docs/b.txt"}


@pytest.mark.asyncio
async def test_rag_settings_saved_during_a_sync_make_the_next_sync_load_every_file():
    folder = _folder_with_two_files()
    folder.on_download = lambda: setattr(folder.row, "rag_config", copy.deepcopy(VECTOR_WITH_OTHER_CHUNKS))

    await folder.sync_now()

    assert folder.recorded_keys() == set()

    folder.forget_calls()
    folder.on_download = None
    await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt", "docs/b.txt"]
    assert folder.recorded_keys() == {"docs/a.txt", "docs/b.txt"}


@pytest.mark.asyncio
async def test_sync_now_succeeds_when_the_loaded_files_cannot_be_saved():
    folder = _folder_with_two_files()
    folder.row_save_error = ConnectionError("database unavailable")

    result = await folder.sync_now()

    assert "status" not in result
    assert result["processed_kbs"] == 2
    assert folder.recorded_keys() == set()


@pytest.mark.asyncio
async def test_nothing_is_saved_when_the_knowledge_base_was_deleted_during_the_sync():
    folder = _folder_with_two_files()
    folder.row_exists = False

    result = await folder.sync_now()

    assert result["processed_kbs"] == 2
    assert folder.row_saves == 0


@pytest.mark.asyncio
async def test_output_folder_sync_loads_and_moves_every_file_as_before():
    folder = _folder_with_two_files(save_output_path="processed/")
    folder.documents[folder.id_of("docs/a.txt")] = "loaded earlier"
    folder.row.extra_metadata[LOADED_FILES_KEY] = {"docs/a.txt": file_version(_listed("docs/a.txt"), "none")}
    record_before = dict(folder.row.extra_metadata[LOADED_FILES_KEY])

    result = await folder.sync_now()

    assert folder.downloaded == ["docs/a.txt", "docs/b.txt"]
    assert folder.moved == ["docs/a.txt", "docs/b.txt"]
    assert result["processed_kbs"] == 2
    assert folder.row_saves == 0
    assert folder.row.extra_metadata[LOADED_FILES_KEY] == record_before


@pytest.mark.asyncio
async def test_output_folder_sync_replaces_the_old_file_name_document():
    folder = _S3Folder(save_output_path="processed/")
    folder.upload("docs/a.txt", text="new drop")
    folder.documents[f"KB:{folder.kb_id}#a.txt"] = "earlier drop"

    await folder.sync_now()

    assert folder.documents == {folder.id_of("docs/a.txt"): "new drop"}


@pytest.mark.asyncio
async def test_scheduled_sync_changes_nothing_after_sync_now():
    folder = _folder_with_two_files()
    await folder.sync_now()
    documents_after_sync_now = dict(folder.documents)
    folder.forget_calls()

    await folder.scheduled_sync()

    assert folder.events == []
    assert folder.documents == documents_after_sync_now


@pytest.mark.asyncio
async def test_sync_now_keeps_one_document_per_file_after_the_scheduled_sync():
    folder = _folder_with_two_files()
    await folder.scheduled_sync()
    documents_after_scheduled_sync = set(folder.documents)

    await folder.sync_now()
    folder.forget_calls()
    await folder.sync_now()

    assert set(folder.documents) == documents_after_scheduled_sync
    assert folder.downloaded == []


SOURCE_ID = uuid.uuid4()


async def _keep_on_save(kb_type, stored_metadata, page_metadata, row_exists=True, page_rag_config=VECTOR_ONLY):
    from app.tasks import kb_batch_tasks

    row = None
    if row_exists:
        row = SimpleNamespace(
            type=kb_type, rag_config=VECTOR_ONLY, sync_source_id=SOURCE_ID, urls=None, extra_metadata=stored_metadata
        )
    incoming = SimpleNamespace(
        type=kb_type, rag_config=page_rag_config, sync_source_id=SOURCE_ID, urls=None, extra_metadata=page_metadata
    )
    with patch.object(kb_batch_tasks, "_current_kb_row", AsyncMock(return_value=row)) as read_row:
        await kb_batch_tasks.keep_loaded_files_on_save(MagicMock(), uuid.uuid4(), incoming)
    return incoming.extra_metadata, read_row


@pytest.mark.asyncio
async def test_save_keeps_the_stored_versions_instead_of_the_pages_older_copy():
    saved, _ = await _keep_on_save(
        "s3",
        {LOADED_FILES_KEY: {"docs/a.txt": "new"}},
        {LOADED_FILES_KEY: {"docs/a.txt": "old"}, "processing_mode": "extract"},
    )

    assert saved == {LOADED_FILES_KEY: {"docs/a.txt": "new"}, "processing_mode": "extract"}


@pytest.mark.asyncio
async def test_save_that_clears_the_documents_empties_the_stored_versions():
    saved, _ = await _keep_on_save(
        "s3",
        {LOADED_FILES_KEY: {"docs/a.txt": "new"}},
        {LOADED_FILES_KEY: {"docs/a.txt": "old"}},
        page_rag_config=VECTOR_WITH_OTHER_CHUNKS,
    )

    assert saved[LOADED_FILES_KEY] == {}


@pytest.mark.asyncio
async def test_save_keeps_the_stored_versions_when_the_page_has_none():
    saved, _ = await _keep_on_save("s3", {LOADED_FILES_KEY: {"docs/a.txt": "new"}}, {"processing_mode": "none"})

    assert saved[LOADED_FILES_KEY] == {"docs/a.txt": "new"}


@pytest.mark.asyncio
async def test_save_drops_versions_only_the_page_has():
    saved, _ = await _keep_on_save("s3", {}, {LOADED_FILES_KEY: {"docs/a.txt": "old"}})

    assert LOADED_FILES_KEY not in saved


@pytest.mark.asyncio
async def test_save_of_another_knowledge_base_type_is_left_alone():
    page_metadata = {"content_format": "text"}

    saved, read_row = await _keep_on_save("zendesk", {LOADED_FILES_KEY: {"docs/a.txt": "new"}}, page_metadata)

    assert saved is page_metadata
    read_row.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_of_a_knowledge_base_that_no_longer_exists_is_left_alone():
    page_metadata = {"processing_mode": "none"}

    saved, _ = await _keep_on_save("s3", {}, page_metadata, row_exists=False)

    assert saved is page_metadata


@pytest.mark.asyncio
async def test_update_route_saves_the_stored_versions_not_the_pages_copy():
    import app.api.v1.routes.agent_knowledge as route_module
    from app.schemas.agent_knowledge import KBBase, KBRead

    kb_id = uuid.uuid4()
    stored_versions = {"docs/a.txt": "new"}
    current = KBRead(
        id=kb_id, name="KB", type="s3", rag_config=VECTOR_ONLY, extra_metadata={LOADED_FILES_KEY: stored_versions}
    )
    incoming = KBBase(
        name="KB", type="s3", rag_config=VECTOR_ONLY, extra_metadata={"processing_mode": "extract"}
    )
    knowledge_service = AsyncMock()
    knowledge_service.get_by_id = AsyncMock(return_value=current)
    knowledge_service.update = AsyncMock(return_value=current)
    locked_read = MagicMock()
    locked_read.scalars.return_value.first.return_value = current
    knowledge_service.repository.db.execute = AsyncMock(return_value=locked_read)
    with patch.object(route_module, "schedule_rag_load"), patch.object(
        route_module, "populate_remote_file_metadata", new=AsyncMock()
    ):
        await route_module.update_knowledge_item(
            kb_id, incoming, knowledge_service=knowledge_service, rag_manager=AsyncMock(), file_manager_service=AsyncMock()
        )

    saved_item = knowledge_service.update.await_args.args[1]
    assert saved_item.extra_metadata == {LOADED_FILES_KEY: stored_versions, "processing_mode": "extract"}


@pytest.mark.asyncio
async def test_update_route_empties_the_stored_versions_when_the_save_clears_the_documents():
    import app.api.v1.routes.agent_knowledge as route_module
    from app.schemas.agent_knowledge import KBBase, KBRead

    kb_id = uuid.uuid4()
    current = KBRead(
        id=kb_id, name="KB", type="s3", rag_config=VECTOR_ONLY, extra_metadata={LOADED_FILES_KEY: {"docs/a.txt": "v1"}}
    )
    incoming = KBBase(name="KB", type="s3", rag_config=VECTOR_WITH_OTHER_CHUNKS, extra_metadata={})
    knowledge_service = AsyncMock()
    knowledge_service.get_by_id = AsyncMock(return_value=current)
    knowledge_service.update = AsyncMock(return_value=current)
    locked_read = MagicMock()
    locked_read.scalars.return_value.first.return_value = current
    knowledge_service.repository.db.execute = AsyncMock(return_value=locked_read)
    rag_manager = AsyncMock()
    rag_manager.clear_documents = AsyncMock(return_value=None)
    with patch.object(route_module, "schedule_rag_load"), patch.object(
        route_module, "populate_remote_file_metadata", new=AsyncMock()
    ):
        await route_module.update_knowledge_item(
            kb_id, incoming, knowledge_service=knowledge_service, rag_manager=rag_manager, file_manager_service=AsyncMock()
        )

    rag_manager.clear_documents.assert_awaited_once()
    assert knowledge_service.update.await_args.args[1].extra_metadata[LOADED_FILES_KEY] == {}
