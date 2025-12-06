from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any
import logging

from requests import request
from app.auth.dependencies import auth, permissions
from app.core.utils.encryption_utils import decrypt_key
from app.core.utils.gmail import get_access_token, get_user_email
from app.schemas.datasource import DataSourceUpdate
from app.services.app_settings import AppSettingsService
from fastapi_injector import Injected

from app.services.datasources import DataSourceService

logger = logging.getLogger(__name__)

router = APIRouter()

# Request/Response models


class GmailAuthRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class GmailAuthResponse(BaseModel):
    status: str
    message: str


@router.post(
    "/oauth/callback",
    response_model=GmailAuthResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions("write:app_settings")),  # Adjust permission as needed
    ],
)
async def store_oauth_code(
    gmail_req: GmailAuthRequest,
    data_source_service: DataSourceService = Injected(DataSourceService),
    app_settings_service=Injected(AppSettingsService),
):
    """
    Exchange Gmail authorization code for access and refresh tokens
    """
    logger.info(f"Received Gmail auth code: {gmail_req.code}")
    try:
        logger.info("Exchanging Gmail authorization code for tokens")
        if not gmail_req.redirect_uri:
            redirect_uri = request.base_url + "gauth/callback"
        else:
            redirect_uri = gmail_req.redirect_uri

        # Get data source to extract app_settings_id
        ds = await data_source_service.get_by_id(UUID(gmail_req.state))
        if not ds or not ds.connection_data:
            raise HTTPException(status_code=404, detail="Data source not found")

        app_settings_id = ds.connection_data.get("app_settings_id")
        if not app_settings_id:
            raise HTTPException(
                status_code=400, detail="App settings ID not found in data source"
            )

        # exchange of auth code for token
        token_data = await get_access_token(
            auth_code=gmail_req.code,
            redirect_uri=redirect_uri,
            app_settings_id=app_settings_id,
            app_settings_service=app_settings_service,
        )

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code for token",
            )

        # get user email from profile
        user_email = await get_user_email(token_data["access_token"])

        # Save auth_code to data source
        await save_gmail_token_to_data_source(
            data_source_service, gmail_req.state, token_data, user_email, redirect_uri
        )
        logger.info(f"Gmail tokens saved successfully")

        return GmailAuthResponse(
            status="success", message="Gmail authentication successful. Tokens saved."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail auth code exchange failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}",
        )


async def save_gmail_token_to_data_source(
    ds_service: DataSourceService,
    data_source_id: str,
    token_data: Dict[str, Any],
    user_email: str,
    redirect_uri: str,
):
    """
    Save Gmail tokens to data source
    """
    try:
        # Save access token
        ds = await ds_service.get_by_id(UUID(data_source_id))
        if not ds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source with ID {data_source_id} not found",
            )

        token_data["user_email"] = user_email
        token_data["redirect_uri"] = redirect_uri

        ds_update = DataSourceUpdate(
            name=ds.name,
            source_type=ds.source_type,
            is_active=1,
            connection_data=token_data,
        )
        await ds_service.update(ds.id, datasource_update=ds_update)

        logger.info("Gmail tokens successfully saved to data connection settings")

    except Exception as e:
        logger.error(f"Failed to save Gmail tokens: {e}")
        raise
