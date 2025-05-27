from typing import Dict, Any
import logging


from app.modules.agents.workflow.builder import WorkflowBuilder
from app.schemas.workflow import WorkflowUpdate

logger = logging.getLogger(__name__)

class WorkflowRunner:
    """Runner for executing workflows from database models or configurations"""
    
    @staticmethod
    async def run_workflow(workflow_id: str, user_query: str, metadata: dict = None) -> Dict[str, Any]:
        """Run a workflow by ID"""
        from app.repositories.workflow import WorkflowRepository
        from app.db.session import async_session_maker
        
        async with async_session_maker() as s:
            repository = WorkflowRepository(s)
            workflow = await repository.get_by_id(workflow_id)
            
            if not workflow:
                return {"status": "error", "message": f"Workflow with ID {workflow_id} not found"}
            
            builder = WorkflowBuilder(workflow_model=workflow)
            return await builder.execute(user_query=user_query, metadata=metadata)
    
    @staticmethod
    async def run_from_configuration(workflow_model: WorkflowUpdate, user_query: str, metadata: dict = None) -> Dict[str, Any]:
        """Run a workflow directly from a configuration"""
        builder = WorkflowBuilder(workflow_model=workflow_model)
        response = await builder.execute(user_query=user_query, metadata=metadata) 
        return response