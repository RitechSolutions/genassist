from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any
import logging

from app.auth.dependencies import auth, permissions
from app.schemas.datasource import DataSourceUpdate
from app.services.app_settings import AppSettingsService
from app.services.datasources import DataSourceService
from app.core.utils.encryption_utils import decrypt_key
from fastapi_injector import Injected
import requests
from datetime import datetime, timedelta

from app.tasks.sharepoint_tasks import import_sharepoint_files_to_kb_async_with_scope
from app.tasks.kb_batch_tasks import batch_process_files_kb_async_with_scope


logger = logging.getLogger(__name__)
router = APIRouter()

# --- Request/Response Schemas ---


class Office365AuthRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class Office365AuthResponse(BaseModel):
    status: str
    message: str


# --- Endpoint ---


@router.post(
    "/oauth/callback",
    response_model=Office365AuthResponse,
    dependencies=[Depends(auth), Depends(permissions("write:app_settings"))],
)
async def office365_callback(
    req: Office365AuthRequest,
    data_source_service: DataSourceService = Injected(DataSourceService),
    app_settings_service: AppSettingsService = Injected(AppSettingsService),
):
    logger.info(f"Received Office365 auth code: {req.code}")

    try:
        if not req.redirect_uri:
            raise HTTPException(status_code=400, detail="Missing redirect_uri")

        # Get data source to extract app_settings_id
        ds = await data_source_service.get_by_id(UUID(req.state))
        if not ds or not ds.connection_data:
            raise HTTPException(status_code=404, detail="Data source not found")

        app_settings_id = ds.connection_data.get("app_settings_id")
        if not app_settings_id:
            raise HTTPException(
                status_code=400, detail="App settings ID not found in data source"
            )

        logger.info("Exchanging Office365 authorization code for tokens")
        token_data = await get_office365_access_token(
            auth_code=req.code,
            redirect_uri=req.redirect_uri,
            app_settings_id=app_settings_id,
            app_settings_service=app_settings_service,
        )

        if not token_data:
            raise HTTPException(
                status_code=400, detail="Failed to exchange code for token"
            )

        user_email = await get_office365_user_email(token_data["access_token"])

        await save_office365_token_to_data_source(
            data_source_service, req.state, token_data, user_email, req.redirect_uri
        )

        return Office365AuthResponse(
            status="success",
            message="Office365 authentication successful. Tokens saved.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Office365 auth failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Office365 auth error: {str(e)}")


# --- Token Save Helper ---


async def save_office365_token_to_data_source(
    ds_service: DataSourceService,
    data_source_id: str,
    token_data: Dict[str, Any],
    user_email: str,
    redirect_uri: str,
):
    try:
        ds = await ds_service.get_by_id(UUID(data_source_id))
        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        token_data["user_email"] = user_email
        token_data["redirect_uri"] = redirect_uri

        ds_update = DataSourceUpdate(
            name=ds.name,
            source_type=ds.source_type,
            is_active=1,
            connection_data=token_data,
        )

        await ds_service.update(ds.id, ds_update)
        logger.info("Office365 tokens successfully saved to data source")

    except Exception as e:
        logger.error(f"Failed to save Office365 tokens: {e}")
        raise


async def get_office365_access_token(
    auth_code: str,
    redirect_uri: str,
    app_settings_id: str,
    app_settings_service: AppSettingsService = Injected(AppSettingsService),
) -> Dict[str, Any]:
    """
    Exchange Office365 authorization code for tokens.
    """
    try:
        # Get app settings by ID
        app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

        # Extract values from the values field
        values = app_settings.values if isinstance(app_settings.values, dict) else {}
        tenant_id = values.get("microsoft_tenant_id")
        client_id = values.get("microsoft_client_id")
        client_secret = values.get("microsoft_client_secret")

        # Decrypt client_secret
        if client_secret:
            client_secret = decrypt_key(client_secret)

        if not tenant_id or not client_id or not client_secret:
            raise HTTPException(
                status_code=500,
                detail="Microsoft credentials not configured in app settings",
            )

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        payload = {
            "client_id": client_id,
            "scope": "https://graph.microsoft.com/.default offline_access",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "client_secret": client_secret,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(token_url, data=payload, headers=headers, timeout=30)
        response.raise_for_status()
        token_data = response.json()

        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        logger.info("Office365 token exchange successful")
        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at.isoformat(),
            "expires_in": expires_in,
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", ""),
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Office365 token exchange failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
        return None
    except KeyError as e:
        logger.error(f"Office365 token response missing key: {e}")
        return None


async def get_office365_user_email(access_token: str) -> str:
    """
    Fetch the user's email from Microsoft Graph /me endpoint.
    """
    try:
        if not access_token:
            raise HTTPException(status_code=400, detail="Access token is required")

        logger.info("Fetching user email from Microsoft Graph")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me", headers=headers, timeout=15
        )

        if response.status_code != 200:
            logger.error(
                f"Failed to retrieve Office365 user info: {response.status_code} - {response.text}"
            )
            raise HTTPException(
                status_code=400,
                detail="Failed to retrieve user info from Microsoft Graph",
            )

        user_info = response.json()
        user_email = user_info.get("mail") or user_info.get("userPrincipalName")

        if not user_email:
            raise HTTPException(
                status_code=400,
                detail="Email not found in Microsoft Graph user profile",
            )

        logger.info(f"Office365 user email retrieved: {user_email}")
        return user_email

    except Exception as e:
        logger.error(f"Error fetching Office365 user email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve user email: {str(e)}"
        )


@router.get(
    "/office365-sharepoint-kb",
    dependencies=[Depends(auth)],
    summary="Runs the job that sync the KB with Sharepoint Site Content",
)
async def run_sharepoint_job_to():
    return await import_sharepoint_files_to_kb_async_with_scope()


@router.get(
    "/kb-batch-tasks",
    dependencies=[Depends(auth)],
    summary="Runs the job that sync the KB with files from various sources",
)
async def summarize_files_from_azure():
    return await batch_process_files_kb_async_with_scope()
