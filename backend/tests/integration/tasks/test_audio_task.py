import os
import pytest
import random
import logging

from app.core.utils.s3_utils import S3Client

logger = logging.getLogger(__name__)


def _aws_credentials_available():
    """Check if AWS credentials are configured."""
    return all([
        os.getenv("AWS_RECORDINGS_BUCKET"),
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY"),
        os.getenv("AWS_REGION"),
    ])


@pytest.fixture(scope="module")
def new_datasource_data():
    data = {
        "name": "Test S3 Audio Data Source",
        "source_type": "s3",
        "connection_data": {
            "bucket_name": os.getenv("AWS_RECORDINGS_BUCKET"),
            "prefix": "sample-recordings/",
            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "region": os.getenv("AWS_REGION"),
        },
        "is_active": 1,
    }
    return data


async def create_ds(client, data):
    response = client.post("/api/datasources/", json=data)
    if response.status_code != 200:
        return False
    data["id"] = response.json()["id"]
    return True


@pytest.mark.asyncio(scope="session")
@pytest.mark.skipif(
    not _aws_credentials_available(),
    reason="AWS credentials not configured (AWS_RECORDINGS_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)"
)
async def test_s3_sync_new_audio_files(authorized_client, new_datasource_data):
    """Test S3 audio file sync functionality. Requires AWS credentials."""

    logger.info(f"Creating test audio datasource: {new_datasource_data}")
    new_datasource_data["connection_data"]["prefix"] = f"test-audio-sync-{random.randint(1000, 9999)}/"

    if not await create_ds(authorized_client, new_datasource_data):
        pytest.skip("Could not create datasource for testing")

    # Find the test audio file
    dir_path = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(dir_path)
    filename = os.path.join(parent_dir, 'audio', 'tech-support.mp3')

    if not os.path.exists(filename):
        pytest.skip(f"Test audio file not found: {filename}")

    logger.info("uploading test file: %s", filename)

    # Use the S3 client to upload sample audio files
    try:
        s3_client = S3Client(
            bucket_name=new_datasource_data["connection_data"]["bucket_name"],
            aws_access_key_id=new_datasource_data["connection_data"]["access_key"],
            aws_secret_access_key=new_datasource_data["connection_data"]["secret_key"],
            region_name=new_datasource_data["connection_data"]["region"]
        )
    except Exception as e:
        pytest.skip(f"Could not create S3 client: {e}")

    # Upload the temporary file to S3
    s3_key = f"{new_datasource_data['connection_data']['prefix']}sample_audio_{random.randint(1000, 9999)}.mp3"

    try:
        s3_client.upload_file(
            filename,
            new_datasource_data["connection_data"]["bucket_name"],
            s3_key
        )
        logger.info(f"Uploaded sample audio file to S3: {s3_key}")
    except Exception as e:
        pytest.skip(f"Could not upload file to S3: {e}")

    try:
        # Run import task
        logger.info("Running import job")
        j_response = authorized_client.get(f"/api/voice/run-s3-audio-sync/{new_datasource_data['id']}")
        assert j_response.status_code == 200, f"Import job failed: {j_response.json()}"
        j_data = j_response.json()

        logger.info(f"Import task result: {j_data}")
        assert j_data is not None
        assert j_data["failed"] == 0
        assert j_data["processed"] > 0

    except Exception as e:
        logger.error(f"Error during import task: {e}")
        import traceback
        logger.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
        raise

    finally:
        # Cleanup - try to delete the uploaded file
        try:
            s3_client.delete_file(
                new_datasource_data["connection_data"]["bucket_name"] + "/" + s3_key
            )
        except Exception as cleanup_error:
            logger.warning(f"Could not cleanup S3 file: {cleanup_error}")

