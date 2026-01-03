#!/usr/bin/env python3
"""
Standalone script to extract Skoob authorization token from browser session.
Uses Playwright to login and extract the JWT token.
"""

import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from extract_token import extract_auth_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SKOOB_BASE_URL = "https://www.skoob.com.br"
LOGIN_URL = f"{SKOOB_BASE_URL}/login"


def wait_for_manual_login(page):
    """Wait for user to manually complete login."""
    logger.info("Browser opened. Please log in manually in the browser window.")
    logger.info("After logging in, return here and press Enter to continue...")
    input("Press Enter after you have logged in...")
    
    # Wait a moment for any redirects to complete
    import time
    time.sleep(2)
    
    # Check if we're logged in by looking for user-specific elements
    try:
        # Try to find elements that indicate logged-in state
        page.wait_for_selector('a[href*="/pt/user/"], a[href*="/usuario/"]', timeout=5000)
        logger.info("Authentication detected.")
        return True
    except PlaywrightTimeoutError:
        logger.warning("Could not confirm authentication. Proceeding anyway...")
        return True


def get_token_from_playwright():
    """
    Launch Playwright, navigate to Skoob, wait for login, and extract token.
    
    Returns:
        Authorization token string or None
    """
    logger.info("Starting token extraction process...")
    
    with sync_playwright() as p:
        # Launch browser
        logger.info("Launching browser...")
        browser = p.chromium.launch(headless=False)  # headless=False so user can see and interact
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Navigate to login page
            logger.info(f"Navigating to login page: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
            
            # Wait for manual login
            if not wait_for_manual_login(page):
                logger.error("Authentication failed or not detected")
                return None
            
            # Navigate to a page that will trigger API requests
            # The bookshelf page should make API calls
            logger.info("Navigating to bookshelf to trigger API requests...")
            page.goto(f"{SKOOB_BASE_URL}/", wait_until='domcontentloaded', timeout=30000)
            
            # Wait a bit for any initial API calls
            import time
            time.sleep(3)
            
            # Try to extract token
            logger.info("Extracting authorization token...")
            token = extract_auth_token(page, timeout=30)
            
            if token:
                logger.info("Token extracted successfully!")
                return token
            else:
                logger.warning("Could not extract token. You may need to navigate to a page that makes API calls.")
                logger.info("Try navigating to your bookshelf page in the browser...")
                input("Press Enter after navigating to a page that loads your books...")
                
                # Try again after user navigates
                token = extract_auth_token(page, timeout=30)
                return token
                
        except Exception as e:
            logger.error(f"Error during token extraction: {e}")
            return None
        finally:
            browser.close()


if __name__ == "__main__":
    token = get_token_from_playwright()
    
    if token:
        print("\n" + "=" * 70)
        print("AUTHORIZATION TOKEN:")
        print("=" * 70)
        print(token)
        print("=" * 70)
        print("\nYou can use this token in your API requests.")
        print("Note: This token expires after approximately 13 days.")
    else:
        print("\nFailed to extract token. Please try again.")

