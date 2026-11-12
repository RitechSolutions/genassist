"""Which S3 files a knowledge base already holds in their current version."""

from typing import Any, Collection, Dict, Iterable, Mapping, Optional

from app.modules.data.service import AgentRAGService

LOADED_FILES_KEY = "s3_loaded_files"


def document_id(kb_id: Any, file_key: str) -> str:
    """The id of an S3 file's document; the scheduled S3 sync builds the same one."""
    return f"KB:{kb_id}#{file_key}"


def file_name_document_id(kb_id: Any, file_key: str) -> str:
    """The id Sync Now used before it kept the folder: the file name alone."""
    return f"KB:{kb_id}#{file_key.split('/')[-1]}"


def file_version(s3_file: Mapping[str, Any], processing_mode: Optional[str]) -> Optional[str]:
    """What a file looked like and how it was read; None when S3 gave no modified date."""
    last_modified = s3_file.get("last_modified")
    if last_modified is None:
        return None
    return f"{last_modified.isoformat()}|{s3_file.get('size')}|{s3_file.get('etag')}|{processing_mode}"


def only_vector_store_enabled(rag_config: Optional[Mapping[str, Any]]) -> bool:
    """True when the vector store is the knowledge base's only store; unreadable settings count as not."""
    try:
        stores = AgentRAGService.from_kb_config("", rag_config).config
    except Exception:
        return False
    has_another_store = bool(stores.get_legra_config() or stores.get_lightrag_config())
    return bool(stores.get_vector_config()) and not has_another_store


def replaced_document_id(kb_id: Any, file_key: str, listed_document_ids: Collection[str]) -> Optional[str]:
    """The file-name id a file may have been stored under before; None when that id belongs to a listed file."""
    old_id = file_name_document_id(kb_id, file_key)
    return None if old_id in listed_document_ids else old_id


class LoadedFiles:
    """The files of one knowledge base that are loaded, with the version each was loaded at."""

    def __init__(
        self,
        kb_id: Any,
        stored_document_ids: Iterable[str],
        stored_versions: Optional[Mapping[str, str]],
        processing_mode: Optional[str],
    ):
        self._kb_id = kb_id
        self._stored_document_ids = set(stored_document_ids)
        self._versions: Dict[str, str] = dict(stored_versions or {})
        self._processing_mode = processing_mode

    def is_current(self, s3_file: Mapping[str, Any]) -> bool:
        """True when the knowledge base holds the file and it has not changed since it was loaded."""
        version = file_version(s3_file, self._processing_mode)
        is_stored = document_id(self._kb_id, s3_file["key"]) in self._stored_document_ids
        return is_stored and version is not None and self._versions.get(s3_file["key"]) == version

    def remember(self, s3_file: Mapping[str, Any]) -> None:
        version = file_version(s3_file, self._processing_mode)
        if version is None:
            self.forget(s3_file)
            return
        self._versions[s3_file["key"]] = version

    def forget(self, s3_file: Mapping[str, Any]) -> None:
        self._versions.pop(s3_file["key"], None)

    def versions_of(self, listed_files: Iterable[Mapping[str, Any]]) -> Dict[str, str]:
        """The versions of the files still listed; files gone from the folder are dropped."""
        listed_keys = {s3_file["key"] for s3_file in listed_files}
        return {key: version for key, version in self._versions.items() if key in listed_keys}
