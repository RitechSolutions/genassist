from fastapi import APIRouter
from app.genagent.api.routes import  agents, config, knowledge, tools

router = APIRouter()

# Include all route modules
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(config.router, prefix="/agents", tags=["agents"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Base"])
router.include_router(tools.router, prefix="/tools", tags=["Tools"]) 