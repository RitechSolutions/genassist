from fastapi import APIRouter, HTTPException, Query, Depends, Body, UploadFile, File, logger
from typing import List, Dict, Any, Optional
import os
import uuid
import shutil
from pathlib import Path

from app.genagent.agents.data.datasource_service import DataSourceService
from app.genagent.models.knowledge import KnowledgeItem
from app.genagent.services.knowledge_service import KnowledgeService
from app.genagent.core.dependencies import get_datasource_service, get_knowledge_service
import logging
logger = logging.getLogger(__name__)
router = APIRouter()
import asyncio
# Define upload directory
UPLOAD_DIR = "agents_config/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/items", response_model=List[KnowledgeItem])
async def get_all_knowledge_items(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """Get all knowledge base items"""
    items = await knowledge_service.get_all_items()
    return items

@router.get("/items/{item_id}", response_model=KnowledgeItem)
async def get_knowledge_item_by_id(
    item_id: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """Get a specific knowledge base item by ID"""
    item = await knowledge_service.get_item_by_id(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail=f"Knowledge base item with ID {item_id} not found")
    return item

@router.post("/items", response_model=KnowledgeItem)
async def create_knowledge_item(
    item: KnowledgeItem = Body(...),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    datasource_service: DataSourceService = Depends(get_datasource_service)     
):
    """Create a new knowledge base item"""
    # Check if item with this ID already exists
    existing = await knowledge_service.get_item_by_id(item.id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Knowledge base item with ID {item.id} already exists")
    
    result = await knowledge_service.create_item(item)
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create knowledge base item")
    
    asyncio.create_task(datasource_service.load_knowledge_base([result]))

    return result

@router.put("/items/{item_id}", response_model=KnowledgeItem)
async def update_knowledge_item(
    item_id: str,
    item: KnowledgeItem = Body(...),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    datasource_service: DataSourceService = Depends(get_datasource_service)
):
    logger.info(f"update_knowledge_item route : item_id = {item_id}")
    """Update an existing knowledge base item"""
    # Check if item exists
    existing = await knowledge_service.get_item_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Knowledge base item with ID {item_id} not found")
    
    # Ensure the ID in the path matches the ID in the body
    if "id" in item and item.id != item_id:
        raise HTTPException(status_code=400, detail="ID in path must match ID in body")
    logger.info(f"update_knowledge_item route trigger : item = {item}")
    result = await knowledge_service.update_item(item_id, item)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update knowledge base item")
    
    asyncio.create_task(datasource_service.load_knowledge_base([result]))

    return result

@router.delete("/items/{item_id}", response_model=Dict[str, str])
async def delete_knowledge_item(
    item_id: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    datasource_service: DataSourceService = Depends(get_datasource_service)
):
    """Delete a knowledge base item"""
    # Check if item exists
    existing = await knowledge_service.get_item_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Knowledge base item with ID {item_id} not found")
    
    result = await knowledge_service.delete_item(item_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete knowledge base item")
    
    asyncio.create_task(datasource_service.delete_knowledge_base_item(item_id))

    return {"status": "success", "message": f"Knowledge base item with ID {item_id} deleted"}

@router.post("/upload", response_model=Dict[str, str])
async def upload_file(
    file: UploadFile = File(...),
):
    """
    Upload a file and return the saved filename
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
        
        # Return the filename and path
        result = {
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_path": file_path
        }
        logger.info(f"Upload successful: {result}")
        return result
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}") 