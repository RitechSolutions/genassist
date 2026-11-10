import pytest


@pytest.fixture(autouse=True)
def _training_data_stays_on_disk(monkeypatch):
    """Unit tests have no File Manager, so training data is stored as with the default local provider."""
    from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
    from app.modules.workflow.engine.nodes.ml import ml_utils, training_data_storage

    async def local_provider():
        return LocalFileSystemProvider({"base_path": str(ml_utils.DATA_VOLUME)})

    monkeypatch.setattr(training_data_storage, "_storage_provider", local_provider)
