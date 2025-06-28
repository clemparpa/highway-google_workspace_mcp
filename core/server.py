import logging
from fastmcp import FastMCP
from environment import ENVIRONMENT

from auth.scopes import (
    USERINFO_EMAIL_SCOPE,
    OPENID_SCOPE,
    CALENDAR_READONLY_SCOPE,
    CALENDAR_EVENTS_SCOPE,
    DRIVE_READONLY_SCOPE,
    DRIVE_FILE_SCOPE,
    GMAIL_READONLY_SCOPE,
    GMAIL_SEND_SCOPE,
    GMAIL_COMPOSE_SCOPE,
    GMAIL_MODIFY_SCOPE,
    GMAIL_LABELS_SCOPE,
    BASE_SCOPES,
    CALENDAR_SCOPES,
    DRIVE_SCOPES,
    GMAIL_SCOPES,
    DOCS_READONLY_SCOPE,
    DOCS_WRITE_SCOPE,
    CHAT_READONLY_SCOPE,
    CHAT_WRITE_SCOPE,
    CHAT_SPACES_SCOPE,
    CHAT_SCOPES,
    SHEETS_READONLY_SCOPE,
    SHEETS_WRITE_SCOPE,
    SHEETS_SCOPES,
    SCOPES
)

# Configure logging
logging.basicConfig(level=ENVIRONMENT.logging_level)
logger = logging.getLogger(__name__)


# Basic MCP server instance
server = FastMCP("google_workspace")