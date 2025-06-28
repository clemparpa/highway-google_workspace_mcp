from os import getenv
import logging
from logging import INFO, DEBUG

logger = logging.getLogger(__name__)


class _ENVIRONMENT: 

    def __init__(self): 
        self._auth_token = getenv("INTEGRATIONS_AUTH_TOKEN")
        self._request_header_user_id_key = getenv("REQUEST_HEADER_USER_ID_KEY")
        self._response_header_user_id_key = getenv("RESPONSE_HEADER_USER_ID_KEY")
        self._response_header_token_key = getenv("RESPONSE_HEADER_TOKEN_KEY")
        self._client_access_token_url = getenv("CLIENT_ACCESS_TOKEN_URL")
        self._logging_level =  DEBUG if getenv("LOGGING_LEVEL") == "debug" else INFO

    @property
    def auth_token(self) -> str:
        if not self._auth_token:
            logger.error("INTEGRATIONS_AUTH_TOKEN is not set")
            raise Exception("INTEGRATIONS_AUTH_TOKEN is not set")
        return self._auth_token
    
    @property
    def request_header_user_id_key(self) -> str:
        if not self._request_header_user_id_key:
            logger.error("REQUEST_HEADER_USER_ID_KEY is not set")
            raise Exception("REQUEST_HEADER_USER_ID_KEY is not set")
        return self._request_header_user_id_key
    
    @property
    def response_header_user_id_key(self) -> str:
        if not self._response_header_user_id_key:
            logger.error("RESPONSE_HEADER_USER_ID_KEY is not set")
            raise Exception("RESPONSE_HEADER_USER_ID_KEY is not set")
        return self._response_header_user_id_key
    
    @property
    def response_header_token_key(self) -> str:
        if not self._response_header_token_key:
            logger.error("RESPONSE_HEADER_TOKEN_KEY is not set")
            raise Exception("RESPONSE_HEADER_TOKEN_KEY is not set")
        return self._response_header_token_key
    
    @property
    def client_access_token_url(self) -> str:
        if not self._client_access_token_url:
            logger.error("CLIENT_ACCESS_TOKEN_URL is not set")
            raise Exception("CLIENT_ACCESS_TOKEN_URL is not set")
        return self._client_access_token_url
    
    @property
    def logging_level(self) -> str:
        return self._logging_level
    

ENVIRONMENT = _ENVIRONMENT()