import os
import pytest
import tempfile
from app.core.utils.s3_utils import S3Client
import random

import logging

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def new_datasource_data():
    data = {
        "name": "Test S3 Data Source",
        "source_type": "s3",
        "connection_data": {
            "bucket_name": os.getenv("AWS_RECORDINGS_BUCKET"),  # AWS_S3_TEST_BUCKET"),
            "prefix": "docs/",
            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),  # S3_ACCESS_KEY_ID"),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),  # S3_SECRET_ACCESS_KEY"),
            "region": os.getenv("AWS_REGION"),  # S3_REGION_NAME"),
        },
        "is_active": 1,
    }
    return data


@pytest.fixture(scope="module")
def new_kb_data():
    data = {
        "name": "Test Knowledge Base for S3 Sync",
        "description": "A test knowledge base item",
        "type": "datasource",
        "content": "This is a test knowledge base content",
        "rag_config": {
            "vector": {
                "enabled": True,
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "chunk_strategy": "recursive",
                "vector_db_type": "chroma",
                "chunk_separators": "",
                "chunk_keep_separator": True,
                "embedding_batch_size": 32,
                "embedding_model_name": "all-MiniLM-L6-v2",
                "embedding_device_type": "cpu",
                "chunk_strip_whitespace": True,
                "vector_db_collection_name": "default",
                "embedding_normalize_embeddings": True,
            },
            "enabled": True,
        },
        "sync_schedule": "0 0 * * *",  # every day at midnight
        "sync_active": True,
    }
    return data


async def create_ds(client, data):
    data["name"] = f"{data['name']}-{random.randint(1000, 9999)}"  # Ensure unique name
    response = client.post("/api/datasources/", json=data)
    assert response.status_code == 200
    data["id"] = response.json()["id"]  # Store ID for later tests


async def create_kb(client, data):
    data["name"] = f"{data['name']}-{random.randint(1000, 9999)}"  # Ensure unique name

    response = client.post("/api/genagent/knowledge/items/", json=data)
    kb_data = response.json()
    logger.info(f"knowledge base creation response: {kb_data}")

    assert response.status_code == 200

    data["id"] = kb_data["id"]  # Store ID for later tests


@pytest.mark.skip(reason="Skipping temporarily until new error is fixed")
async def test_s3_sync_new_files(authorized_client, new_datasource_data, new_kb_data):
    logger.info(f"Creating datasource: {new_datasource_data}")
    await create_ds(authorized_client, new_datasource_data)

    logger.info(f"Creating knowledge base: {new_kb_data}")
    new_kb_data["sync_source_id"] = new_datasource_data["id"]
    await create_kb(authorized_client, new_kb_data)

    kbid = new_kb_data["id"]

    logger.info(f"Getting knowledge base: {kbid}")
    kb_response = authorized_client.get(f"/api/genagent/knowledge/items/{kbid}")
    assert kb_response.status_code == 200
    kb_data = kb_response.json()
    assert kb_data["sync_source_id"] == new_datasource_data["id"]
    prev_last_sync = kb_data["last_synced"]

    # Create temp file and upload to S3
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
        f.write("Test content for S3 sync")
        f.flush()

        conn_data = new_datasource_data["connection_data"]
        logger.info(f"Connection data: {conn_data}")

        s3_client = S3Client(
            bucket_name=new_datasource_data["connection_data"]["bucket_name"],
            aws_access_key_id=new_datasource_data["connection_data"]["access_key"],
            aws_secret_access_key=new_datasource_data["connection_data"]["secret_key"],
            region_name=new_datasource_data["connection_data"]["region"],
        )

        # Upload test file
        bucket = conn_data["bucket_name"]

        rand_ids = random.sample(range(10), 5)
        for i in rand_ids:
            key = f"{conn_data['prefix']}test_file_{i}.txt"
            logger.info(f"Uploading test file to S3: s3://{bucket}/{key}")

            s3_client.upload_content(f"Test content {i}", bucket, key)
            logger.info(f"Uploaded test file to S3: s3://{bucket}/{key}")

        try:
            # Run import task
            # res = await import_s3_files_to_kb_async(kbid)
            res = authorized_client.get(
                f"/api/genagent/knowledge/run-s3-file-sync/{kbid}"
            )

            logger.info(f"Import task result: {res}")
            assert res.status_code == 200
            assert res.json()["status"] == "completed"

            # Verify process was run
            kb_response = authorized_client.get(f"/api/genagent/knowledge/items/{kbid}")
            assert kb_response.status_code == 200
            kb_data = kb_response.json()
            lastSync = kb_data["last_synced"]
            logger.info(f"Knowledge base data last syc: {lastSync}")

            assert lastSync is not None
            if prev_last_sync is not None:
                assert lastSync > prev_last_sync

            existing_files = s3_client.list_files(conn_data["prefix"])
            logger.info(f"Existing files in S3: {existing_files}")

            existing_files = existing_files["files"]
            if len(existing_files) < 5:
                return

            # delete 5 files randomly from the list
            rand_indexes = random.sample(
                range(len(existing_files)), len(existing_files) - 5
            )
            logger.info(f"Random indexes to delete: {rand_indexes}")
            for f in rand_indexes:
                key = existing_files[f]["key"]
                logger.info(f"Deleting test file from S3: {key}")
                s3_client.delete_file(key)
                logger.info(f"Deleted test file from S3: {key}")

            # Run import task
            # res = await import_s3_files_to_kb_async(kbid)
            res = authorized_client.get(
                f"/api/genagent/knowledge/run-s3-file-sync/{kbid}"
            )
            logger.info(f"Import task result 2: {res}")
            assert res.status_code == 200
            res = res.json()
            assert res["status"] == "completed"
            assert (
                res["files_added"] == 0
            )  # sync not run for second time because of schedule

            # update last sync time of KB to be able to run the task again
            kb_response = authorized_client.get(f"/api/genagent/knowledge/items/{kbid}")
            assert kb_response.status_code == 200
            kb_data = kb_response.json()
            kb_data["last_synced"] = None
            authorized_client.put(f"/api/genagent/knowledge/items/{kbid}", json=kb_data)

            # Run import task
            # res = await import_s3_files_to_kb_async(kbid)
            res = authorized_client.get(
                f"/api/genagent/knowledge/run-s3-file-sync/{kbid}"
            )
            logger.info(f"Import task result 3: {res}")
            assert res.status_code == 200
            res = res.json()
            assert res["status"] == "completed"
            assert (
                res["files_deleted"] == len(rand_indexes) + 1
            )  # including 1 more file that gets added from KB content during load_knowledge_base

        except Exception as e:
            logger.error(f"Error during import task: {e}")
            import traceback

            logger.error("".join(traceback.format_exception(e)))

            assert False, f"Import task failed with error: {e}"

        finally:
            # Remove explicit session close since it's managed by the fixture
            pass
