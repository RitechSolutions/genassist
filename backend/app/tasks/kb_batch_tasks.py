import asyncio
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional

from celery import shared_task

from app.dependencies.injector import injector
from app.services.datasources import DataSourceService
from app.services.app_settings import AppSettingsService
from app.services.llm_analysts import LlmAnalystService
from app.services.AzureStorageService import AzureStorageService

logger = logging.getLogger(__name__)


@shared_task
def batch_process_files_kb(ds_id: Optional[str] = None):
    """
    Celery task entry point.
    Runs async summary pipeline for Azure blob files.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(batch_process_files_kb_async_with_scope(ds_id))


async def batch_process_files_kb_async_with_scope(ds_id: Optional[str] = None):
    """Wrapper to run KB batch processing for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        batch_process_files_kb_async,
        "KB batch processing",
        ds_id=ds_id
    )


async def batch_process_files_kb_async(ds_id: Optional[str] = None):
    dsService = injector.get(DataSourceService)
    settingsService = injector.get(AppSettingsService)
    llmService = injector.get(LlmAnalystService)

    # Load Azure credentials from settings or datasource config
    if ds_id:
        ds_item = await dsService.get_by_id(ds_id, True)
        datasources = [ds_item]
    else:
        datasources = await dsService.get_by_type("azure_blob", True)

    count_datasource = 0
    count_success = 0
    count_fail = 0
    processed = []

    for ds_item in datasources:
        if ds_item.is_active == 0:
            continue

        count_datasource += 1
        conn = ds_item.connection_data
        logger.info(f"Processing Azure Blob Datasource: {conn}")

        # Required Azure details stored in datasource connection_data
        container = conn.get("container_name")
        prefix = conn.get("input_prefix", "incoming")
        summary_prefix = conn.get("summary_prefix", "summary")

        azure = AzureStorageService(
            connection_string=conn.get("connection_string"),
            container_name=container
        )

        # List files to summarize
        files = azure.file_list(prefix=prefix)
        if not files:
            logger.info(f"No files found in container: {container}/{prefix}")
            continue

        for blob_path in files:
            filename = blob_path.replace(prefix + "/", "")  # Clean file name

            try:
                logger.info(f"Reading blob: {blob_path}")
                container_client = azure._get_container()
                blob_client = container_client.get_blob_client(blob_path)

                content_bytes = blob_client.download_blob().readall()
                content = content_bytes.decode("utf-8", errors="ignore")

                # Generate Summary via LLM
                logger.info(f"Summarizing {filename}...")
                summary_text = await llmService.generate_summary(content)

                # Save summary file in summary folder
                summary_filename = f"{filename}.summary.txt"
                azure.file_upload_content(
                    local_file_content=summary_text.encode("utf-8"),
                    local_file_name=summary_filename,
                    destination_name=summary_filename,
                    prefix=summary_prefix
                )

                processed.append({"file": filename, "summary": summary_filename})
                count_success += 1

            except Exception as e:
                count_fail += 1
                logger.error(f"Failed to summarize {filename}: {str(e)}")

    return {
        "datasources": count_datasource,
        "processed": count_success,
        "failed": count_fail,
        "files": processed
    }
