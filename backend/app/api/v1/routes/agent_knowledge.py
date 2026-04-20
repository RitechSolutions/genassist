import logging
import os
import shutil
import uuid
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.config.settings import file_storage_settings
from app.core.config.settings import settings as project_settings
from app.core.project_path import DATA_VOLUME
from app.core.tenant_scope import get_tenant_context
from app.core.utils.bi_utils import set_url_content_if_no_rag
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.data.providers.legra import (
    FaissFlatIndexer,
    HuggingFaceGenerator,
    Legra,
    LeidenClusterer,
    SemanticChunker,
    SentenceTransformerEmbedder,
)
from app.modules.data.utils import FileExtractor, FileTextExtractor
from app.modules.workflow.agents.rag import ThreadScopedRAG
from app.schemas.agent_knowledge import KBBase, KBCreate, KBListItem, KBRead
from app.schemas.common import PaginatedResponse
from app.schemas.dynamic_form_schemas import AGENT_RAG_FORM_SCHEMAS_DICT
from app.schemas.file import FileBase, FileUploadResponse
from app.schemas.filter import BaseFilterModel
from app.schemas.knowledge_upload import (
    KbUploadSessionCreate,
    KbUploadSessionCreateResponse,
    KbUploadSessionStatusResponse,
)
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.agent_knowledge_utils import (
    populate_remote_file_metadata,
    schedule_rag_load,
)
from app.services.app_settings import AppSettingsService

# File manager service
from app.services.file_manager import FileManagerService
from app.services.file_upload_session import FileUploadSessionService
from app.tasks.kb_batch_tasks import batch_process_files_kb_async_with_scope
from app.tasks.s3_tasks import import_s3_files_to_kb_async

router = APIRouter()
logger = logging.getLogger(__name__)

# Helper functions removed - now using simplified manager interface
# Define upload directory
UPLOAD_DIR = str(DATA_VOLUME / "agents_config/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
# TODO set permission validation


@router.get(
    "/items",
    response_model=List[KBRead],
    dependencies=[
        Depends(auth),
    ],
)
async def get_all_knowledge_items(
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
):
    """Get all knowledge base items"""
    items = await knowledge_service.get_all()
    return items


@router.get(
    "/list",
    response_model=PaginatedResponse[KBListItem],
    dependencies=[Depends(auth)],
)
async def get_knowledge_items_list(
    filter_obj: BaseFilterModel = Depends(),
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
):
    """Paginated KB list — optimized for performance (minimal fields only)."""
    return await knowledge_service.get_list_paginated(filter_obj)


@router.get(
    "/items/{item_id}",
    response_model=KBRead,
    dependencies=[
        Depends(auth),
    ],
)
async def get_knowledge_item_by_id(
    item_id: UUID,
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
):
    """Get a specific knowledge base item by ID"""
    item = await knowledge_service.get_by_id(item_id)

    if not item:
        raise HTTPException(
            status_code=404, detail=f"Knowledge base item with ID {item_id} not found"
        )
    return item


@router.post(
    "/items",
    response_model=KBRead,
    dependencies=[
        Depends(auth),
    ],
)
async def create_knowledge_item(
    item: KBCreate = Body(...),
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
    rag_manager: AgentRAGServiceManager = Injected(AgentRAGServiceManager),
    file_manager_service: FileManagerService = Injected(FileManagerService),
):
    """Create a new knowledge base item"""
    # store url content as text in content field if all rag stores are False
    if item.type == "url":
        await set_url_content_if_no_rag(item)

    result = await knowledge_service.create(item)

    # Enrich files with storage metadata when using remote providers (S3, etc.)
    await populate_remote_file_metadata(result, file_manager_service)

    # Load knowledge item using simplified manager in the background
    schedule_rag_load(rag_manager, result, action="create")
    return result


@router.put(
    "/items/{item_id}",
    response_model=KBRead,
    dependencies=[
        Depends(auth),
    ],
)
async def update_knowledge_item(
    item_id: UUID,
    item: KBBase = Body(...),
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
    rag_manager: AgentRAGServiceManager = Injected(AgentRAGServiceManager),
    file_manager_service: FileManagerService = Injected(FileManagerService),
):
    logger.info(f"update_knowledge_item route : item_id = {item_id}")
    """Update an existing knowledge base item"""
    # Check if item exists
    await knowledge_service.get_by_id(item_id)

    # Ensure the ID in the path matches the ID in the body
    if "id" in item and item.id != item_id:
        raise HTTPException(
            status_code=400, detail="ID in path must match ID in body")

    logger.info(f"update_knowledge_item route trigger : item = {item}")

    # store url content as text in content field if all rag stores are False
    if item.type == "url":
        await set_url_content_if_no_rag(item)

    result = await knowledge_service.update(item_id, item)

    # Enrich files with storage metadata when using remote providers (S3, etc.)
    await populate_remote_file_metadata(result, file_manager_service)

    # Load knowledge item using simplified manager
    schedule_rag_load(rag_manager, result, action="update")
    return result


@router.delete(
    "/items/{kb_id}",
    response_model=Dict[str, str],
    dependencies=[
        Depends(auth),
    ],
)
async def delete_knowledge(
    kb_id: UUID,
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
    rag_manager: AgentRAGServiceManager = Injected(AgentRAGServiceManager),
    file_manager_service: FileManagerService = Injected(FileManagerService),
):
    """Delete a knowledge base item"""
    # Check if item exists
    kb = await knowledge_service.get_by_id(kb_id)

    # Delete all documents from knowledge base using simplified manager
    doc_ids = await rag_manager.get_document_ids(kb)
    for doc_id in doc_ids:
        await rag_manager.delete_document(kb, doc_id)

    # Delete all files from file manager service
    if kb.files and len(kb.files) > 0:
        for file in kb.files:
            if isinstance(file, dict) and file.get("file_id"):
                file_id = file.get("file_id")
                await file_manager_service.delete_file(UUID(str(file_id)))

    await knowledge_service.delete(kb_id)

    return {"status": "success", "message": f"Knowledge base with ID {kb_id} deleted"}


@router.delete(
    "/items/{kb_id}/{doc_id}",
    response_model=Dict[str, str],
    dependencies=[
        Depends(auth),
    ],
)
async def delete_knowledge_doc(
    kb_id: UUID,
    doc_id: str,
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
    rag_manager: AgentRAGServiceManager = Injected(AgentRAGServiceManager),
):
    """Delete a knowledge base item"""
    kb_read = await knowledge_service.get_by_id(kb_id)

    # Delete document using simplified manager
    await rag_manager.delete_document(kb_read, doc_id)

    return {
        "status": "success",
        "message": f"Doc {doc_id} deleted from knowledge base with ID {kb_id}",
    }


@router.post(
    "/upload",
    response_model=List[Dict[str, str]],
    dependencies=[
        Depends(auth),
    ],
)
async def upload_file(
    request: Request,
    files: List[UploadFile] = File(...),
    file_manager_service: FileManagerService = Injected(FileManagerService),
    app_settings_svc: AppSettingsService = Injected(AppSettingsService),
):
    """
    Upload multiple files, extract their text content, and return saved filenames and paths.
    """
    results = []
    logger.info(f"Starting upload of {len(files)} files.")

    max_kb = project_settings.KNOWLEDGE_MAX_UPLOAD_BYTES
    use_file_manager = file_storage_settings.FILE_MANAGER_ENABLED
    storage_provider = None
    app_settings_config = None
    if use_file_manager:
        app_settings_config = await app_settings_svc.get_by_type_and_name(
            "FileManagerSettings", "File Manager Settings"
        )
        storage_provider = await file_manager_service.initialize(
            base_url=str(request.base_url).rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_settings_config,
        )

    for file in files:
        try:
            logger.info(
                f"Received file upload: {file.filename}, size: {file.size}, content_type: {file.content_type}"
            )

            if file.size is not None and file.size > max_kb:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds maximum allowed size ({max_kb} bytes).",
                )

            # Generate a unique filename
            file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
            unique_filename = (f"{uuid.uuid4()}.{file_extension}" if file_extension else f"{uuid.uuid4()}")

            # create the result object
            result = {
                "filename": unique_filename,
                "original_filename": file.filename,
            }

            if use_file_manager and storage_provider:
                sub_folder = "agents_config/uploads"
                file_base = FileBase(
                    name=unique_filename,
                    storage_path=storage_provider.get_base_path(),
                    path=sub_folder,
                    storage_provider=storage_provider.name,
                    file_extension=file_extension,
                )

                created_file = await file_manager_service.create_file(
                    file=file,
                    file_base=file_base,
                    max_file_size=max_kb,
                )
                file_id = str(created_file.id)
                file_url = await file_manager_service.get_file_source_url(created_file.id)

                result["file_type"] = "url"
                result["file_url"] = file_url
                result["file_id"] = file_id

                if created_file.storage_provider == "local":
                    result["file_path"] = f"{created_file.storage_path}/{created_file.path}"
            else:
                # create the file path where the file will be saved
                file_path = os.path.join(str(UPLOAD_DIR), unique_filename)
                # add the file_path to the result
                result["file_path"] = file_path

                # save the file to the upload directory
                logger.info(f"Saving file to: {file_path}")

                # Save the file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                logger.info(f"Extracting text from file: {file_path}")

            logger.info(f"Upload successful: {result}")
            results.append(result)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error uploading file: {str(e)}")

    logger.info(f"All uploads successful: {results}")
    return results


@router.post(
    "/upload-session",
    response_model=KbUploadSessionCreateResponse,
    dependencies=[Depends(auth)],
)
async def create_kb_upload_session(
    payload: KbUploadSessionCreate,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
):
    """Start a chunked upload for a single large file (backward compatible with /upload)."""
    try:
        created = await svc.create_session(
            payload.original_filename,
            payload.expected_size,
            payload.content_type,
        )
        return KbUploadSessionCreateResponse(
            session_id=created.session_id,
            max_chunk_bytes=created.max_chunk_bytes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/upload-session/{session_id}/chunk",
    dependencies=[Depends(auth)],
)
async def kb_upload_session_chunk(
    session_id: UUID,
    chunk: UploadFile = File(...),
    chunk_index: int = Form(0),
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
):
    """Append one chunk to a staged upload session."""
    try:
        data = await chunk.read()
        total = await svc.append_chunk(session_id, data, chunk_index)
        return {"status": "ok", "bytes_received": total}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/upload-session/{session_id}/complete",
    response_model=Dict[str, str],
    dependencies=[Depends(auth)],
)
async def kb_upload_session_complete(
    session_id: UUID,
    request: Request,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
    file_manager_service: FileManagerService = Injected(FileManagerService),
    app_settings_svc: AppSettingsService = Injected(AppSettingsService),
):
    """Finalize staged bytes into storage + files row (same shape as one legacy /upload item)."""
    try:
        return await svc.complete_session(
            session_id,
            request,
            file_manager_service,
            app_settings_svc,
            sub_folder="agents_config/uploads",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/upload-session/{session_id}",
    response_model=KbUploadSessionStatusResponse,
    dependencies=[Depends(auth)],
)
async def kb_upload_session_status(
    session_id: UUID,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
):
    try:
        s = await svc.get_status(session_id)
        return KbUploadSessionStatusResponse(
            id=s.id,
            status=s.status,
            bytes_received=s.bytes_received,
            expected_bytes=s.expected_bytes,
            error_message=s.error_message,
            result=s.result,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/upload-chat-file",
    response_model=FileUploadResponse,
    dependencies=[
        Depends(auth),
    ]
)
async def upload_file_to_chat(
    request: Request,
    chat_id: str = Form(...),
    file: UploadFile = File(...),
    file_manager_service: FileManagerService = Injected(FileManagerService),
    app_settings_svc: AppSettingsService = Injected(AppSettingsService),
):
    """
    Upload a file, extract its text content, and return both the saved filename and extracted text file
    """
    try:
        logger.info(
            f"Received file upload: {file.filename}, size: {file.size}, content_type: {file.content_type}"
        )

        # file storage settings
        app_settings_config = await app_settings_svc.get_by_type_and_name("FileManagerSettings", "File Manager Settings")
        storage_provider = await file_manager_service.initialize(base_url=str(request.base_url).rstrip('/'), base_path=str(DATA_VOLUME), app_settings = app_settings_config)

        file_url = None

        try:
            file_base = FileBase(
                name=file.filename,
                path=f"agents_config/upload-chat-files/{chat_id}",
                storage_path=storage_provider.get_base_path(),
                storage_provider=storage_provider.name,
                file_extension=file.filename.split(".")[-1] if "." in file.filename else "",
            )

            # create file in file manager service
            created_file = await file_manager_service.create_file(
                file,
                file_base=file_base,
                allowed_extensions=["pdf", "docx", "txt", "jpg", "jpeg", "png"],
            )

            file_url = await file_manager_service.get_file_url(created_file)
        except Exception as e:
            logger.error(f"Error creating file: {str(e)}")
            raise HTTPException(
                status_code=400, detail="Unsupported file type. Only PDF, DOCX, TXT, JPG, JPEG, and PNG are allowed.") from e

        # get file id from created file
        file_id = created_file.id
        file_extension = created_file.file_extension
        storage_path = created_file.storage_path
        file_path = f"{storage_path}/{created_file.path}"

        logger.debug(f"File Id: {file_id}")

        # Extract text from the file
        try:
            # Download file content via the service so it works with any storage provider (local, S3, etc.)
            # file_content = await file_manager_service.get_file_content(created_file)

            if file_extension.lower() in ["jpg", "jpeg", "png"]:
                _file, file_content_bytes = await file_manager_service.download_file(created_file.id)
                extracted_text = FileExtractor.extract_from_image_bytes(file_content_bytes)
            else:
                _file, file_content_bytes = await file_manager_service.download_file(created_file.id)
                extracted_text = FileTextExtractor().extract(
                    filename=created_file.name or file.filename,
                    content=file_content_bytes,
                )
            from app.dependencies.injector import injector

            # add file content to thread rag using workflow engine
            thread_rag = injector.get(ThreadScopedRAG)
            await thread_rag.add_file_content(
                chat_id=chat_id,
                file_content=extracted_text,
                file_name=file.filename or "unknown",
                file_id=file_id,
            )

        except Exception as e:
            logger.warning(f"Could not extract text from file: {str(e)}")


        # Return the filenames and paths
        result = FileUploadResponse(
            filename=str(file_id),
            original_filename=file.filename,
            storage_path=storage_path,
            file_path=file_path,
            file_url=file_url,
            file_id=str(file_id),
        )

        logger.debug(f"Upload successful: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get(
    "/run-s3-file-sync/{item_id}",
    dependencies=[
        Depends(auth),
    ],
)
async def run_sync_kb(
    item_id: Optional[UUID] = None,
):
    res = await import_s3_files_to_kb_async(item_id)
    return res


@router.post(
    "/search",
    response_model=List[Dict[str, str]] | str,
    dependencies=[
        Depends(auth),
    ],
)
async def search(
    query: str = Body(...),
    items: List[KBRead] = Body(...),
    rag_manager: AgentRAGServiceManager = Injected(AgentRAGServiceManager),
):
    logger.debug(f"search route : query = {query}")

    # Search using simplified manager
    results = await rag_manager.search(items, query, limit=5, format_results=True)

    if not results:
        logger.debug(f"No results found for query: {query}")
        return []

    return results


@router.post("/finalize/{kb_id}", dependencies=[Depends(auth)])
async def finalize_legra_knowledgebase(
    kb_id: UUID,
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
    rag_manager: AgentRAGServiceManager = Injected(AgentRAGServiceManager),
):
    logger.info(f"finalizing knowledge base : kb_id = {kb_id}")
    knowledge_base = await knowledge_service.get_by_id(kb_id)

    # Finalize LEGRA using simplified manager
    success = await rag_manager.finalize_legra(knowledge_base)

    if success:
        # Update knowledge base to mark LEGRA as finalized
        knowledge_base.legra_finalize = True
        await knowledge_service.update(
            knowledge_base.id, KBCreate(
                **knowledge_base.model_dump(exclude={"id"}))
        )
        return {
            "status": "success",
            "message": f"LEGRA finalization completed for KB {kb_id}",
        }
    else:
        return {
            "status": "error",
            "message": f"LEGRA finalization failed for KB {kb_id}",
        }


@router.post(
    "/process-files",
    dependencies=[Depends(auth), Depends(
        permissions("update:knowledge_base"))],
)
async def process_files(files: list[UploadFile] = File(...)):

    chunker = SemanticChunker(
        min_sents=1,
        max_sents=30,
        min_sent_length=32,
    )
    embedder = SentenceTransformerEmbedder(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    indexer = FaissFlatIndexer(dim=embedder.dimension, use_gpu=False)

    clusterer = LeidenClusterer(resolution_parameter=0.5)

    hf_gen = HuggingFaceGenerator(
        model_name="gpt2",
        device="cpu",
        truncate_context_size=1024,
    )
    rag = Legra(
        doc_folder="",
        chunker=chunker,
        embedder=embedder,
        indexer=indexer,
        clusterer=clusterer,
        generator=hf_gen,
        max_tokens=1024,
    )
    rag.index(files)

    return {"message": "success"}


@router.get(
    "/form_schemas",
    dependencies=[
        Depends(auth),
    ],
)
async def get_form_schemas():
    """Get supported RAG configuration schemas."""
    return AGENT_RAG_FORM_SCHEMAS_DICT



# Endpoint to trigger KB batch processing (S3, Azure Blob, SharePoint, Zendesk, etc.)
@router.get(
    "/kb-batch-tasks-execution",
    dependencies=[Depends(auth)],
    summary="Runs the job that syncs the KB with files or Zendesk articles for this tenant",
)
async def summarize_files_from_azure(
    kb_id: Optional[UUID] = None,
):
    if not kb_id:
        logger.warning("Attempting to run KB batch processing without specifying a KB ID.")
        return {"status": "error", "message": "kb_id is required"}

    tenant_id = get_tenant_context()
    # Await inline so the response includes batch results (Zendesk counts, file lists, etc.).
    # Previously this used BackgroundTasks + Celery for Zendesk only, so the client saw
    # {"status": "started"} while real metrics appeared only in worker logs.
    batch_result = await batch_process_files_kb_async_with_scope(
        kb_id=str(kb_id),
        tenant_id=tenant_id,
    )
    return {"status": "completed", **batch_result}
