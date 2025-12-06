from datetime import datetime, timedelta
import logging
from typing import Any, Dict
from uuid import UUID
from fastapi import HTTPException
from fastapi_injector import Injected
import requests

from app.core.utils.encryption_utils import decrypt_key
from app.services.app_settings import AppSettingsService

logger = logging.getLogger(__name__)


async def get_access_token(
    auth_code: str,
    redirect_uri: str,
    app_settings_id: str,
    app_settings_service: AppSettingsService = Injected(AppSettingsService),
) -> Dict[str, Any]:
    """
    Exchange authorization code for access and refresh tokens
    """
    try:
        # Get app settings by ID
        app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

        # Extract values from the values field
        values = app_settings.values if isinstance(app_settings.values, dict) else {}
        client_id = values.get("gmail_client_id")
        client_secret = values.get("gmail_client_secret")

        # Decrypt client_secret
        if client_secret:
            client_secret = decrypt_key(client_secret)

        if not client_id or not client_secret:
            raise HTTPException(
                status_code=500,
                detail="Gmail credentials not configured in app settings",
            )

        token_url = "https://oauth2.googleapis.com/token"

        payload = {
            "code": auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(token_url, data=payload, headers=headers, timeout=30)
        response.raise_for_status()

        token_data = response.json()

        logger.debug(f"Token exchange successful: {token_data}")

        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at.isoformat(),
            "expires_in": expires_in,
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", ""),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Token exchange request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
        return None
    except KeyError as e:
        logger.error(f"Invalid token response format: {e}")
        return None


async def get_user_email(access_token: str) -> str:
    """
    Fetch user email using the Gmail API
    """
    try:
        if not access_token:
            logger.error("Access token is required to fetch user email")
            raise HTTPException(status_code=400, detail="Access token is required")
        logger.info("Fetching user email from Gmail profile")
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.request("GET", user_info_url, headers=headers)
        if response.status_code != 200:
            logger.error(
                f"Failed to retrieve user info: {response.status_code} - {response.text}"
            )
            raise HTTPException(
                status_code=400, detail="Failed to retrieve user information"
            )
        user_info = response.json()
        user_email = user_info.get("email")
        if not user_email:
            logger.error(f"User email not found in Gmail profile - {user_info}")
            raise HTTPException(
                status_code=400,
                detail="Failed to retrieve user email from Gmail profile",
            )
        logger.info(f"Retrieved user email: {user_email}")
        return user_email
    except Exception as e:
        logger.error(f"Error fetching user email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve user email: {str(e)}"
        )
