from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi_injector import Injected

from app.auth.dependencies import auth
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.agent_config import AgentConfigService


router = APIRouter()


# TODO set permission validation
@router.get(
    "/configs",
    response_model=List[AgentRead],
    dependencies=[
        Depends(auth),
    ],
)
async def get_all_configs(
    config_service: AgentConfigService = Injected(AgentConfigService),
):
    """Get all agent configurations"""
    models = await config_service.get_all_full()

    agent_reads = [
        AgentRead.model_validate(agent_model).model_copy(
            update={
                "user_id": agent_model.operator.user.id,
                "test_input": (
                    agent_model.workflow.testInput
                    if agent_model.workflow.testInput
                    else None
                ),
            }
        )
        for agent_model in models
    ]
    return agent_reads


@router.get(
    "/configs/{agent_id}",
    response_model=AgentRead,
    dependencies=[
        Depends(auth),
    ],
)
async def get_config_by_id(
    agent_id: UUID, config_service: AgentConfigService = Injected(AgentConfigService)
):
    """Get a specific agent configuration by ID"""
    agent_model = await config_service.get_by_id_full(agent_id)
    agent_read = AgentRead.model_validate(agent_model).model_copy(
        update={"user_id": agent_model.operator.user.id}
    )
    return agent_read


@router.post(
    "/configs",
    response_model=AgentRead,
    dependencies=[
        Depends(auth),
    ],
)
async def create_config(
    request: Request,
    agent_create: AgentCreate = Body(...),
    config_service: AgentConfigService = Injected(AgentConfigService),
):
    """Create a new agent configuration"""
    current_user = request.state.user
    result = await config_service.create(agent_create, user_id=current_user.id)

    return AgentRead.model_validate(result).model_copy(
        update={"user_id": result.operator.user.id if result.operator else None}
    )


@router.put(
    "/configs/{agent_id}",
    response_model=AgentRead,
    dependencies=[
        Depends(auth),
    ],
)
async def update_config(
    agent_id: UUID,
    agent_update: AgentUpdate = Body(...),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """Update an existing agent configuration"""

    await agent_config_service.update(agent_id, agent_update)
    # Fetch the updated agent with all relationships to ensure security_settings is included
    agent_read = await agent_config_service.get_by_id_full(agent_id)
    return agent_read


@router.delete(
    "/configs/{agent_id}",
    response_model=Dict[str, str],
    dependencies=[
        Depends(auth),
    ],
)
async def delete_config(
    agent_id: UUID, config_service: AgentConfigService = Injected(AgentConfigService)
):
    """Delete an agent configuration"""
    await config_service.delete(agent_id)
    return {"status": "success", "message": f"Configuration with ID {agent_id} deleted"}


@router.post(
    "/configs/{agent_id}/welcome-image",
    dependencies=[
        Depends(auth),
    ],
)
async def upload_welcome_image(
    agent_id: UUID,
    image: UploadFile = File(...),
    config_service: AgentConfigService = Injected(AgentConfigService),
):
    """Upload welcome image for an agent"""
    # Validate file type
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read image data
    image_data = await image.read()

    # Validate file size (e.g., max 5MB)
    if len(image_data) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="Image file too large. Maximum size is 5MB"
        )

    await config_service.upload_welcome_image(agent_id, image_data)
    return {"status": "success", "message": "Welcome image uploaded successfully"}


@router.get("/configs/{agent_id}/welcome-image")
async def get_welcome_image(
    agent_id: UUID, config_service: AgentConfigService = Injected(AgentConfigService)
):
    """Get welcome image for an agent"""
    image_data = await config_service.get_welcome_image(agent_id)

    if image_data is None:
        raise HTTPException(status_code=404, detail="Welcome image not found")

    # Determine content type based on image data
    content_type = "image/jpeg"  # Default
    if image_data.startswith(b"\x89PNG"):
        content_type = "image/png"
    elif image_data.startswith(b"GIF"):
        content_type = "image/gif"
    elif image_data.startswith(b"RIFF") and b"WEBP" in image_data[:12]:
        content_type = "image/webp"

    return Response(content=image_data, media_type=content_type)


@router.delete(
    "/configs/{agent_id}/welcome-image",
    dependencies=[
        Depends(auth),
    ],
)
async def delete_welcome_image(
    agent_id: UUID, config_service: AgentConfigService = Injected(AgentConfigService)
):
    """Delete welcome image for an agent"""
    await config_service.delete_welcome_image(agent_id)
    return {"status": "success", "message": "Welcome image deleted successfully"}
