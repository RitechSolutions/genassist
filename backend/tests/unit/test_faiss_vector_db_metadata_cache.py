"""Persistence round-trip and CWE-502 regression tests for the FAISS metadata cache"""

import logging
import os
import pickle

import numpy as np
import pytest

from app.modules.data.providers.vector.db.base import VectorDBConfig
from app.modules.data.providers.vector.db.faiss import FaissVectorDB

LOGGER_NAME = "app.modules.data.providers.vector.db.faiss"
LOAD_FAILED = "Failed to load FAISS index"


def _config(persist_directory) -> VectorDBConfig:
    return VectorDBConfig(
        type="faiss", collection_name="kb", persist_directory=str(persist_directory), index_type="flat"
    )


def _metadata_file(config: VectorDBConfig) -> str:
    return os.path.join(config.persist_directory, f"{config.collection_name}_metadata.pkl")


async def _populated_db(persist_directory) -> FaissVectorDB:
    db = FaissVectorDB(_config(persist_directory))
    assert await db.initialize()
    assert await db.create_collection(3)
    assert await db.add_vectors(
        ["doc-a", "doc-b"],
        [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
        [{"source": "a"}, {"source": "b"}],
        ["alpha", "beta"],
    )
    return db


async def _reload(persist_directory, caplog) -> FaissVectorDB:
    db = FaissVectorDB(_config(persist_directory))
    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        assert await db.initialize()
    return db


def _assert_empty_state(db: FaissVectorDB) -> None:
    assert db.index is None
    assert db.id_map == {}
    assert db.metadata_map == {}
    assert db.content_map == {}
    assert db.next_id == 0


@pytest.mark.asyncio
async def test_metadata_cache_round_trips(tmp_path):
    saved = await _populated_db(tmp_path)
    assert os.path.exists(_metadata_file(saved.config))

    loaded = FaissVectorDB(_config(tmp_path))
    assert await loaded.initialize()
    assert loaded.index.ntotal == 2
    assert loaded.id_map == {0: "doc-a", 1: "doc-b"}
    assert loaded.metadata_map == {"doc-a": {"source": "a"}, "doc-b": {"source": "b"}}
    assert loaded.content_map == {"doc-a": "alpha", "doc-b": "beta"}
    assert loaded.next_id == 2
    assert loaded.dimension == 3


@pytest.mark.asyncio
async def test_malicious_metadata_cache_is_refused_without_side_effects(tmp_path, caplog):
    saved = await _populated_db(tmp_path)
    marker = tmp_path / "pwned"

    class _WriteFile:
        def __reduce__(self):
            return (os.system, (f"touch {marker}",))

    with open(_metadata_file(saved.config), "wb") as f:
        pickle.dump(_WriteFile(), f)

    db = await _reload(tmp_path, caplog)
    assert not marker.exists()
    _assert_empty_state(db)
    assert f"{LOAD_FAILED}: Blocked:" in caplog.text


@pytest.mark.asyncio
async def test_numpy_typed_metadata_cache_is_refused(tmp_path, caplog):
    saved = await _populated_db(tmp_path)
    poisoned = {"id_map": {}, "metadata_map": {}, "content_map": {}, "next_id": 0, "dimension": np.int64(3)}
    with open(_metadata_file(saved.config), "wb") as f:
        pickle.dump(poisoned, f)

    db = await _reload(tmp_path, caplog)
    _assert_empty_state(db)
    assert f"{LOAD_FAILED}: Blocked:" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_bytes", [0, 0.5])
async def test_truncated_metadata_cache_resets_state_without_refusal(tmp_path, caplog, keep_bytes):
    saved = await _populated_db(tmp_path)
    path = _metadata_file(saved.config)
    with open(path, "rb") as f:
        data = f.read()
    with open(path, "wb") as f:
        f.write(data[: int(len(data) * keep_bytes)])

    db = await _reload(tmp_path, caplog)
    _assert_empty_state(db)
    assert LOAD_FAILED in caplog.text
    assert "Blocked:" not in caplog.text
