from fastmcp.server.dependencies import get_http_request
from environment import ENVIRONMENT
from google.oauth2.credentials import Credentials
import httpx
import logging
from core.cache import CredentialsCache
from auth.scopes import (
    GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE, GMAIL_LABELS_SCOPE,
    DRIVE_READONLY_SCOPE, DRIVE_FILE_SCOPE,
    DOCS_READONLY_SCOPE, DOCS_WRITE_SCOPE,
    CALENDAR_READONLY_SCOPE, CALENDAR_EVENTS_SCOPE,
    SHEETS_READONLY_SCOPE, SHEETS_WRITE_SCOPE,
    CHAT_READONLY_SCOPE, CHAT_WRITE_SCOPE, CHAT_SPACES_SCOPE,
)
    

logger = logging.getLogger(__name__)

SCOPE_GROUPS = {
    "gmail": [GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE, GMAIL_LABELS_SCOPE],
    "drive": [DRIVE_READONLY_SCOPE, DRIVE_FILE_SCOPE],
    "docs": [DOCS_READONLY_SCOPE, DOCS_WRITE_SCOPE],
    "calendar": [CALENDAR_READONLY_SCOPE, CALENDAR_EVENTS_SCOPE],
    "sheets": [SHEETS_READONLY_SCOPE, SHEETS_WRITE_SCOPE],
    "chat": [CHAT_READONLY_SCOPE, CHAT_WRITE_SCOPE, CHAT_SPACES_SCOPE],
}



def _get_auth_header() -> dict[str, str] | None:
    """Retrieve the Google Workspace authentication header from the request."""
    user_id = get_http_request().headers.get(ENVIRONMENT.request_header_user_id_key)
    auth_token = ENVIRONMENT.auth_token

    if (not user_id) or (not auth_token):
        logger.error("User ID or auth token is missing in the request headers.")
        return None

    return {
        ENVIRONMENT.response_header_user_id_key: user_id,
        ENVIRONMENT.response_header_token_key: auth_token
    }

def _parse_credentials(response: dict) -> Credentials | None:
    """Parse the Google Workspace credentials from the response.
    
    Args:
        response (dict): The response containing the credentials.
        
    Returns:
        Credentials | None: The parsed credentials or None if parsing fails.
    """
    access_token = response.get("accessToken")
    user_email = response.get("email")
    scopes = response.get("scopes", [])
    # scopes = []
    # for service in services:
    #     if service not in SCOPE_GROUPS:
    #         logger.warning(f"Service '{service}' is not recognized. Skipping.")
    #     else:
    #         scopes.extend(SCOPE_GROUPS[service])

    if not access_token:
        logger.error("Access token not found in the response.")
        return None
    if not user_email:
        logger.error("User email not found in the response.")
        return None
    if len(scopes) == 0:
        logger.error("No valid scopes found in the response.")
        return None
    try:
        return Credentials(
            token=access_token,
            account=user_email,
            scopes=scopes
        )
    except Exception as e:
        logger.error(f"Error parsing Google Workspace credentials: {e}")
        return None


def get_credentials() -> Credentials | None :
    """Get the current user ID from the X-User-ID header.
    
    Returns:
        The user ID from the request header, or an error message if not found.
    """
    try: 
        headers = _get_auth_header()
        if not headers:
            logger.error("Error getting Google Workspace auth header.")
            return None
        
        user_id = headers.get(ENVIRONMENT.request_header_user_id_key)
        if not user_id:
            logger.error("User ID is missing in the request headers.")
            return None
        
        credentials = CredentialsCache.get_cached_item(user_id) 
        if credentials:
            logger.debug(f"Using cached credentials for user_id: {user_id}")
            return credentials

        resp = httpx.get(ENVIRONMENT.client_access_token_url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"Error getting Google Workspace access token: {resp.status_code} {resp.text}")
            return None        
        credentials = _parse_credentials(resp.json())
        if not credentials:
            logger.error("Failed to parse Google Workspace credentials from response.")
            return None
        CredentialsCache.cache_item(user_id, credentials)
        return credentials

    except Exception as e:
        logger.error(f"Error getting Google Workspace access token: {e}")
        return None
