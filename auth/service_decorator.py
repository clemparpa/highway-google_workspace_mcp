import inspect
import logging
from functools import wraps
from typing import Dict, List, Optional, Any, Callable, Union
from core import ServiceCache
from auth.client_auth import get_credentials
from googleapiclient.discovery import build


logger = logging.getLogger(__name__)

# Import scope constants
from auth.scopes import (
    GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE, GMAIL_LABELS_SCOPE,
    DRIVE_READONLY_SCOPE, DRIVE_FILE_SCOPE,
    DOCS_READONLY_SCOPE, DOCS_WRITE_SCOPE,
    CALENDAR_READONLY_SCOPE, CALENDAR_EVENTS_SCOPE,
    SHEETS_READONLY_SCOPE, SHEETS_WRITE_SCOPE,
    CHAT_READONLY_SCOPE, CHAT_WRITE_SCOPE, CHAT_SPACES_SCOPE,
)

# Service configuration mapping
SERVICE_CONFIGS = {
    "gmail": {"service": "gmail", "version": "v1"},
    "drive": {"service": "drive", "version": "v3"},
    "calendar": {"service": "calendar", "version": "v3"},
    "docs": {"service": "docs", "version": "v1"},
    "sheets": {"service": "sheets", "version": "v4"},
    "chat": {"service": "chat", "version": "v1"},
    "forms": {"service": "forms", "version": "v1"},
    "slides": {"service": "slides", "version": "v1"}
}

# Scope group definitions for easy reference
SCOPE_GROUPS = {
    # Gmail scopes
    "gmail_read": GMAIL_READONLY_SCOPE,
    "gmail_compose": GMAIL_COMPOSE_SCOPE,
    "gmail_labels": GMAIL_LABELS_SCOPE,

    # Drive scopes
    "drive_read": DRIVE_READONLY_SCOPE,
    "drive_file": DRIVE_FILE_SCOPE,

    # Docs scopes
    "docs_read": DOCS_READONLY_SCOPE,
    "docs_write": DOCS_WRITE_SCOPE,

    # Calendar scopes
    "calendar_read": CALENDAR_READONLY_SCOPE,
    "calendar_events": CALENDAR_EVENTS_SCOPE,

    # Sheets scopes
    "sheets_read": SHEETS_READONLY_SCOPE,
    "sheets_write": SHEETS_WRITE_SCOPE,

    # Chat scopes
    "chat_read": CHAT_READONLY_SCOPE,
    "chat_write": CHAT_WRITE_SCOPE,
    "chat_spaces": CHAT_SPACES_SCOPE,
}


def _resolve_scopes(scopes: Union[str, List[str]]) -> List[str]:
    """Resolve scope names to actual scope URLs."""
    if isinstance(scopes, str):
        if scopes in SCOPE_GROUPS:
            return [SCOPE_GROUPS[scopes]]
        else:
            return [scopes]

    resolved = []
    for scope in scopes:
        if scope in SCOPE_GROUPS:
            resolved.append(SCOPE_GROUPS[scope])
        else:
            resolved.append(scope)
    return resolved


def require_google_service(
    service_type: str,
    scopes: Union[str, List[str]],
):
    """
    Decorator that automatically handles Google service authentication and injection.

    Args:
        service_type: Type of Google service ("gmail", "drive", "calendar", etc.)
        scopes: Required scopes (can be scope group names or actual URLs)
        version: Service version (defaults to standard version for service type)
        cache_enabled: Whether to use service caching (default: True)

    Usage:
        @require_google_service("gmail", "gmail_read")
        async def search_messages(service, user_google_email: str, query: str):
            # service parameter is automatically injected
            # Original authentication logic is handled automatically
    """
    def decorator(func: Callable) -> Callable:
        # Inspect the original function signature
        original_sig = inspect.signature(func)
        params = list(original_sig.parameters.values())

        # The decorated function must have 'service' and "user_google_email" as its first parameters.
        if not params or params[0].name != 'service':
            raise TypeError(
                f"Function '{func.__name__}' decorated with @require_google_service "
                "must have 'service' as its first parameter."
            )
        
        if not params or params[1].name != 'user_google_email':
            raise TypeError(
                f"Function '{func.__name__}' decorated with @require_google_service "
                "must have 'user_google_email' as its second parameter."
            )
        
        # Create a new signature for the wrapper that excludes the 'service' and "user_google_email" parameter.
        # This is the signature that FastMCP will see.
        wrapper_sig = original_sig.replace(parameters=params[2:])


        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Note: `args` and `kwargs` are now the arguments for the *wrapper*,
            # which does not include 'service'.
            if service_type not in SERVICE_CONFIGS:
                raise Exception(f"Unknown service type: {service_type}")

            config = SERVICE_CONFIGS[service_type]
            service_name = config["service"]
            version = config["version"]
            resolved_scopes = _resolve_scopes(scopes)

            credentials = get_credentials()
            if not credentials:
                raise Exception("No valid credentials found")

            if not credentials.has_scopes(resolved_scopes):
                raise Exception(
                    f"User doesn't have required scopes for {service_type} ({service_name}).\n"
                    "User needs to re-authenticate with the required scopes."
                )

            service = ServiceCache.get_cached_item([credentials.account, service_name])
            
            if not service:
                logger.debug(f"Creating new {service_name} service instance for {credentials.account}")
                if not service:
                    service = build(service_name, version, credentials=credentials)
                    ServiceCache.cache_item([credentials.account, service_name], service)

            try: 
                return await func(service, credentials.account, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {service_name} service call: {e}")
                raise Exception(f"Failed to call {service_name} service")            
        # Set the wrapper's signature to the one without 'service'
        wrapper.__signature__ = wrapper_sig
        return wrapper
    return decorator



def require_multiple_services(service_configs: List[Dict[str, Any]]):
    """
    Decorator for functions that need multiple Google services.

    Args:
        service_configs: List of service configurations, each containing:
            - service_type: Type of service
            - scopes: Required scopes
            - param_name: Name to inject service as (e.g., 'drive_service', 'docs_service')

    Usage:
        @require_multiple_services([
            {"service_type": "drive", "scopes": "drive_read", "param_name": "drive_service"},
            {"service_type": "docs", "scopes": "docs_read", "param_name": "docs_service"}
        ])
        async def get_doc_with_metadata(drive_service, docs_service, user_google_email: str, doc_id: str):
            # Both services are automatically injected
    """
    def decorator(func: Callable) -> Callable:
        # Extract user_google_email
        original_sig = inspect.signature(func)
        params = list(original_sig.parameters.values())
            
        for index, config in enumerate(service_configs):
            current_param_name = config['param_name']
            if not params or params[index].name != current_param_name:
                raise TypeError(
                    f"Function '{func.__name__}' decorated with @require_multiple_services "
                    f"must have '{current_param_name}' as its {index + 1}th parameter."
                )

        if not params or params[len(service_configs)].name != 'user_google_email':
            raise TypeError(
                f"Function '{func.__name__}' decorated with @require_multiple_services "
                f"must have 'user_google_email' as its {len(service_configs) + 1}th parameter."
            )

        wrapper_sig = original_sig.replace(parameters=params[len(service_configs) + 1:])

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Note: `args` and `kwargs` are now the arguments for the *wrapper*,
            # which does not include 'service'.
            credentials = get_credentials()
            if not credentials:
                raise Exception("No valid credentials found")

            services = []
            for config in service_configs:                
                service_type = config["service_type"]
                scopes = config["scopes"]

                if service_type not in SERVICE_CONFIGS:
                    raise Exception(f"Unknown service type: {service_type}")

                service_config = SERVICE_CONFIGS[service_type]
                service_name = service_config["service"]
                version = service_config["version"]
                resolved_scopes = _resolve_scopes(scopes)

                if not credentials.has_scopes(resolved_scopes):
                    raise Exception(
                        f"User doesn't have required scopes for {service_type} ({service_name}).\n"
                        "User needs to re-authenticate with the required scopes."
                    )

                service = ServiceCache.get_cached_item([credentials.account, service_name])                    
                if not service:
                    logger.debug(f"Creating new {service_name} service instance for {credentials.account}")
                    if not service:
                        service = build(service_name, version, credentials=credentials)
                        ServiceCache.cache_item([credentials.account, service_name], service)
                services.append(service)
            try: 
                return await func(*services, credentials.account, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {service_name} service call: {e}")
                raise Exception(f"Failed to call {service_name} service")            
            # Set the wrapper's signature to the one without 'service'
        # Set the wrapper's signature to the one without services
        wrapper.__signature__ = wrapper_sig
        return wrapper
    return decorator
                


