import asyncio
import io
import logging
from datetime import datetime, timezone
from io import BytesIO
from queue import Full
from typing import Optional

from aiohttp import ClientError
from celery import shared_task
from fastapi import HTTPException, UploadFile
from sqlalchemy import null, true

from app.db.seed.seed_data_config import SeedTestData
from app.dependencies.injector import injector
from app.modules.data.providers.vector.chunking import recursive
from app.modules.data.utils.file_extractor import FileTextExtractor
from app.schemas.recording import RecordingCreate
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.audio import AudioService
from app.services.datasources import DataSourceService
from app.services.app_settings import AppSettingsService
from app.services.llm_analysts import LlmAnalystService
from app.services.AzureStorageService import AzureStorageService
from app.services.transcription import transcribe_audio_whisper

logger = logging.getLogger(__name__)


@shared_task
def batch_process_files_kb(kb_id: Optional[str] = None):
    """
    Celery task entry point.
    Runs async summary pipeline for Azure blob files.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(batch_process_files_kb_async_with_scope(kb_id))


async def batch_process_files_kb_async_with_scope(kb_id: Optional[str] = None):
    """Wrapper to run KB batch processing for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        batch_process_files_kb_async,
        "KB batch processing",
        kb_id=kb_id
    )


async def batch_process_files_kb_async(kb_id: Optional[str] = None):
    dsService = injector.get(DataSourceService)
    llmService = injector.get(LlmAnalystService)
    kbService = injector.get(KnowledgeBaseService)

    # If kb_id is provided, process only that KB's datasource; otherwise, process all active Azure Blob datasources
    kb_items = []
    if kb_id:
        kb_item = await kbService.get_by_id(kb_id)
        kb_items = [kb_item]
    else:
        # kb_items = await kbService.get_all()
        pass # For now, only support single KB processing via kb_id since it is locking celery jobs. 
        # in frontend of KB has ven added buton Sync Now to manually triger this task
        # Full batch processing will be implemented in the future.

    count_kbs = len(kb_items)
    count_success = 0
    count_skipped = 0
    count_fail = 0
    files_processed = []

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
            continue


        conn = ds_item.connection_data
        logger.info(f"Processing {ds_item.source_type} Datasource: {ds_item.name} for KB: {kb_item.name}")

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
            prefix_input_folder = conn.get("prefix", "") 
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

            for s3_file in s3_files.get("files", []):
                if s3_file.get("size", 0) == 0:
                    logger.info(f"Skipping empty file: {s3_file['key']}")
                    continue
                file_content = await s3_download_file(
                    api_key = keyid_username, 
                    api_secret = secret_password, 
                    region = region, 
                    bucket_name = bucket_server, 
                    item = s3_file["key"]
                )

                print(f"Downloaded file {s3_file['key']} with size {s3_file['size']} bytes")

                extracted_content = await get_content_from_file(mode=processing_mode, file=file_content)

                print(f"Extracted Content for file {s3_file['key']}: \n\n{extracted_content}")

                # if RAG enabled, chunk and vectorize content, and save to vector database
                if vector_enabled and extracted_content.get("content", None):
                    chunks = []
                    if chunk_strategy == "recursive":
                        separators = [s.strip() for s in chunk_separators.split(",")]
                        chunks = recursive(
                            text=extracted_content["content"],
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap,
                            separators=separators,
                            keep_separator=chunk_keep_separator,
                            strip_whitespace=chunk_strip_whitespace
                        )
                    else:
                        logger.warning(f"Unsupported chunk strategy: {chunk_strategy}. Skipping chunking.")
                        chunks = [extracted_content["content"]]

                    ###### Add other chunking strategies here (semantic, simple, etc.) ######

                    # Vectorize chunks and save to vector database




        elif ds_item.type == "azure_blob":
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
        "total_kbs": count_kbs,
        "processed_kbs": count_success,
        "failed_kb": count_fail,
        "skipped_kbs": count_skipped,
        "files": files_processed
    }




############################################
#  S3 Helper  FUnctions (to be moved to a separate module)
############################################
import boto3
import fnmatch
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

        if prefix:
            list_params["Prefix"] = prefix

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
                "last_modified": obj["LastModified"]
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
                "last_modified": file.last_modified,
                "content": None
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
           
            result["content"] = transcribed_recording

            return result


        # MODE: EXTRACT
        elif mode == "extract":

            result["content"] = FileTextExtractor().extract(file = file)

            return result

        else:
            raise ValueError(f"Unsupported mode: {mode}")

    except Exception as e:
        raise Exception(f"Failed to process file in mode '{mode}': {str(e)}")

