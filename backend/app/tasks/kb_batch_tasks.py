import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

from aiohttp import ClientError
from celery import shared_task
from fastapi import HTTPException, UploadFile

from app.db.transaction_manager import TransactionManager
from app.dependencies.injector import injector
from app.modules.data.load_result import DocumentNotLoadedError, has_text, load_document
from app.modules.data.manager import AgentRAGServiceManager, save_load_action
from app.modules.data.s3_loaded_files import (
    LOADED_FILES_KEY,
    LoadedFiles,
    document_id,
    only_vector_store_enabled,
    replaced_document_id,
)
from app.modules.data.utils.file_extractor import FileTextExtractor
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.AzureStorageService import AzureStorageService
from app.services.datasources import DataSourceService
from app.services.llm_analysts import LlmAnalystService
from app.services.transcription import transcribe_audio_whisper
from app.tasks.base import run_async_in_celery
from app.tasks.salesforce_article_sync_tasks import _current_kb_row, import_salesforce_articles_to_kb_async
from app.tasks.zendesk_article_sync_tasks import import_zendesk_articles_to_kb_async

logger = logging.getLogger(__name__)


@shared_task
def batch_process_files_kb(kb_id: Optional[str] = None):
    """
    Celery task entry point.
    Runs async summary pipeline for Azure blob files.
    Accepts kb_id (single) - dispatches to appropriate Celery tasks by KB type.
    """
    return run_async_in_celery(
        batch_process_files_kb_async_with_scope(kb_id=kb_id),
        timeout=4 * 60,
        task_name="batch_process_files_kb",
    )


async def batch_process_files_kb_async_with_scope(
    kb_id: Optional[str] = None,
):
    """
    Wrapper to run KB batch processing.

    Args:
        kb_id: Specific KB ID to process.
    """
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        batch_process_files_kb_async,
        "KB batch processing",
        kb_id=kb_id
    )


async def batch_process_files_kb_async(
    kb_id: Optional[str] = None
):
    dsService = injector.get(DataSourceService)
    llmService = injector.get(LlmAnalystService)
    kbService = injector.get(KnowledgeBaseService)
    agentRAGServiceManager = injector.get(AgentRAGServiceManager)

    # Resolve list of kb_ids to process
    ids_to_process: List[str] = [kb_id] if kb_id else []

    # Dispatch KBs by type: Zendesk runs inline in this async context so the caller
    # (API or Celery worker) gets results and we respect the current tenant context.
    # Queuing import_zendesk_articles_to_kb.delay() here duplicated work and ran
    # run_task_with_tenant_support in the worker (master + all tenants) for one KB.
    zendesk_sync_results: list = []
    salesforce_sync_results: list = []
    # KBs that could not be synced at all; the manual sync reports them as a failure.
    kbs_not_synced: list = []
    kb_items = []
    for kid in ids_to_process:
        try:
            kb_item = await kbService.get_by_id(kid)

            # used for sync now on Zendesk KBs
            if kb_item.type.lower() == "zendesk":
                logger.debug(f"Running Zendesk article import inline for KB {kb_item.id}")
                zres = await import_zendesk_articles_to_kb_async(
                    kb_id=kb_item.id, sync_now=True
                )
                zendesk_sync_results.append(
                    {"kb_id": str(kb_item.id), "type": "zendesk", "result": zres}
                )
            elif kb_item.type.lower() == "salesforce":
                logger.debug(f"Running SalesForce article import inline for KB {kb_item.id}")
                sres = await import_salesforce_articles_to_kb_async(
                    kb_id=kb_item.id, sync_now=True
                )
                salesforce_sync_results.append(
                    {"kb_id": str(kb_item.id), "type": "salesforce", "result": sres}
                )
            else:
                # Queue regular KB batch processing task
                kb_items.append(kb_item)
        except Exception as e:
            logger.warning(f"Could not fetch KB {kid}: {e}")
            kbs_not_synced.append(str(kid))
            continue

    # Inline processing for non-zendesk types (s3, azure_blob, etc.)
    count_kbs = len(kb_items)
    count_success = 0
    count_skipped = 0
    count_fail = 0
    count_unchanged = 0
    files_not_loaded = 0
    files_processed = []
    count_zendesk_syncs = len(zendesk_sync_results)

    # Process KBs
    for kb_item in kb_items:
        if kb_item.type not in ["s3", "sharepoint", "smb_share_folder", "azure_blob", "google_bucket"]:
            # Only process KBs with folder structured sources for this task
            count_skipped += 1
            continue

        # KB/Datasourcce type is supported
        # Get KB Paramters/RAG configuration/Schedule details
        synch_schedule = kb_item.sync_schedule
        enable_synch = True if kb_item.sync_schedule else False
        save_output = kb_item.extra_metadata.get("save_output", False)
        llm_analyst_id = kb_item.extra_metadata.get("llm_analyst_id", None)
        processing_mode = kb_item.extra_metadata.get("processing_mode", "none") # "none", "extract", "transcribe"
        save_output_path = kb_item.extra_metadata.get("save_output_path", "output/")
        processing_filter = kb_item.extra_metadata.get("processing_filter", "*.*")
        save_in_conversation = kb_item.extra_metadata.get("save_in_conversation", False)
        transcription_engine = kb_item.extra_metadata.get("transcription_engine", "openai_whisper") # "google_chirp3", "openai_whisper"

        vector_config = kb_item.rag_config.get("vector", {})
        vector_enabled = vector_config.get("enabled", False)
        chunk_size = vector_config.get("chunk_size", 1000)
        chunk_overlap = vector_config.get("chunk_overlap", 200)
        chunk_strategy = vector_config.get("chunk_strategy", "recursive") # "recursive", "semantic", "simple"
        embedding_type = vector_config.get("embedding_type", "huggingface")
        vector_db_host = vector_config.get("vector_db_host", "localhost")
        vector_db_port = vector_config.get("vector_db_port", 8005)
        vector_db_type = vector_config.get("vector_db_type", "pgvector") # "pgvector", "chroma", "qdrant"
        chunk_separators = vector_config.get("chunk_separators", "\\n\\n,\\n, ,") # for recursive chunking
        embedding_model_id = vector_config.get("embedding_model_id", "all-MiniLM-L6-v2") # for cloud embedding services like AWS, Azure, etc.
        embedding_model_name = vector_config.get("embedding_model_name", "all-MiniLM-L6-v2") # for local embedding models
        chunk_keep_separator = vector_config.get("chunk_keep_separator", True)
        chunk_strip_whitespace = vector_config.get("chunk_strip_whitespace", True)
        vector_db_collection_name = vector_config.get("vector_db_collection_name", "default")
        embedding_normalize_embeddings = vector_config.get("embedding_normalize_embeddings", True)


        # Get datasource details
        ds_item = await dsService.get_by_id(kb_item.sync_source_id, True)

        # If datasource is missing or invalid, log and skip
        if not ds_item:
            logger.error(f"KB {kb_item.id} has no valid datasource with id {kb_item.sync_source_id}. Failling.")
            count_fail += 1
            kbs_not_synced.append(str(kb_item.id))
            continue


        conn = ds_item.connection_data
        logger.debug(f"Processing {ds_item.source_type} Datasource: {ds_item.name} for KB: {kb_item.name}")

        keyid_username=""
        secret_password=""
        bucket_server=""
        prefix_input_folder=""
        filter_pattern= ""
        region=""



        ##############################################
        # Process S3 Datasource/KB
        if ds_item.source_type.lower() == "s3":
            keyid_username = conn.get("access_key")
            secret_password = conn.get("secret_key")
            bucket_server = conn.get("bucket_name")
            prefix_input_folder = (conn.get("prefix") or "").lstrip("/").strip()
            filter_pattern = processing_filter # filter defined in KB not DS
            region = conn.get("region", "us-east-1")

            s3_files = await s3_list_source(
                api_key = keyid_username,
                api_secret = secret_password,
                region = region,
                bucket_name = bucket_server,
                prefix = prefix_input_folder,
                filter = filter_pattern
            )

            s3_access = {
                "api_key": keyid_username,
                "api_secret": secret_password,
                "region": region,
                "bucket_name": bucket_server,
            }
            listed_files = s3_files.get("files", [])
            listed_document_ids = {document_id(kb_item.id, s3_file["key"]) for s3_file in listed_files}
            files_stay_in_folder = not save_output_path
            skips_unchanged_files = files_stay_in_folder and only_vector_store_enabled(kb_item.rag_config)
            stored_document_ids = await agentRAGServiceManager.get_document_ids(kb_item) if skips_unchanged_files else []
            loaded_files = LoadedFiles(
                kb_item.id, stored_document_ids, kb_item.extra_metadata.get(LOADED_FILES_KEY), processing_mode
            )
            datasource_name = ds_item.name
            try:
                for s3_file in listed_files:
                    if s3_file.get("size", 0) == 0:
                        logger.debug(f"Skipping empty file: {s3_file['key']}")
                        count_skipped += 1
                        continue
                    if skips_unchanged_files and loaded_files.is_current(s3_file):
                        logger.debug(f"Skipping unchanged file: {s3_file['key']}")
                        count_unchanged += 1
                        continue
                    file_content = await s3_download_file(**s3_access, item=s3_file["key"])
                    logger.debug(f"Downloaded file {s3_file['key']} with size {s3_file['size']} bytes")

                    extracted_content = await get_content_from_file(mode=processing_mode, file=file_content)
                    has_readable_text = has_text(extracted_content.get("content"))

                    if vector_enabled and has_readable_text:
                        loaded_files.forget(s3_file)
                        await _remove_file_name_document(
                            agentRAGServiceManager, kb_item, s3_file["key"], listed_document_ids
                        )
                        try:
                            await _add_s3_document(
                                agentRAGServiceManager, kb_item, ds_item, s3_file["key"], extracted_content
                            )
                        except DocumentNotLoadedError as e:
                            logger.error(f"{e}; {s3_file['key']} stays in the input folder")
                            count_fail += 1
                            files_not_loaded += 1
                            continue
                        loaded_files.remember(s3_file)

                    if save_output_path:
                        await _move_to_output_folder(s3_access, s3_file["key"], save_output_path)

                    had_nothing_to_load = vector_enabled and not has_readable_text
                    if had_nothing_to_load:
                        logger.warning(f"{s3_file['key']} has no readable text; it was not loaded into the knowledge base")
                        count_skipped += 1
                    else:
                        count_success += 1
            finally:
                if skips_unchanged_files:
                    await _save_loaded_files(kbService, kb_item, loaded_files.versions_of(listed_files))

            logger.info(f"Finished processing S3 datasource {datasource_name} for KB {kb_item.name}\n - {count_success} files processed, \n - {count_unchanged} files unchanged, \n - {count_skipped} files skipped, and \n - {count_fail} failures.")



        elif ds_item.source_type.lower() == "azure_blob":
            # # Required connection details stored in datasource connection_data
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
                logger.debug(f"No files found in container: {container}/{prefix}")
                continue

            for blob_path in files:
                filename = blob_path.replace(prefix + "/", "")  # Clean file name

                try:
                    logger.debug(f"Reading blob: {blob_path}")
                    container_client = azure._get_container()
                    blob_client = container_client.get_blob_client(blob_path)

                    content_bytes = blob_client.download_blob().readall()
                    content = content_bytes.decode("utf-8", errors="ignore")

                    # Generate Summary via LLM
                    logger.debug(f"Summarizing {filename}...")
                    summary_text = await llmService.generate_summary(content)

                    # Save summary file in summary folder
                    summary_filename = f"{filename}.summary.txt"
                    azure.file_upload_content(
                        local_file_content=summary_text.encode("utf-8"),
                        local_file_name=summary_filename,
                        destination_name=summary_filename,
                        prefix=summary_prefix
                    )

                    files_processed.append({"file": filename, "summary": summary_filename})
                    count_success += 1

                except Exception as e:
                    count_fail += 1
                    logger.error(f"Failed to summarize {filename}: {str(e)}")

    result = {
        "total_kbs": count_kbs,
        "processed_kbs": count_success,
        "failed_kb": count_fail,
        "skipped_kbs": count_skipped,
        "files": files_processed,
        "zendesk_sync_results": zendesk_sync_results,
        "zendesk_kbs_synced": count_zendesk_syncs,
        "salesforce_sync_results": salesforce_sync_results,
        "salesforce_kbs_synced": len(salesforce_sync_results),
        "kbs_not_synced": kbs_not_synced,
    }
    if files_not_loaded:
        result["status"] = "error"
        result["message"] = (
            f"{files_not_loaded} file(s) could not be loaded into the knowledge base and were left in the input folder."
        )

    return result




############################################
#  S3 Helper  FUnctions (to be moved to a separate module)
############################################
import fnmatch

import boto3


async def _add_s3_document(
    rag_manager: AgentRAGServiceManager, kb_item, ds_item, file_key: str, extracted_content: dict
) -> None:
    """Add the extracted text to the knowledge base; raises when no store took it."""
    file_name = extracted_content.get("file_name", "unknown_file")
    rag_doc_id = document_id(kb_item.id, file_key)
    rag_doc_metadata = extracted_content.get("metadata", {})
    rag_doc_metadata["name"] = file_name
    rag_doc_metadata["description"] = f"File in {kb_item.name} from S3 source {ds_item.name}"
    rag_doc_metadata["kb_id"] = str(kb_item.id)
    logger.debug(f"Adding document {rag_doc_id} to RAG service for KB {kb_item.id}\nMetadata: {rag_doc_metadata}")

    warning = await load_document(
        rag_manager, kb_item, rag_doc_id, extracted_content["content"], rag_doc_metadata, file_name, legra_finalize=True
    )
    if warning:
        logger.warning(warning)


async def _remove_file_name_document(
    rag_manager: AgentRAGServiceManager, kb_item, file_key: str, listed_document_ids: set
) -> None:
    """Remove the document an earlier sync stored for this file under its name alone."""
    old_document_id = replaced_document_id(kb_item.id, file_key, listed_document_ids)
    if old_document_id:
        logger.debug(f"Removing {old_document_id}, replaced by {document_id(kb_item.id, file_key)}")
        await rag_manager.delete_document(kb_item, old_document_id)


async def _save_loaded_files(kb_service: KnowledgeBaseService, started_kb, versions: dict) -> None:
    """Write only the loaded-file versions onto the current KB row; when that fails the files are loaded again next time."""
    transactions = injector.get(TransactionManager)
    try:
        row = await _current_kb_row(kb_service, started_kb.id)
        if row is not None:
            await _write_loaded_files(kb_service, row, started_kb, versions)
        await transactions.commit()
    except Exception as e:
        logger.warning(f"Could not save the loaded files of KB {started_kb.id}: {e}")
        await transactions.rollback()


async def _write_loaded_files(kb_service: KnowledgeBaseService, row, started_kb, versions: dict) -> None:
    """Keep no versions when a save during the sync made the documents outdated, so the next sync loads every file."""
    documents_outdated = save_load_action(started_kb, row) == "clear"
    versions_to_keep = {} if documents_outdated else versions
    stored_versions = (row.extra_metadata or {}).get(LOADED_FILES_KEY) or {}
    if versions_to_keep == stored_versions:
        return
    row.extra_metadata = {**(row.extra_metadata or {}), LOADED_FILES_KEY: versions_to_keep}
    await kb_service.repository.update(row)


async def keep_loaded_files_on_save(kb_service: KnowledgeBaseService, kb_id, incoming) -> None:
    """On save, keep the loaded-file versions the KB row holds, or none when the save clears the documents."""
    if incoming.type != "s3":
        return
    current_row = await _current_kb_row(kb_service, kb_id)
    if current_row is None:
        return
    incoming_metadata = dict(incoming.extra_metadata or {})
    stored_versions = (current_row.extra_metadata or {}).get(LOADED_FILES_KEY)
    if save_load_action(current_row, incoming) == "clear":
        incoming_metadata[LOADED_FILES_KEY] = {}
    elif stored_versions is None:
        incoming_metadata.pop(LOADED_FILES_KEY, None)
    else:
        incoming_metadata[LOADED_FILES_KEY] = stored_versions
    incoming.extra_metadata = incoming_metadata


async def _move_to_output_folder(s3_access: dict, file_key: str, output_path: str) -> None:
    """Move a processed input file to the output folder under a timestamped name."""
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
    destination_key = output_path.rstrip("/") + "/" + timestamp_str + "_" + file_key.split("/")[-1]
    await s3_move_file(**s3_access, item=file_key, destination=destination_key)


async def s3_list_source(
    api_key: str,
    api_secret: str,
    region: str,
    bucket_name: str,
    prefix: str = None,
    filter: str = None
):

    try:
        # Create S3 client directly
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=api_key,
            aws_secret_access_key=api_secret,
            region_name=region
        )

        # Prepare parameters
        list_params = {
            "Bucket": bucket_name
        }

        cleaned_prefix = (prefix or "").lstrip("/").strip()
        if cleaned_prefix:
            list_params["Prefix"] = cleaned_prefix

        # Call S3
        response = s3_client.list_objects_v2(**list_params)

        if "Contents" not in response:
            return {"files": []}

        files = []

        for obj in response["Contents"]:
            key = obj["Key"]

            # Apply optional filter
            if filter:
                if not fnmatch.fnmatch(key, filter):
                    continue

            files.append({
                "key": key,
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
                "etag": obj.get("ETag"),
            })

        return {"files": files}

    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))

#################################

async def s3_download_file(
    api_key: str,
    api_secret: str,
    region: str,
    bucket_name: str,
    item: str
):

    try:
        # Create S3 client directly
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=api_key,
            aws_secret_access_key=api_secret,
            region_name=region
        )

        # Get object metadata
        metadata = s3_client.head_object(
            Bucket=bucket_name,
            Key=item
        )

        file_size = metadata["ContentLength"]
        last_modified = metadata["LastModified"]
        # Create in-memory file object
        file_object = BytesIO()

        s3_client.download_fileobj(
            Bucket=bucket_name,
            Key=item,
            Fileobj=file_object
        )

        # Move pointer to beginning like a real file
        file_object.seek(0)

        file_object.name = item.split("/")[-1]
        file_object.filename = file_object.name # for compatibility with FileTextExtractor and other file processing functions that expect a filename attribute
        file_object.length = file_size
        file_object.last_modified = last_modified

        return file_object

    except ClientError as e:
        raise Exception(f"S3 download failed: {str(e)}")

#####################
async def s3_move_file(
    api_key: str,
    api_secret: str,
    region: str,
    bucket_name: str,
    item: str,
    destination: str
):
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=api_key,
            aws_secret_access_key=api_secret,
            region_name=region
        )
        s3_client.copy_object(
            Bucket=bucket_name,
            CopySource={'Bucket': bucket_name, 'Key': item},
            Key=destination
        )
        logger.debug(f"Copied processed file {item} to {destination}")

        # Delete original file after copying (MOVE Logic)
        s3_client.delete_object(Bucket=bucket_name, Key=item)
        logger.debug(f"Deleted original file {item} after processing")
    except ClientError as e:
        raise Exception(f"S3 move failed: {str(e)}")

############################################
#  Helper that returns content from the file based on processing mode (none, extract, transcribe, etc.)
############################################

async def get_content_from_file(mode: str, file):
    """
    Reads or processes file content depending on mode.

    mode:
        - 'none'       -> treat as plain text file
        - 'transcribe' -> use whisper to transcribe file (only audio files)
        - 'extract'    -> use FileTextExtractor().extract() to extract text from file (for pdf, docx, etc.)

    Returns:
        str
    """

    try:
        if not file:
            raise ValueError("File is required")

        result = {
                "file_name": file.name,
                "file_size": file.length,
                "last_modified": file.last_modified.astimezone(timezone.utc).isoformat() if file.last_modified else None,
                "content": None,
                "metadata" :{
                    "file_name": file.filename,
                    "file_size": file.length,
                    "last_modified": file.last_modified.astimezone(timezone.utc).isoformat() if file.last_modified else None,
                    "extracttion_mode": mode,
                }
        }
        # Ensure file pointer is at beginning
        if hasattr(file, "seek"):
            file.seek(0)


        # MODE: NONE (plain text)
        if mode == "none":
            content = file.read()

            # If bytes, decode
            if isinstance(content, bytes):
                result["content"] = content.decode("utf-8", errors="ignore")
            else:
                result["content"] = content

            return result


        # MODE: TRANSCRIBE
        elif mode == "transcribe":
            # whisper.transcribe
            the_file = UploadFile(
                filename=file.filename,
                file=file,
                size=file.length,
                headers={"content-type": "application/octet-stream"}
            )
            transcribed_recording = await transcribe_audio_whisper(the_file)

            result["content"] = transcribed_recording.get("text", "")
            result["file_name"] = file.filename
            result["file_size"] = file.length
            result["last_modified"] = file.last_modified.astimezone(timezone.utc).isoformat() if file.last_modified else None,
            result["metadata"] = {
                "file_name": file.filename,
                "file_size": file.length,
                "last_modified": file.last_modified.astimezone(timezone.utc).isoformat() if file.last_modified else None,
                "audio_duration": transcribed_recording.get("audio_duration", None),
                "processing_time": transcribed_recording.get("processing_time", None),
                "model_name": transcribed_recording.get("model_name", None),
                "device": transcribed_recording.get("device", None)
            }


            return result


        # MODE: EXTRACT
        elif mode == "extract":

            result["content"] = FileTextExtractor().extract(file = file)

            return result

        else:
            raise ValueError(f"Unsupported mode: {mode}")

    except Exception as e:
        raise Exception(f"Failed to process file in mode '{mode}': {str(e)}")

