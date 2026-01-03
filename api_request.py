#!/usr/bin/env python3
"""
Skoob API Request Script
Replicates the API request to fetch bookshelf data.
"""

import requests
import json
import logging
import time
from datetime import datetime
from typing import Optional

# Configure logging (level will be set by main script)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API endpoint
url = "https://prd-api.skoob.com.br/api/v1/bookshelf"

# Default query parameters (user_id will be extracted dynamically)
DEFAULT_LIMIT = 30
DEFAULT_FILTER = "read"
DEFAULT_SEARCH_TYPE = "title"

SKOOB_BASE_URL = "https://www.skoob.com.br"
LOGIN_URL = f"{SKOOB_BASE_URL}/login"


def extract_user_id(page, api_response=None):
    """
    Extract user_id from Playwright page or API response.
    
    Args:
        page: Playwright page object
        api_response: Optional API response dict to extract user_id from
    
    Returns:
        user_id string or None
    """
    # Method 1: Try to extract from API response first (most reliable)
    if api_response and isinstance(api_response, dict):
        user_data = api_response.get("user", {})
        if isinstance(user_data, dict) and "id" in user_data:
            user_id = user_data["id"]
            logger.info(f"Extracted user_id from API response: {user_id}")
            return user_id
    
    # Method 2: Extract from Playwright page
    try:
        # Try to find user ID from profile link or URL
        user_link = page.query_selector('a[href*="/pt/user/"][href*="/bookshelf"], a[href*="/usuario/"][href*="/estante"]')
        if user_link:
            href = user_link.get_attribute('href')
            if href:
                # Extract user ID from URL like /pt/user/67bd0d5270c4abc337699ac9/bookshelf
                if '/pt/user/' in href:
                    parts = href.split('/pt/user/')
                    if len(parts) > 1:
                        user_id = parts[1].split('/')[0]
                        logger.info(f"Extracted user_id from page link: {user_id}")
                        return user_id
                # Or /usuario/12345/estante (old format)
                elif '/usuario/' in href:
                    parts = href.split('/usuario/')
                    if len(parts) > 1:
                        user_id = parts[1].split('/')[0]
                        logger.info(f"Extracted user_id from page link: {user_id}")
                        return user_id
        
        # Alternative: check current URL if already on user page
        current_url = page.url
        if '/pt/user/' in current_url:
            parts = current_url.split('/pt/user/')
            if len(parts) > 1:
                user_id = parts[1].split('/')[0]
                logger.info(f"Extracted user_id from current URL: {user_id}")
                return user_id
        elif '/usuario/' in current_url:
            parts = current_url.split('/usuario/')
            if len(parts) > 1:
                user_id = parts[1].split('/')[0]
                logger.info(f"Extracted user_id from current URL: {user_id}")
                return user_id
        
        # Try to find any link with user ID pattern
        links = page.query_selector_all('a[href*="/pt/user/"], a[href*="/usuario/"]')
        for link in links:
            href = link.get_attribute('href')
            if href:
                if '/pt/user/' in href:
                    parts = href.split('/pt/user/')
                    if len(parts) > 1:
                        user_id = parts[1].split('/')[0]
                        # User IDs can be alphanumeric (like 67bd0d5270c4abc337699ac9)
                        if user_id:
                            logger.info(f"Extracted user_id from page links: {user_id}")
                            return user_id
                elif '/usuario/' in href:
                    parts = href.split('/usuario/')
                    if len(parts) > 1:
                        user_id = parts[1].split('/')[0]
                        if user_id.isdigit():
                            logger.info(f"Extracted user_id from page links: {user_id}")
                            return user_id
        
        logger.warning("Could not extract user_id from page")
        return None
    except Exception as e:
        logger.error(f"Error extracting user_id from page: {e}")
        return None


def get_token_from_playwright():
    """
    Launch Playwright, navigate to Skoob, wait for login, and extract token and user_id.
    Uses the extract_token utility.
    
    Returns:
        Tuple of (token, user_id) or (None, None) on failure
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        from extract_token import extract_auth_token
        import time
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Make sure playwright and extract_token.py are available")
        return None
    
    logger.info("Starting Playwright token extraction...")
    
    with sync_playwright() as p:
        # Launch browser
        logger.info("Launching browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Navigate to login page
            logger.info(f"Navigating to login page: {LOGIN_URL}")
            try:
                page.goto(LOGIN_URL, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                logger.warning(f"Initial navigation timeout, trying with load strategy: {e}")
                page.goto(LOGIN_URL, wait_until='load', timeout=60000)
            
            # Wait for manual login
            logger.info("Browser opened. Please log in manually in the browser window.")
            logger.info("After logging in, return here and press Enter to continue...")
            input("Press Enter after you have logged in...")
            
            time.sleep(2)
            
            # Check if we're logged in
            try:
                page.wait_for_selector('a[href*="/pt/user/"], a[href*="/usuario/"]', timeout=5000)
                logger.info("Authentication detected.")
            except PlaywrightTimeoutError:
                logger.warning("Could not confirm authentication. Proceeding anyway...")
            
            # Set up network interception BEFORE navigating to pages that make API calls
            from extract_token import _extract_from_network, _extract_from_storage, _is_valid_jwt_token
            logger.info("Setting up network interception for token extraction...")
            
            # Set up request listener before navigation
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
                    if auth_header and _is_valid_jwt_token(auth_header):
                        token = auth_header
                        request_found = True
                        logger.info(f"Found valid JWT authorization token in request to {url}")
            
            # Set up request listener BEFORE navigation
            page.on("request", handle_request)
            
            # Navigate to user's bookshelf page to trigger API requests and get user_id
            logger.info("Navigating to bookshelf to trigger API requests...")
            # First try to get user_id from current page
            user_id = extract_user_id(page)
            
            # Navigate to homepage first, then to bookshelf if we have user_id
            try:
                page.goto(f"{SKOOB_BASE_URL}/", wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                logger.warning(f"Navigation to homepage had issues, continuing anyway: {e}")
            time.sleep(2)
            
            # If we don't have user_id yet, try to extract it again
            if not user_id:
                user_id = extract_user_id(page)
            
            # Navigate to bookshelf page if we have user_id (this should trigger API calls)
            if user_id:
                bookshelf_url = f"{SKOOB_BASE_URL}/pt/user/{user_id}/bookshelf?filter=read"
                logger.info(f"Navigating to bookshelf: {bookshelf_url}")
                try:
                    page.goto(bookshelf_url, wait_until='domcontentloaded', timeout=60000)
                except Exception as e:
                    logger.warning(f"Navigation to bookshelf had issues, continuing anyway: {e}")
                # Wait for API requests to be made
                logger.info("Waiting for API requests to be triggered...")
                time.sleep(5)
            else:
                logger.warning("Could not extract user_id. Will try to extract from API response.")
                logger.info("Waiting for API requests to be triggered...")
                time.sleep(5)
            
            # Wait a bit more for the token to be captured
            if not token:
                logger.info("Waiting for token to be captured from network requests...")
                start_time = time.time()
                while not request_found and (time.time() - start_time) < 30:
                    time.sleep(0.5)
                    if token:
                        break
            
            # Remove listener
            try:
                page.remove_listener("request", handle_request)
            except:
                pass
            
            # If network interception didn't work, try storage fallback
            if not token:
                logger.info("Network interception didn't capture token, trying storage fallback...")
                token = _extract_from_storage(page)
                if token and not _is_valid_jwt_token(token):
                    logger.warning("Storage token is not a valid JWT. Ignoring.")
                    token = None
            
            if not token:
                logger.warning("Could not extract token. You may need to navigate to a page that makes API calls.")
                logger.info("Try navigating to your bookshelf page in the browser...")
                input("Press Enter after navigating to a page that loads your books...")
                
                # Try again after user navigates
                token = extract_auth_token(page, timeout=30)
                # Also try to get user_id again
                if not user_id:
                    user_id = extract_user_id(page)
            
            # If we still don't have user_id, try one more time
            if not user_id:
                user_id = extract_user_id(page)
            
            if token and user_id:
                logger.info(f"Successfully extracted token and user_id: {user_id}")
                return (token, user_id)
            elif token:
                logger.warning("Extracted token but not user_id. user_id will need to be extracted from API response.")
                return (token, None)
            else:
                logger.error("Failed to extract token")
                return (None, None)
                
        except Exception as e:
            logger.error(f"Error during token extraction: {e}")
            return (None, None)
        finally:
            browser.close()


def fetch_all_pages(token: str, user_id: str, filter_type: str = "read", search_type: str = "title", limit: int = 30, debug: bool = False):
    """
    Fetch all pages of bookshelf data recursively.
    
    Args:
        token: Authorization token
        user_id: User ID
        filter_type: Filter type (e.g., "read", "reading", "want")
        search_type: Search type (e.g., "title")
        limit: Items per page (default 30, API limit)
    
    Returns:
        Dictionary with all items and metadata, or None on error
    """
    url = "https://prd-api.skoob.com.br/api/v1/bookshelf"
    headers = get_headers(token)
    
    all_items = []
    page = 1
    total_pages = None
    total_items = None
    years_filter = None
    user_data = None
    
    logger.info(f"Starting to fetch all pages for user_id: {user_id}")
    
    while True:
        params = {
            "page": page,
            "limit": limit,
            "bookshelf_type": "book",
            "user_id": user_id,
            "filter": filter_type,
            "search_type": search_type
        }
        
        try:
            logger.info(f"Fetching page {page}...")
            response = requests.get(url, params=params, headers=headers)
            
            # Debug: Log response details (only in debug mode)
            if debug:
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Content-Encoding: {response.headers.get('Content-Encoding', 'none')}")
                logger.debug(f"Response content length: {len(response.content)} bytes")
            
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                if page == 1:
                    # If first page fails, return None
                    return None
                else:
                    # If later page fails, check if we've reached expected total
                    if total_items and len(all_items) >= total_items:
                        logger.info(f"Reached expected total items ({total_items}). Stopping.")
                        break
                    # Try to continue or break based on what we have
                    logger.warning(f"Page {page} failed, but continuing with {len(all_items)} items collected so far")
                    break
            
            # Check if response is compressed and handle it
            content_encoding = response.headers.get('Content-Encoding', '').lower()
            response_text = None
            
            if content_encoding:
                if debug:
                    logger.debug(f"Response is compressed with: {content_encoding}")
                # Try to get decompressed text
                try:
                    response_text = response.text
                    # Check if it's actually decompressed (starts with { or [)
                    if response_text and (response_text.strip().startswith('{') or response_text.strip().startswith('[')):
                        if debug:
                            logger.debug("Response successfully decompressed")
                    else:
                        logger.warning(f"Response may not be properly decompressed. First 50 bytes: {response.content[:50]}")
                        # Try to manually decompress
                        import gzip
                        import zlib
                        try:
                            if 'gzip' in content_encoding:
                                response_text = gzip.decompress(response.content).decode('utf-8')
                                logger.info("Manually decompressed gzip response")
                            elif 'deflate' in content_encoding:
                                response_text = zlib.decompress(response.content).decode('utf-8')
                                logger.info("Manually decompressed deflate response")
                        except Exception as decompress_error:
                            logger.error(f"Failed to manually decompress: {decompress_error}")
                except Exception as e:
                    logger.error(f"Error getting response text: {e}")
            else:
                response_text = response.text
            
            # Check if response is empty
            if not response_text or not response_text.strip():
                logger.warning(f"Empty response on page {page}")
                if total_items and len(all_items) >= total_items:
                    logger.info(f"Reached expected total items ({total_items}). Stopping.")
                    break
                # If we're past the expected last page, stop
                if total_pages and page > total_pages:
                    break
                # Otherwise, try next page
                page += 1
                continue
            
            # Check if response looks like JSON
            if not (response_text.strip().startswith('{') or response_text.strip().startswith('[')):
                logger.error(f"Response doesn't look like JSON. First 200 chars: {response_text[:200]}")
                logger.error(f"Response content (hex): {response.content[:100].hex()}")
                # Try to decode as text to see what we got
                try:
                    logger.error(f"Response as text (first 200 chars): {response_text[:200]}")
                except:
                    pass
            
            # Try to parse JSON - use response.json() directly as it handles decompression
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response on page {page}: {e}")
                if debug:
                    logger.error(f"Response status: {response.status_code}")
                    logger.error(f"Content-Encoding: {content_encoding}")
                    logger.error(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                    logger.error(f"Response encoding: {response.encoding}")
                    logger.error(f"Response content length: {len(response.content)} bytes")
                
                # Try to manually decompress if needed
                if content_encoding:
                    logger.info(f"Attempting manual decompression for {content_encoding}...")
                    try:
                        if 'gzip' in content_encoding:
                            decompressed = gzip.decompress(response.content)
                            response_text = decompressed.decode('utf-8')
                            logger.info("Successfully decompressed gzip")
                        elif 'deflate' in content_encoding:
                            decompressed = zlib.decompress(response.content)
                            response_text = decompressed.decode('utf-8')
                            logger.info("Successfully decompressed deflate")
                        elif 'br' in content_encoding:
                            try:
                                import brotli
                                decompressed = brotli.decompress(response.content)
                                response_text = decompressed.decode('utf-8')
                                logger.info("Successfully decompressed brotli")
                            except ImportError:
                                logger.error("Brotli library not installed. Install with: pip install brotli")
                                raise
                        else:
                            logger.error(f"Unknown compression type: {content_encoding}")
                            raise ValueError(f"Unknown compression: {content_encoding}")
                        
                        # Try parsing again with decompressed data
                        data = json.loads(response_text)
                        logger.info("Successfully parsed JSON after manual decompression")
                    except Exception as decompress_error:
                        logger.error(f"Manual decompression failed: {decompress_error}")
                        logger.error(f"Response text (first 500 chars): {response_text[:500] if response_text else 'N/A'}")
                        logger.error(f"Raw content (first 100 bytes hex): {response.content[:100].hex()}")
                        raise
                else:
                    logger.error(f"Response text (first 500 chars): {response_text[:500] if response_text else 'N/A'}")
                    logger.error(f"Raw content (first 100 bytes hex): {response.content[:100].hex()}")
                    raise
                
                # If this is the last expected page and we're missing items, retry
                if total_pages and page == total_pages:
                    if total_items and len(all_items) < total_items:
                        logger.warning(f"Last page ({page}) failed but we only have {len(all_items)}/{total_items} items. Retrying...")
                        try:
                            time.sleep(2)  # Brief delay before retry
                            retry_response = requests.get(url, params=params, headers=headers)
                            if retry_response.status_code == 200:
                                retry_data = retry_response.json()
                                retry_items = retry_data.get("items", [])
                                if retry_items:
                                    all_items.extend(retry_items)
                                    logger.info(f"Page {page} (retry): Retrieved {len(retry_items)} items (total so far: {len(all_items)})")
                                    break
                        except Exception as retry_error:
                            logger.error(f"Retry also failed: {retry_error}")
                
                # Check if we've reached expected total
                if total_items and len(all_items) >= total_items:
                    logger.info(f"Reached expected total items ({total_items}) despite JSON error. Stopping.")
                    break
                # If we're past the expected last page, stop
                if total_pages and page > total_pages:
                    break
                # Otherwise, try next page
                page += 1
                continue
            
            # Extract metadata from first page
            if page == 1:
                total_pages = data.get("total_pages")
                total_items = data.get("total_items")
                years_filter = data.get("years_filter")
                user_data = data.get("user")
                
                # If we didn't have user_id, extract it from response
                if not user_id and user_data and "id" in user_data:
                    user_id = user_data["id"]
                    logger.info(f"Extracted user_id from API response: {user_id}")
                    # Update params for future requests
                    params["user_id"] = user_id
            
            # Get items from this page
            items = data.get("items", [])
            
            if not items:
                logger.info(f"No items found on page {page}.")
                # Check if we've reached expected total
                if total_items and len(all_items) >= total_items:
                    logger.info(f"Reached expected total items ({total_items}). Stopping.")
                    break
                # If we're past the expected last page, stop
                if total_pages and page >= total_pages:
                    logger.info(f"Reached last page ({total_pages}). Stopping pagination.")
                    break
                # Otherwise, try next page in case of temporary issue
                logger.warning(f"No items on page {page}, but expected {total_items} total. Trying next page...")
                page += 1
                continue
            
            all_items.extend(items)
            logger.info(f"Page {page}: Retrieved {len(items)} items (total so far: {len(all_items)})")
            
            # Check if we've reached the expected total
            if total_items and len(all_items) >= total_items:
                logger.info(f"Reached expected total items ({total_items}). Stopping pagination.")
                break
            
            # Check if we've reached the last page
            if total_pages and page >= total_pages:
                logger.info(f"Reached last page ({total_pages}). Stopping pagination.")
                break
            
            # Safety check: if we got fewer items than limit, we're probably on the last page
            if len(items) < limit:
                logger.info(f"Received fewer items than limit ({len(items)} < {limit}). Assuming last page.")
                break
            
            page += 1
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed on page {page}: {e}")
            if page == 1:
                return None
            else:
                # Check if we've reached expected total
                if total_items and len(all_items) >= total_items:
                    logger.info(f"Reached expected total items ({total_items}) despite request error. Stopping.")
                    break
                # Otherwise, break and return what we have
                break
        except Exception as e:
            logger.error(f"Unexpected error on page {page}: {e}")
            if page == 1:
                return None
            else:
                break
    
    logger.info(f"Finished fetching all pages. Total items: {len(all_items)}")
    
    # Return combined data structure
    result = {
        "total_pages": total_pages or page - 1,
        "total_items": total_items or len(all_items),
        "years_filter": years_filter,
        "user": user_data,
        "items": all_items
    }
    
    return result


def get_headers(token: str) -> dict:
    """
    Get request headers with authorization token.
    
    Args:
        token: Authorization token (required)
    
    Returns:
        Headers dictionary
    """
    
    return {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en;q=0.9,pt-BR;q=0.8,pt;q=0.7,en-US;q=0.6",
        "authorization": token,
        "content-type": "application/json",
        # "if-none-match": 'W/"hnVLAmB6W56WSP9o4Hj2RwyAeuQ="',  # Commented out to get fresh data instead of 304
        "origin": "https://www.skoob.com.br",
        "referer": "https://www.skoob.com.br/",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }

def fetch_bookshelf_data(filter_type: str = DEFAULT_FILTER, search_type: str = DEFAULT_SEARCH_TYPE, 
                        limit: int = DEFAULT_LIMIT, token: Optional[str] = None, user_id: Optional[str] = None, debug: bool = False):
    """
    Fetch all bookshelf data using Playwright for authentication.
    
    Args:
        filter_type: Filter type (e.g., "read", "reading", "want")
        search_type: Search type (e.g., "title")
        limit: Items per page (default 30)
        token: Optional token (if not provided, will extract from Playwright)
        user_id: Optional user_id (if not provided, will extract from Playwright or API)
    
    Returns:
        Dictionary with all items and metadata, or None on error
    """
    # Extract token and user_id from Playwright if not provided
    if not token or not user_id:
        logger.info("Extracting token and user_id from Playwright session...")
        result = get_token_from_playwright()
        if not result or result[0] is None:
            logger.error("Failed to extract token from Playwright session")
            return None
        
        extracted_token, extracted_user_id = result
        
        if not token:
            token = extracted_token
        if not user_id:
            user_id = extracted_user_id
        
        if not token:
            logger.error("No token available. Cannot proceed.")
            return None
    
    # If we still don't have user_id, we'll try to get it from the first API response
    logger.info(f"Using token and user_id: {user_id if user_id else 'will extract from API'}")
    
    # Fetch all pages
    data = fetch_all_pages(token, user_id or "", filter_type, search_type, limit, debug=debug)
    
    if data:
        # If we didn't have user_id before, extract it from the response
        if not user_id and data.get("user") and data["user"].get("id"):
            user_id = data["user"]["id"]
            logger.info(f"Extracted user_id from API response: {user_id}")
        
        # Save to file only if debug mode
        if debug:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"api_response_{timestamp}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Response saved to: {filename}")
        
        logger.info(f"Fetched {data.get('total_items', len(data.get('items', [])))} items across {data.get('total_pages', 1)} pages")
        
        return data
    else:
        logger.error("Failed to fetch bookshelf data")
        return None

if __name__ == "__main__":
    import sys
    
    # Check for debug flag
    debug = "--debug" in sys.argv or "-d" in sys.argv
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    print("Skoob Bookshelf API Fetcher")
    print("=" * 50)
    print("This script will:")
    print("1. Open a browser for you to log in to Skoob")
    print("2. Extract your authorization token and user ID")
    print("3. Fetch all pages of your bookshelf data")
    print("=" * 50)
    print()
    
    # Check for filter argument
    filter_type = DEFAULT_FILTER
    if "--filter" in sys.argv:
        try:
            idx = sys.argv.index("--filter")
            filter_type = sys.argv[idx + 1]
        except (IndexError, ValueError):
            logger.warning("Invalid --filter argument, using default: read")
    
    result = fetch_bookshelf_data(filter_type=filter_type, debug=debug)
    
    if result:
        print("\n" + "=" * 50)
        print("SUCCESS!")
        print(f"Total items: {result.get('total_items', 0)}")
        print(f"Total pages: {result.get('total_pages', 0)}")
        print(f"Items retrieved: {len(result.get('items', []))}")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("FAILED!")
        print("Could not fetch bookshelf data.")
        print("=" * 50)

