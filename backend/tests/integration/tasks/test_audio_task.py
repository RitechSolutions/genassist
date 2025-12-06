import os
import pytest
import json
import tempfile
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.audio_tasks import transcribe_audio_files_async, transcribe_audio_files_async_with_scope
from app.core.utils.s3_utils import S3Client
import random

import logging

logger = logging.getLogger(__name__)


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
    assert response.status_code == 200
    data["id"] = response.json()["id"]  # Store ID for later tests


@pytest.mark.asyncio(scope="session")
async def test_s3_sync_new_audio_files(
     authorized_client, new_datasource_data):
    
    logger.info(f"Creating test audio datasource: {new_datasource_data}")
    new_datasource_data["connection_data"]["prefix"] = f"test-audio-sync-{random.randint(1000, 9999)}/"
    await create_ds(authorized_client, new_datasource_data)

    #upload sample file to S3
    dir_path = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(dir_path)

    filename = parent_dir+'/audio/tech-support.mp3'
    logger.info("uploading test file:"+filename)

    # Use the S3 client to upload sample audio files    
    s3_client = S3Client(
        bucket_name=new_datasource_data["connection_data"]["bucket_name"],
        aws_access_key_id=new_datasource_data["connection_data"]["access_key"],
        aws_secret_access_key=new_datasource_data["connection_data"]["secret_key"],
        region_name=new_datasource_data["connection_data"]["region"]
    )

    # Upload the temporary file to S3
    s3_key = f"{new_datasource_data['connection_data']['prefix']}sample_audio_{random.randint(1000, 9999)}.mp3"
    s3_client.upload_file(
        filename,
        new_datasource_data["connection_data"]["bucket_name"],
        s3_key)
    logger.info(f"Uploaded sample audio file to S3: {s3_key}")

    try:
        # Run import task /jobs/s3_audio_transcribe
        #res = await transcribe_audio_files_async(kbid)

        logger.info(f"Running import job")
        j_response = authorized_client.get(f"/api/voice/run-s3-audio-sync/{new_datasource_data['id']}")
        assert j_response.status_code == 200
        j_data = j_response.json()

        logger.info(f"Import task result: {j_data}")
        assert j_data is not None
        assert j_data["failed"] == 0
        assert j_data["processed"] > 0

        s3_client.delete_file( new_datasource_data["connection_data"]["bucket_name"] + "/" + s3_key)

    except Exception as e:
        logger.error(f"Error during import task: {e}")
        import traceback
        logger.error(''.join(traceback.format_exception(e)))

        assert False, f"Import task failed with error: {e}"

    finally:
        # Remove explicit session close since it's managed by the fixture
        pass

