from fastapi import APIRouter, Query, HTTPException, Depends
from app.genagent.agents.data.datasource_service import DataSourceService
from app.genagent.core.dependencies import get_knowledge_service, get_datasource_service

router = APIRouter()
knowledge_service = get_knowledge_service()

@router.get("/")
async def search_knowledge(
    query: str = Query(..., description="Search query"),
    limit: int = Query(5, description="Maximum number of results to return"),
    datasource_service: DataSourceService = Depends(get_datasource_service)
):
    """
    Search the knowledge base using vector and graph databases
    
    This endpoint performs semantic search across all knowledge base items
    using both vector similarity and graph relationships.
    """
    try:
        results = await datasource_service.search_knowledge(query, limit)
        return {
            "query": query,
            "results_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@router.post("/initialize")
async def initialize_datasources(
    datasource_service: DataSourceService = Depends(get_datasource_service)
):
    """
    Initialize all data sources with the knowledge base
    
    This endpoint loads all knowledge base items into the configured
    data sources (vector DB, graph DB, etc.)
    """
    try:
        success = await datasource_service.load_knowledge_base()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to initialize data sources")
        return {"message": "Data sources initialized successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization error: {str(e)}") 