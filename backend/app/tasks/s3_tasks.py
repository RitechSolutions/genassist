import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import textract
from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.utils.s3_utils import S3Client
from app.db.models.datasource import DataSourceModel
from app.db.session import get_db
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.repositories.datasources import DataSourcesRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.agent_knowledge import KBCreate
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.datasources import DataSourceService
from app.tasks import celery_app
from app.tasks.tasks import BaseTaskWithLogging

logger = logging.getLogger(__name__)


@celery_app.task(base=BaseTaskWithLogging)
def import_s3_files_to_kb(kb_id: UUID):
    """
    Import files from S3 bucket into the knowledge base.

    Args:
        prefix: Filter files by prefix (folder path)
        file_extensions: List of file extensions to filter (e.g., ['.pdf', '.txt'])
        max_files: Maximum number of files to process
        embeddings_model: Model to use for embeddings
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(import_s3_files_to_kb_async0(kb_id))


async def import_s3_files_to_kb_async0(kb_id: UUID):
    async for db in get_db():
        await import_s3_files_to_kb_async(kb_id, db)


async def import_s3_files_to_kb_async(kb_id: UUID, db: AsyncSession):
    """Async implementation of S3 file import"""
    logger.info("Starting S3 file import...")

    kb_service = KnowledgeBaseService(repository=KnowledgeBaseRepository(db))
    ds_service = DataSourceService(repository=DataSourcesRepository(db))
    agent_ds_service = AgentDataSourceService.get_instance()

    kbList = []
    if not kb_id:
        kbList = await kb_service.get_all()
    else:
        kbList = [await kb_service.get_by_id(kb_id)]

    processed_ds = 0
    files_added_tot = 0
    files_deleted_tot = 0
    errors = []
    last_file_date = None

    for kb in kbList:
        logger.info(f"Processing knowledge base {kb.name}")

        if kb.sync_active == 0 or not kb.sync_source_id:
            logger.info(
                f"Knowledge base {kb.id} is not active or does not have a sync source"
            )
            continue

        ds = await ds_service.get_by_id(kb.sync_source_id)
        if not ds:
            logger.info(f"Knowledge base {kb.id} has no sync source")
            continue

        if ds.source_type != "s3":
            logger.info(
                f"Knowledge base {kb.id} has a sync source that is not an S3 bucket"
            )
            continue

        cron_string = kb.sync_schedule
        if not cron_string:
            logger.info(f"Knowledge base {kb.id} has no sync schedule")
            continue

        cron_iter = croniter(cron_string)
        next_run_time = datetime.now()
        if kb.last_synced:
            logger.info("Getting next run time from last synced")
            next_run_time = cron_iter.get_next(start_time=kb.last_synced)
            next_run_time = datetime.fromtimestamp(next_run_time)
            logger.info(
                f"Knowledge base {kb.id} last synced at {kb.last_synced}, next run time: {next_run_time}"
            )

        if datetime.now() < next_run_time:
            logger.info(
                f"Knowledge base {kb.id} is not due for sync, next sync at {next_run_time}"
            )
            continue

        if not ds.connection_data:
            logger.info(
                f"Knowledge base {kb.id} has no connection data for sync source {ds.name}"
            )
            continue

        conn_data = json.loads(ds.connection_data)

        prefix = conn_data["prefix"]
        bucket = conn_data["bucket_name"]
        access_key = conn_data["aws_access_key_id"]
        secret_key = conn_data["aws_secret_access_key"]
        region = conn_data["region_name"]

        # Initialize S3 client
        s3_client = S3Client(
            bucket_name=bucket,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        # Get list of files from S3
        result = s3_client.list_files(
            prefix=prefix,
        )

        if not result["files"]:
            logger.info(
                f"No files found in S3 with prefix: {prefix} in datasource {ds.name}"
            )
            processed_ds += 1
            kb.last_synced = datetime.now()
            await kb_service.update(kb.id, KBCreate(**kb.model_dump_json()))  # type: ignore
            continue

        files_added = 0
        files_deleted = 0
        errors = []

        logger.info("Getting existing files from RAG...")
        existing_files = await agent_ds_service.get_document_ids(kb)
        logger.info(
            f"Found {len(existing_files)} existing files in RAG for knowledge base {kb.id}"
        )
        logger.info(f"Existing files: {existing_files}")

        s3_new_files = [
            file_info
            for file_info in result["files"]
            #if file_info["key"] not in existing_files
            if not any(existing_file.startswith(f"KB:{str(kb.id)}#{file_info['key']}") for existing_file in existing_files)
        ]
        logger.info(
            f"Found {len(s3_new_files)} new files in S3 to process for knowledge base {kb.id}"
        )
        logger.info(f"New files: {s3_new_files}")

        s3_deleted_files = [
            ex_file
            for ex_file in existing_files
            #if ex_file not in [f"KB:{str(kb.id)}#{f['key']}" for f in result["files"]]
            if not any(ex_file.startswith(f"KB:{str(kb.id)}#{f['key']}") for f in result["files"])
        ]
        logger.info(
            f"Found {len(s3_deleted_files)} deleted files in S3 to process for knowledge base {kb.id}"
        )

        # Delete files from RAG
        if s3_deleted_files:
            for filename in s3_deleted_files:
                try:
                    logger.info(f"Deleting file {filename} from RAG...")
                    await agent_ds_service.delete_doc(kb, filename)
                    files_deleted += 1
                except Exception as e:
                    error_msg = f"Error deleting file {filename}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue

        current_file = 0
        # add new files to RAG
        for file_info in s3_new_files:
            try:
                current_file += 1
                logger.info(f"Processing file {current_file} of {len(result['files'])}")

                # Create a temporary file to store the S3 content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    # Download file content
                    file_content = s3_client.get_file_content(file_info["key"])
                    temp_file.write(file_content)
                    temp_file.flush()

                    logger.info(f"Extracting text from {file_info}...")
                    extracted_text = textract.process(temp_file.name).decode("utf-8")

                    # Create knowledge base item
                    last_file_date = datetime.strptime(
                        file_info["last_modified"], "%Y-%m-%dT%H:%M:%S%z"
                    )
                    if not kb.last_file_date or last_file_date > kb.last_file_date:
                        last_file_date = datetime.now()

                    # add doc to RAG
                    doc_id = (
                        "KB:"
                        + str(kb.id)
                        + "#"
                        + file_info["key"]
                    )
                    file_name = file_info["key"].split("/")[-1]

                    rag_config = kb.rag_config

                    metadata = {
                        "name": file_name,
                        "description": f"File in {kb.name} from S3 source {ds.name}",  # type: ignore
                        "kb_id": str(kb.id),
                    }

                    # embed in RAG
                    res = await agent_ds_service.process_document(
                        doc_id, extracted_text, metadata, rag_config
                    )
                    logger.info(f"Document {file_name} processed with result: {res}")
                    files_added += 1

            except Exception as e:
                error_msg = f"Error processing file {file_info['key']}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            finally:
                # Cleanup temporary file
                if "temp_file" in locals():
                    os.unlink(temp_file.name)

        existing_files = await agent_ds_service.get_document_ids(kb)
        logger.info(
            f"Updated to {len(existing_files)} existing files in RAG for knowledge base {kb.id}"
        )

        search_results = await agent_ds_service.search_knowledge("Test", 2, [kb])
        logger.info(   
            f"Found {len(search_results)} search results in RAG for knowledge base {kb.id}"
        )

        # Update last synced time
        logger.info(f"Updating knowledge base {kb.id} last synced time...")
        kb_update = json.loads(kb.model_dump_json())
        kb_update["last_synced"] = datetime.now()
        kb_update["last_file_date"] = last_file_date
        await kb_service.update(kb.id, KBCreate(**kb_update))

        files_added_tot += files_added
        files_deleted_tot += files_deleted
        processed_ds += 1

    res = {
        "status": "completed",
        "files_added": files_added_tot,
        "files_deleted": files_deleted_tot,
        "datasources_processed": processed_ds,
        "errors": errors if errors else None,
    }

    logger.info(f"S3 file import completed with result: {res}")
    return res
