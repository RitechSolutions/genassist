from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File, Form
from typing import List, Dict, Optional
import os
import uuid
import shutil
from fastapi_injector import Injected
from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.bi_utils import set_url_content_if_no_rag
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.data.utils import FileExtractor, FileTextExtractor
import logging
from uuid import UUID
from app.modules.data.providers.legra import (
    FaissFlatIndexer,
    HuggingFaceGenerator,
    Legra,
    LeidenClusterer,
    SemanticChunker,
    SentenceTransformerEmbedder,
)
from app.schemas.agent_knowledge import KBBase, KBCreate, KBRead
from app.services.agent_knowledge import KnowledgeBaseService
import asyncio
from app.tasks.s3_tasks import import_s3_files_to_kb_async
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.agents.rag import ThreadScopedRAG
from app.schemas.dynamic_form_schemas import AGENT_RAG_FORM_SCHEMAS_DICT
# File manager service
from app.services.file_manager import FileManagerService
from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.schemas.file import FileUploadResponse

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
):
    """Create a new knowledge base item"""
    # store url content as text in content field if all rag stores are False
    if item.type == "url":
        await set_url_content_if_no_rag(item)

    result = await knowledge_service.create(item)

    # Load knowledge item using simplified manager
    asyncio.create_task(rag_manager.load_knowledge_items(
        [result], action="create"))

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

    # Load knowledge item using simplified manager
    _ = asyncio.create_task(
        rag_manager.load_knowledge_items([result], action="update"))

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
):
    """Delete a knowledge base item"""
    # Check if item exists
    kb = await knowledge_service.get_by_id(kb_id)

    # Delete all documents from knowledge base using simplified manager
    doc_ids = await rag_manager.get_document_ids(kb)
    for doc_id in doc_ids:
        await rag_manager.delete_document(kb, doc_id)

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
    files: List[UploadFile] = File(...),
):
    """
    Upload multiple files, extract their text content, and return saved filenames and paths.
    """
    results = []
    logger.info(f"Starting upload of {len(files)} files.")
    for file in files:
        try:
            logger.info(
                f"Received file upload: {file.filename}, size: {file.size}, content_type: {file.content_type}"
            )

            # Generate a unique filename
            file_extension = file.filename.split(
                ".")[-1] if "." in file.filename else ""
            unique_filename = (
                f"{uuid.uuid4()}.{file_extension}" if file_extension else f"{uuid.uuid4()}"
            )
            file_path = os.path.join(UPLOAD_DIR, unique_filename)

            logger.info(f"Saving file to: {file_path}")

            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Extract text from the file
            extracted_text = FileTextExtractor().extract_from_path(path=file_path)
            if not extracted_text:
                raise AppException(ErrorKey.ERROR_EXTRACTING_FROM_FILE)

            # Return the filenames and paths
            result = {
                "filename": unique_filename,
                "original_filename": file.filename,
                "file_path": file_path,
            }
            logger.info(f"Upload successful: {result}")
            results.append(result)
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error uploading file: {str(e)}")

    logger.info(f"All uploads successful: {results}")
    return results


@router.post(
    "/upload-chat-file",
    response_model=FileUploadResponse,
    dependencies=[
        Depends(auth),
    ]
)
async def upload_file_to_chat(
    chat_id: str = Form(...),
    file: UploadFile = File(...),
    file_manager_service: FileManagerService = Injected(FileManagerService),
):
    """
    Upload a file, extract its text content, and return both the saved filename and extracted text file
    """
    try:
        logger.info(
            f"Received file upload: {file.filename}, size: {file.size}, content_type: {file.content_type}"
        )

        # Introduce file manager service and set the storage provider to local file system
        await file_manager_service.set_storage_provider(LocalFileSystemProvider(config={"base_path": UPLOAD_DIR}))

        try:
            # create file in file manager service
            created_file = await file_manager_service.create_file(
                file,
                allowed_extensions=["pdf", "docx", "txt", "jpg", "jpeg", "png"],
            )
        except Exception as e:
            logger.error(f"Error creating file: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type. Only PDF, DOCX, TXT, JPG, JPEG, and PNG are allowed.") from e

        # get file id from created file
        file_id = created_file.id
        file_extension = created_file.file_extension
        storage_path = created_file.storage_path
        file_path = f"{UPLOAD_DIR}/{storage_path}"

        logger.debug(f"File Id: {file_id}")

        # Extract text from the file
        try:
            if file_extension.lower() == "pdf":
                extracted_text = FileExtractor.extract_from_pdf(file_path)
            elif file_extension.lower() == "docx":
                extracted_text = FileExtractor.extract_from_docx(file_path)
            elif file_extension.lower() in ["jpg", "jpeg", "png"]:
                extracted_text = FileExtractor.extract_from_image(file_path)
            else:  # Assume text file
                extracted_text = FileExtractor.extract_from_txt(file_path)
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

        file_relative_url = f"/api/file-manager/files/{file_id}/source"

        # Return the filenames and paths
        result = FileUploadResponse(
            filename=str(file_id),
            original_filename=file.filename,
            storage_path=storage_path,
            file_path=file_path,
            file_url=file_relative_url,
            file_id=str(file_id),
        )

        logger.debug(f"Upload successful: {result}")
        return result
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
    logger.info(f"search route : query = {query}")

    # Search using simplified manager
    results = await rag_manager.search(items, query, limit=5, format_results=True)

    if not results:
        logger.info(f"No results found for query: {query}")
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
    "/process-files/",
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
