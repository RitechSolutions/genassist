from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File
from typing import List, Dict
import os
import uuid
import shutil
import textract
import logging

<<<<<<< HEAD
from app.modules.agents.data.datasource_service import DataSourceService
from app.dependencies.agents import get_datasource_service
=======
from app.auth.dependencies import auth
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.dependencies.agents import get_agent_datasource_service
>>>>>>> development
import logging
from uuid import UUID
from app.schemas.agent_knowledge import KBBase, KBRead
from app.services.agent_knowledge import KnowledgeBaseService
import asyncio



router = APIRouter()
logger = logging.getLogger(__name__)
# Define upload directory
UPLOAD_DIR = "agents_config/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
<<<<<<< HEAD

@router.get("/items", response_model=List[KBRead])
=======
# TODO set permission validation



@router.get("/items", response_model=List[KBRead], dependencies=[
    Depends(auth),
    ])
>>>>>>> development
async def get_all_knowledge_items(
    knowledge_service: KnowledgeBaseService = Depends()
):
    """Get all knowledge base items"""
    items = await knowledge_service.get_all()
    return items

<<<<<<< HEAD
@router.get("/items/{item_id}", response_model=KBRead)
=======
@router.get("/items/{item_id}", response_model=KBRead,
            dependencies=[
                Depends(auth),
                ]
            )
>>>>>>> development
async def get_knowledge_item_by_id(
    item_id: UUID,
    knowledge_service: KnowledgeBaseService = Depends()
):
    """Get a specific knowledge base item by ID"""
    item = await knowledge_service.get_by_id(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail=f"Knowledge base item with ID {item_id} not found")
    return item

<<<<<<< HEAD
@router.post("/items", response_model=KBRead)
async def create_knowledge_item(
    item: KBBase = Body(...),
    knowledge_service: KnowledgeBaseService = Depends(),
    datasource_service: DataSourceService = Depends(get_datasource_service)     
=======
@router.post("/items", response_model=KBRead, dependencies=[
    Depends(auth),
    ])
async def create_knowledge_item(
    item: KBBase = Body(...),
    knowledge_service: KnowledgeBaseService = Depends(),
    datasource_service: AgentDataSourceService = Depends(get_agent_datasource_service)
>>>>>>> development
):
    """Create a new knowledge base item"""
    result = await knowledge_service.create(item)

    asyncio.create_task(datasource_service.load_knowledge_base([result]))

    return result

<<<<<<< HEAD
@router.put("/items/{item_id}", response_model=KBRead)
=======
@router.put("/items/{item_id}", response_model=KBRead, dependencies=[
    Depends(auth),
    ])
>>>>>>> development
async def update_knowledge_item(
    item_id: UUID,
    item: KBBase = Body(...),
    knowledge_service: KnowledgeBaseService = Depends(),
<<<<<<< HEAD
    datasource_service: DataSourceService = Depends(get_datasource_service)
=======
    datasource_service: AgentDataSourceService = Depends(get_agent_datasource_service)
>>>>>>> development
):
    logger.info(f"update_knowledge_item route : item_id = {item_id}")
    """Update an existing knowledge base item"""
    # Check if item exists
    await knowledge_service.get_by_id(item_id)

    # Ensure the ID in the path matches the ID in the body
    if "id" in item and item.id != item_id:
        raise HTTPException(status_code=400, detail="ID in path must match ID in body")

    logger.info(f"update_knowledge_item route trigger : item = {item}")
    result = await knowledge_service.update(item_id, item)

    asyncio.create_task(datasource_service.load_knowledge_base([result]))

    return result

<<<<<<< HEAD
@router.delete("/items/{item_id}", response_model=Dict[str, str])
async def delete_knowledge_item(
    item_id: UUID,
    knowledge_service: KnowledgeBaseService = Depends(),
    datasource_service: DataSourceService = Depends(get_datasource_service)
):
    """Delete a knowledge base item"""
    # Check if item exists
    await knowledge_service.get_by_id(item_id)
    await knowledge_service.delete(item_id)
    asyncio.create_task(datasource_service.delete_knowledge_base_item(item_id))

    return {"status": "success", "message": f"Knowledge base item with ID {item_id} deleted"}

@router.post("/upload", response_model=Dict[str, str])
=======
@router.delete("/items/{kb_id}", response_model=Dict[str, str], dependencies=[
    Depends(auth),
    ])
async def delete_knowledge(
    kb_id: UUID,
    knowledge_service: KnowledgeBaseService = Depends(),
    agent_datasource_service: AgentDataSourceService = Depends(get_agent_datasource_service)
):
    """Delete a knowledge base item"""
    # Check if item exists
    kb = await knowledge_service.get_by_id(kb_id)
    await agent_datasource_service.delete_kb(kb)
    await knowledge_service.delete(kb_id)

    return {"status": "success", "message": f"Knowledge base with ID {kb_id} deleted"}


@router.delete("/items/{kb_id}/{doc_id}", response_model=Dict[str, str], dependencies=[
    Depends(auth),
    ])
async def delete_knowledge_doc(
    kb_id: UUID,
    doc_id: UUID,
    knowledge_service: KnowledgeBaseService = Depends(),
    agent_datasource_service: AgentDataSourceService = Depends(get_agent_datasource_service)
):
    """Delete a knowledge base item"""
    await agent_datasource_service.delete_doc(str(kb_id), str(doc_id))

    return {"status": "success", "message": f"Doc {doc_id} deleted from knowledge base with ID {kb_id}"}

@router.post("/upload", response_model=Dict[str, str], dependencies=[
    Depends(auth),
    ])
>>>>>>> development
async def upload_file(
    file: UploadFile = File(...),
):
    """
    Upload a file, extract its text content, and return both the saved filename and extracted text file
    """
    try:
        logger.info(f"Received file upload: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Generate a unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else f"{uuid.uuid4()}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        logger.info(f"Saving file to: {file_path}")
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract text from the file
        try:
            extracted_text = textract.process(file_path)
            # Save extracted text to a new file
            text_filename = f"{unique_filename}_text.txt"
            text_file_path = os.path.join(UPLOAD_DIR, text_filename)
            with open(text_file_path, "wb") as text_file:
                text_file.write(extracted_text)
        except Exception as e:
            logger.warning(f"Could not extract text from file: {str(e)}")
            text_filename = None
            text_file_path = None
        
        # Return the filenames and paths
        result = {
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_path": text_file_path if text_file_path else file_path,
            # "text_filename": text_filename,
            # "text_file_path": text_file_path
        }
        logger.info(f"Upload successful: {result}")
        return result
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}") 