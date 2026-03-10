"""
Integration tests for the ML model analyze-pkl endpoint.

Run S3-as-default test:
  pytest tests/integration/ml_models/test_analyze_pkl.py -v -k s3_default

Run live S3 URL test (set TEST_PKL_S3_URL to a .pkl URL):
  TEST_PKL_S3_URL='https://...' pytest tests/integration/ml_models/test_analyze_pkl.py -k real_s3 -v
"""
import logging
import os
import pickle
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

logger = logging.getLogger(__name__)

TEST_PKL_S3_URL_ENV = "TEST_PKL_S3_URL"


@pytest.fixture
def minimal_pkl_path():
    """Create a minimal .pkl in wrapped format (model + metadata) for extraction."""
    wrapped = {
        "model": None,  # placeholder; validator only needs metadata for wrapped
        "metadata": {
            "model_type": "xgboost",
            "feature_columns": ["f1", "f2", "f3"],
        },
    }
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
        pickle.dump(wrapped, f)
        path = f.name
    yield path
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_analyze_pkl_with_file_upload(authorized_client, minimal_pkl_path):
    """Analyze-pkl with multipart file upload."""
    with open(minimal_pkl_path, "rb") as f:
        response = authorized_client.post(
            "/api/ml-models/analyze-pkl",
            files=[("file", ("model.pkl", f, "application/octet-stream"))],
        )
    assert response.status_code == 200
    data = response.json()
    assert data.get("model_type") == "xgboost"
    assert data.get("features") == ["f1", "f2", "f3"]
    assert data.get("error") is None


@pytest.mark.asyncio
async def test_analyze_pkl_with_pkl_file_url_s3_flow(authorized_client, minimal_pkl_path):
    """Analyze-pkl via pkl_file_url; download is mocked to simulate S3/remote."""
    async def mock_download(url: str, path: str) -> bool:
        with open(minimal_pkl_path, "rb") as src:
            with open(path, "wb") as dst:
                dst.write(src.read())
        return True

    with patch(
        "app.services.file_manager.FileManagerService.download_file_from_url_to_path",
        new_callable=AsyncMock,
        side_effect=mock_download,
    ):
        response = authorized_client.post(
            "/api/ml-models/analyze-pkl",
            data={"pkl_file_url": "https://example.com/bucket/model.pkl"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data.get("model_type") == "xgboost"
    assert data.get("features") == ["f1", "f2", "f3"]
    assert data.get("error") is None


@pytest.mark.asyncio
async def test_analyze_pkl_with_pkl_file_url_when_s3_default_provider(
    authorized_client, minimal_pkl_path
):
    """Analyze-pkl with pkl_file_url when S3 is the default file storage provider."""
    async def mock_download(url: str, path: str) -> bool:
        with open(minimal_pkl_path, "rb") as src:
            with open(path, "wb") as dst:
                dst.write(src.read())
        return True

    with patch(
        "app.services.file_manager.FileManagerService.download_file_from_url_to_path",
        new_callable=AsyncMock,
        side_effect=mock_download,
    ), patch(
        "app.services.file_manager.file_storage_settings.FILE_MANAGER_PROVIDER",
        "s3",
    ):
        response = authorized_client.post(
            "/api/ml-models/analyze-pkl",
            data={"pkl_file_url": "https://example.com/bucket/model.pkl"},
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("model_type") == "xgboost"
    assert data.get("features") == ["f1", "f2", "f3"]
    assert data.get("error") is None


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get(TEST_PKL_S3_URL_ENV),
    reason=f"Set {TEST_PKL_S3_URL_ENV} to a real .pkl URL (e.g. S3 presigned) to run",
)
async def test_analyze_pkl_with_real_s3_url(authorized_client):
    """Analyze-pkl using a real URL (e.g. S3 presigned); requires TEST_PKL_S3_URL."""
    url = os.environ.get(TEST_PKL_S3_URL_ENV).strip()
    assert url.lower().endswith(".pkl"), f"{TEST_PKL_S3_URL_ENV} must point to a .pkl file"
    response = authorized_client.post(
        "/api/ml-models/analyze-pkl",
        data={"pkl_file_url": url},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("error") is None, data.get("error")
    assert "model_type" in data or "features" in data
