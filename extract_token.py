#!/usr/bin/env python3
"""
Token Extraction Utility for Skoob API
Extracts JWT authorization token from Playwright browser session.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _is_valid_jwt_token(token: str) -> bool:
    """
    Check if a token is a valid JWT format.
    JWT tokens start with 'eyJ' (base64 encoded JSON header).
    
    Args:
        token: Token string to validate
    
    Returns:
        True if token appears to be a valid JWT, False otherwise
    """
    if not token or not isinstance(token, str):
        return False
    
    # JWT tokens are base64 encoded and start with 'eyJ' ({"alg":...})
    # They also have three parts separated by dots
    parts = token.split('.')
    if len(parts) != 3:
        return False
    
    # Check if it starts with JWT header pattern
    if not token.startswith('eyJ'):
        return False
    
    # JWT tokens are typically quite long (at least 100 characters)
    if len(token) < 50:
        return False
    
    return True


def extract_auth_token(page, timeout: int = 30) -> Optional[str]:
    """
    Extract authorization token from Playwright page using network interception
    and storage fallback methods.
    
    Args:
        page: Playwright page object
        timeout: Maximum time to wait for token (seconds)
    
    Returns:
        Authorization token string or None if not found
    """
    token = None
    
    # Method 1: Intercept network requests (primary method)
    logger.info("Attempting to extract token via network interception...")
    token = _extract_from_network(page, timeout)
    
    if token and _is_valid_jwt_token(token):
        logger.info("Token extracted successfully via network interception")
        return token
    elif token:
        logger.warning(f"Network interception found token but it doesn't appear to be a valid JWT. Ignoring.")
        token = None
    
    # Method 2: Check browser storage (fallback)
    logger.info("Network interception failed, trying storage fallback...")
    token = _extract_from_storage(page)
    
    if token and _is_valid_jwt_token(token):
        logger.info("Token extracted successfully from browser storage")
        return token
    elif token:
        logger.warning(f"Storage found token but it doesn't appear to be a valid JWT. Ignoring.")
        token = None
    
    logger.warning("Could not extract valid JWT token using any method")
    return None


def _extract_from_network(page, timeout: int) -> Optional[str]:
    """
    Extract token by intercepting network requests to Skoob API.
    
    Args:
        page: Playwright page object
        timeout: Maximum time to wait (seconds)
    
    Returns:
        Authorization token string or None
    """
    token = None
    request_found = False
    
    def handle_request(request):
        nonlocal token, request_found
        url = request.url
        headers = request.headers
        
        # Check if this is a request to the Skoob API
        if "prd-api.skoob.com.br" in url or "api.skoob.com.br" in url:
            # Check for authorization header
            auth_header = headers.get("authorization") or headers.get("Authorization")
            if auth_header:
                token = auth_header
                request_found = True
                logger.info(f"Found authorization token in request to {url}")
    
    # Set up request listener
    page.on("request", handle_request)
    
    try:
        # Wait for a request with authorization header
        start_time = time.time()
        while not request_found and (time.time() - start_time) < timeout:
            time.sleep(0.5)
            if token:
                break
        
        # Remove listener
        page.remove_listener("request", handle_request)
        
        return token
    except Exception as e:
        logger.error(f"Error during network interception: {e}")
        try:
            page.remove_listener("request", handle_request)
        except:
            pass
        return None


def _extract_from_storage(page) -> Optional[str]:
    """
    Extract token from browser localStorage or sessionStorage.
    
    Args:
        page: Playwright page object
    
    Returns:
        Authorization token string or None
    """
    try:
        # Common storage keys to check
        storage_keys = [
            "auth_token",
            "token",
            "jwt",
            "authorization",
            "authToken",
            "accessToken",
            "access_token",
            "skoob_token",
            "skoob_auth",
        ]
        
        # Check localStorage
        logger.info("Checking localStorage...")
        for key in storage_keys:
            try:
                value = page.evaluate(f"() => localStorage.getItem('{key}')")
                if value:
                    logger.info(f"Found token in localStorage key: {key}")
                    return value
            except Exception as e:
                logger.debug(f"Error checking localStorage key '{key}': {e}")
        
        # Check sessionStorage
        logger.info("Checking sessionStorage...")
        for key in storage_keys:
            try:
                value = page.evaluate(f"() => sessionStorage.getItem('{key}')")
                if value:
                    logger.info(f"Found token in sessionStorage key: {key}")
                    return value
            except Exception as e:
                logger.debug(f"Error checking sessionStorage key '{key}': {e}")
        
        # Try to find any key containing "auth" or "token"
        logger.info("Searching for keys containing 'auth' or 'token'...")
        try:
            # Get all localStorage keys
            local_keys = page.evaluate("() => Object.keys(localStorage)")
            for key in local_keys:
                if "auth" in key.lower() or "token" in key.lower():
                    value = page.evaluate(f"() => localStorage.getItem('{key}')")
                    if value and _is_valid_jwt_token(value):
                        logger.info(f"Found valid JWT token in localStorage key: {key}")
                        return value
                    elif value and len(value) > 20:
                        logger.debug(f"Found value in localStorage key '{key}' but it's not a valid JWT")
        except Exception as e:
            logger.debug(f"Error searching localStorage: {e}")
        
        try:
            # Get all sessionStorage keys
            session_keys = page.evaluate("() => Object.keys(sessionStorage)")
            for key in session_keys:
                if "auth" in key.lower() or "token" in key.lower():
                    value = page.evaluate(f"() => sessionStorage.getItem('{key}')")
                    if value and _is_valid_jwt_token(value):
                        logger.info(f"Found valid JWT token in sessionStorage key: {key}")
                        return value
                    elif value and len(value) > 20:
                        logger.debug(f"Found value in sessionStorage key '{key}' but it's not a valid JWT")
        except Exception as e:
            logger.debug(f"Error searching sessionStorage: {e}")
        
        return None
    except Exception as e:
        logger.error(f"Error during storage extraction: {e}")
        return None

