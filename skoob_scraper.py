#!/usr/bin/env python3
"""
Skoob Bookshelf Scraper
Scrapes book information from Skoob Estante and exports to CSV.
"""

import csv
import re
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SKOOB_BASE_URL = "https://www.skoob.com.br"


def scrape_book_details_http(book_url):
        # First, try to get title from image alt text (format: "Capa do livro [Title]")
        img_elem = book_element.query_selector('img[alt^="Capa do livro"]')
        if img_elem:
            alt_text = img_elem.get_attribute('alt') or ''
            if alt_text.startswith('Capa do livro '):
                title = alt_text.replace('Capa do livro ', '').strip()
                # Remove "fallback" suffix that appears in nocover books
                if title.lower().endswith(' fallback'):
                    title = title[:-9].strip()  # Remove " fallback" (9 characters)
                book_data['title'] = title
        
        # Title - also check h2 elements (the actual structure uses h2 for title)
        if not book_data.get('title'):
            title_elem = book_element.query_selector('h2')
            if title_elem:
                title_text = title_elem.inner_text().strip()
                if title_text:
                    book_data['title'] = title_text
        
        # If still no title, try other selectors
        if not book_data.get('title'):
            title_selectors = [
                'h3', 'h4',
                '.titulo', '.title',
                'a[href*="/livro/"]',
                '[class*="titulo"]',
                '[class*="title"]',
                '[data-title]'
            ]
            for selector in title_selectors:
                title_elem = book_element.query_selector(selector)
                if title_elem:
                    title_text = title_elem.inner_text().strip()
                    if title_text:
                        book_data['title'] = title_text
                        break
        
        # If no title found, try getting it from the link
        if not book_data.get('title'):
            link_elem = book_element.query_selector('a[href*="/livro/"]')
            if link_elem:
                title_text = link_elem.inner_text().strip()
                if title_text:
                    book_data['title'] = title_text
        
        # Author - check h3 elements (the structure uses h3 for author)
        author_elem = book_element.query_selector('h3')
        if author_elem:
            author_text = author_elem.inner_text().strip()
            if author_text:
                book_data['author'] = author_text
        
        # If no author found, try other strategies
        if not book_data.get('author'):
            author_selectors = [
                '.autor', '.author',
                '[class*="autor"]',
                '[class*="author"]',
                '[data-author]',
                '.by',  # Common pattern: "by Author Name"
            ]
            for selector in author_selectors:
                author_elem = book_element.query_selector(selector)
                if author_elem:
                    author_text = author_elem.inner_text().strip()
                    if author_text:
                        book_data['author'] = author_text
                        break
        
        # If no author found, try extracting from text patterns
        if not book_data.get('author'):
            all_text = book_element.inner_text()
            # Look for patterns like "por Author Name" or "by Author Name"
            por_match = re.search(r'por\s+([^\n]+)', all_text, re.IGNORECASE)
            by_match = re.search(r'by\s+([^\n]+)', all_text, re.IGNORECASE)
            if por_match:
                book_data['author'] = por_match.group(1).strip()
            elif by_match:
                book_data['author'] = by_match.group(1).strip()
        
        # ISBN - if available
        isbn_elem = book_element.query_selector('[class*="isbn"], .isbn, [data-isbn]')
        if isbn_elem:
            isbn_text = isbn_elem.inner_text().strip()
            # Extract only digits and hyphens
            isbn_clean = re.sub(r'[^\d-]', '', isbn_text)
            if isbn_clean:
                book_data['isbn'] = isbn_clean
        
        # Publication date
        pub_date_elem = book_element.query_selector('[class*="data"], [class*="ano"], .ano, [class*="year"], [data-year]')
        if pub_date_elem:
            book_data['publication_date'] = pub_date_elem.inner_text().strip()
        
        # Publisher
        publisher_elem = book_element.query_selector('[class*="editora"], .editora, .publisher, [class*="publisher"], [data-publisher]')
        if publisher_elem:
            book_data['publisher'] = publisher_elem.inner_text().strip()
        
        # My Rating - user's rating (look for stars, numbers, etc.)
        # Look for rating elements that show user's personal rating
        rating_elem = book_element.query_selector('[class*="rating"], [class*="nota"], .rating, .nota, [class*="estrela"], [data-rating], svg[class*="star"]')
        if rating_elem:
            rating_text = rating_elem.inner_text().strip()
            # Also check for aria-label or title attributes
            if not rating_text:
                rating_text = rating_elem.get_attribute('aria-label') or rating_elem.get_attribute('title') or ''
            if rating_text:
                # Extract numeric rating if present (e.g., "3.0" from "3.0 stars")
                rating_num = re.search(r'(\d+\.?\d*)', rating_text)
                if rating_num:
                    book_data['rating'] = rating_num.group(1)
                else:
                    book_data['rating'] = rating_text.strip()
        
        # Also try to find rating from text patterns (e.g., "3.0" in the book element)
        if not book_data.get('rating'):
            all_text = book_element.inner_text()
            # Look for patterns like "3.0" that might be ratings
            rating_match = re.search(r'\b(\d\.\d)\b', all_text)
            if rating_match:
                # Check if it's near rating-related text
                context = all_text[max(0, rating_match.start()-20):rating_match.end()+20].lower()
                if 'estrela' in context or 'rating' in context or 'nota' in context:
                    book_data['rating'] = rating_match.group(1)
        
        # Review/Notes
        review_elem = book_element.query_selector('[class*="review"], [class*="resenha"], .review, .resenha, [class*="nota-texto"], [data-review]')
        if review_elem:
            book_data['review'] = review_elem.inner_text().strip()
        
        # Date read
        read_date_elem = book_element.query_selector('[class*="data-leitura"], [class*="read-date"], [class*="data-lida"], [data-read-date]')
        if read_date_elem:
            book_data['date_read'] = read_date_elem.inner_text().strip()
        
        # Book link/URL - try multiple ways to find the book link
        # On React/Next.js sites, links might be in onClick handlers or data attributes
        book_url = None
        
        # Method 1: Try to find actual <a> tags with href
        link_selectors = [
            'a[href*="/pt/book/"]',
            'a[href*="/book/"]',
            'a[href*="/livro/"]',
        ]
        
        for selector in link_selectors:
            link_elem = book_element.query_selector(selector)
            if link_elem:
                try:
                    href = link_elem.get_attribute('href')
                    if not href:
                        href = link_elem.evaluate('(el) => el.href')
                    if href:
                        book_url = href
                        break
                except Exception:
                    continue
        
        # Method 2: Use JavaScript to find clickable elements and extract their navigation target
        # Also try clicking the image to see where it navigates
        if not book_url:
            try:
                # First, try to find the image and see if it has click handlers
                img_elem = book_element.query_selector('img[alt^="Capa do livro"]')
                if img_elem:
                    # Try to get the parent element that might have the click handler
                    try:
                        # Get the parent that likely contains the navigation
                        parent_elem = img_elem.evaluate('(img) => img.parentElement')
                        if parent_elem:
                            # Check if parent or any ancestor has an onclick or href
                            book_url = book_element.evaluate('''(img) => {
                                let current = img.parentElement;
                                for (let i = 0; i < 10 && current; i++) {
                                    // Check for href
                                    if (current.href && (current.href.includes('/book/') || current.href.includes('/livro/'))) {
                                        return current.href;
                                    }
                                    // Check for onclick that might navigate
                                    if (current.onclick) {
                                        const onclickStr = current.onclick.toString();
                                        const bookMatch = onclickStr.match(/['"](\\/pt\\/book\\/|\\/book\\/|\\/livro\\/)(\\d+)['"]/);
                                        if (bookMatch) {
                                            return 'https://www.skoob.com.br/pt/book/' + bookMatch[2];
                                        }
                                    }
                                    // Check data attributes
                                    const dataHref = current.getAttribute('data-href') || current.getAttribute('href');
                                    if (dataHref && (dataHref.includes('/book/') || dataHref.includes('/livro/'))) {
                                        return dataHref;
                                    }
                                    current = current.parentElement;
                                }
                                return null;
                            }''', img_elem)
                    except Exception as e:
                        logger.debug(f"Error checking image parent for navigation: {e}")
                
                # Fallback: try to find any clickable element
                if not book_url:
                    book_url = book_element.evaluate('''(container) => {
                        // Find all clickable elements (a, button, div with onClick)
                        const clickable = container.querySelector('a, button, [onclick], [role="button"]');
                        if (clickable) {
                            // If it's an <a> tag, get href
                            if (clickable.tagName === 'A' && clickable.href) {
                                return clickable.href;
                            }
                            // Check for data attributes
                            if (clickable.getAttribute('data-href')) {
                                return clickable.getAttribute('data-href');
                            }
                            // Check parent elements for href
                            let current = clickable.parentElement;
                            for (let i = 0; i < 5 && current; i++) {
                                if (current.tagName === 'A' && current.href) {
                                    return current.href;
                                }
                                current = current.parentElement;
                            }
                        }
                        // Try to find any link in the container
                        const anyLink = container.querySelector('a[href]');
                        if (anyLink && anyLink.href) {
                            return anyLink.href;
                        }
                        return null;
                    }''')
            except Exception as e:
                logger.debug(f"Error finding URL via JavaScript: {e}")
        
        # Method 3: Try to extract URL from React component props
        # This is more reliable than using image URLs (which contain edition IDs)
        if not book_url:
            try:
                img_elem = book_element.query_selector('img[alt^="Capa do livro"]')
                if img_elem:
                    # Try to find the actual navigation target by checking React props
                    book_url = img_elem.evaluate('''(img) => {
                        // Walk up the DOM tree to find the Link component
                        let current = img;
                        for (let i = 0; i < 10 && current; i++) {
                            // Check React Fiber props for href
                            const keys = Object.keys(current);
                            for (const key of keys) {
                                if (key.startsWith('__reactFiber') || key.startsWith('__reactInternalInstance')) {
                                    let fiber = current[key];
                                    for (let j = 0; j < 20 && fiber; j++) {
                                        if (fiber.memoizedProps) {
                                            const props = fiber.memoizedProps;
                                            // Check for href in props
                                            if (props.href && (props.href.includes('/book/') || props.href.includes('/livro/'))) {
                                                return props.href;
                                            }
                                            // Check for onClick that navigates
                                            if (props.onClick) {
                                                const onClickStr = props.onClick.toString();
                                                const match = onClickStr.match(/['"](\\/pt\\/book\\/|\\/book\\/|\\/livro\\/)(\\d+)['"]/);
                                                if (match) {
                                                    return 'https://www.skoob.com.br/pt/book/' + match[2];
                                                }
                                            }
                                        }
                                        fiber = fiber.return || fiber._debugOwner;
                                    }
                                }
                            }
                            current = current.parentElement;
                        }
                        return null;
                    }''')
            except Exception as e:
                logger.debug(f"Error extracting URL from React props: {e}")
        
        # Method 4: Extract book ID from data attributes and construct URL
        if not book_url:
            try:
                # Check for book ID in data attributes
                book_id = None
                data_attrs = ['data-book-id', 'data-livro-id', 'data-id', 'data-edition-id', 'data-editionId']
                for attr in data_attrs:
                    value = book_element.get_attribute(attr)
                    if value:
                        book_id = value
                        break
                
                # NOTE: Image URLs contain edition IDs, not book IDs!
                # We should NOT use image URLs to extract book IDs
                # The edition ID in the image URL (e.g., /livros/410286/) is NOT the book page ID
                # Instead, we rely on API response map or React props
                
                if book_id:
                    book_url = f"{SKOOB_BASE_URL}/pt/book/{book_id}"
                
                # Method 4: Try to extract href from Next.js Link component
                # The image is usually wrapped in a Next.js Link component with the correct href
                if not book_url:
                    try:
                        img_elem = book_element.query_selector('img[alt^="Capa do livro"]')
                        if img_elem:
                            # Find the parent Link component and extract its href
                            book_url = img_elem.evaluate('''(img) => {
                                // Walk up the DOM to find the Link component
                                let current = img;
                                for (let i = 0; i < 15 && current; i++) {
                                    // Check if current element has href (Link component)
                                    if (current.href && (current.href.includes('/book/') || current.href.includes('/livro/'))) {
                                        return current.href;
                                    }
                                    // Check for Next.js Link href attribute
                                    const href = current.getAttribute && current.getAttribute('href');
                                    if (href && (href.includes('/book/') || href.includes('/livro/'))) {
                                        // Make it absolute if relative
                                        if (href.startsWith('/')) {
                                            return 'https://www.skoob.com.br' + href;
                                        }
                                        return href;
                                    }
                                    // Check React props for href
                                    const keys = Object.keys(current);
                                    for (const key of keys) {
                                        if (key.startsWith('__reactFiber') || key.startsWith('__reactInternalInstance')) {
                                            let fiber = current[key];
                                            for (let j = 0; j < 25 && fiber; j++) {
                                                if (fiber.memoizedProps) {
                                                    const props = fiber.memoizedProps;
                                                    // Look for href in props (Next.js Link)
                                                    if (props.href && (props.href.includes('/book/') || props.href.includes('/livro/'))) {
                                                        const href = props.href;
                                                        if (href.startsWith('/')) {
                                                            return 'https://www.skoob.com.br' + href;
                                                        }
                                                        return href;
                                                    }
                                                    // Look for as prop (Next.js Link alternative)
                                                    if (props.as && (props.as.includes('/book/') || props.as.includes('/livro/'))) {
                                                        const href = props.as;
                                                        if (href.startsWith('/')) {
                                                            return 'https://www.skoob.com.br' + href;
                                                        }
                                                        return href;
                                                    }
                                                }
                                                fiber = fiber.return || fiber._debugOwner;
                                            }
                                        }
                                    }
                                    current = current.parentElement;
                                }
                                return null;
                            }''')
                    except Exception as e:
                        logger.debug(f"Error extracting href from Link component: {e}")
            except Exception as e:
                logger.debug(f"Error extracting book ID: {e}")
        
        # Method 5: Use book_id_map from API interception (especially for nocover books)
        if not book_url and book_data.get('title') and book_id_map:
            # Try exact match first
            book_id = book_id_map.get(book_data['title'].lower())
            if not book_id:
                # Try partial match (in case title has extra whitespace or slight differences)
                title_lower = book_data['title'].lower().strip()
                for map_title, map_id in book_id_map.items():
                    if title_lower in map_title or map_title in title_lower:
                        book_id = map_id
                        logger.debug(f"Found partial title match: '{book_data['title']}' -> '{map_title}'")
                        break
            
            if book_id:
                book_url = f"{SKOOB_BASE_URL}/pt/book/{book_id}"
                logger.debug(f"Constructed URL for '{book_data['title']}' from API map: {book_url}")
        
        # Normalize the URL
        if book_url:
            if book_url.startswith('/'):
                book_url = SKOOB_BASE_URL + book_url
            elif not book_url.startswith('http'):
                book_url = SKOOB_BASE_URL + '/' + book_url
            
            # Ensure URL uses /pt/book/ format
            if '/livro/' in book_url:
                book_url = book_url.replace('/livro/', '/pt/book/')
            
            # Only set if it looks like a book URL
            if '/book/' in book_url or '/livro/' in book_url:
                book_data['book_url'] = book_url
            else:
                logger.debug(f"URL doesn't look like a book URL: {book_url}")
                book_data.pop('book_url', None)
        
        # Extract any data attributes that might contain book info
        data_attrs = ['data-id', 'data-livro-id', 'data-book-id']
        for attr in data_attrs:
            value = book_element.get_attribute(attr)
            if value:
                book_data[attr.replace('data-', '').replace('-', '_')] = value
        
        # Note: raw_text extraction removed - user doesn't need percent read data
        
    except Exception as e:
        logger.warning(f"Error extracting book data: {e}")
    
    return book_data


def scrape_book_details_http(book_url):
    """Scrape detailed information from a book's detail page using HTTP requests (faster, no auth needed)."""
    details = {}
    
    try:
        # Use requests for faster HTTP access (no browser overhead)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(book_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text()
        
        # ISBN - look for ISBN-13 or ISBN text (format: ISBN-13: 9788516085773)
        isbn_match = re.search(r'ISBN[^:]*:?\s*([0-9-]+)', page_text, re.IGNORECASE)
        if isbn_match:
            details['isbn'] = isbn_match.group(1).strip()
        
        # Publisher - look for "Editora" (format: Editora Salamandra)
        # The text shows: "Editora Salamandra201340 páginas" - they're concatenated
        # Extract publisher name (letters/spaces) between "Editora" and a 4-digit year
        publisher_match = re.search(r'Editora\s+([A-Za-z][A-Za-z\s]+?)(?=\d{4})', page_text, re.IGNORECASE)
        if publisher_match:
            details['publisher'] = publisher_match.group(1).strip()
        
        # Year Published - look for 4-digit year after publisher, before pages
        # Pattern: "Editora Salamandra201340 páginas" - extract the 4-digit year
        year_match = re.search(r'Editora[^\d]*(\d{4})(?=\d+\s*páginas)', page_text, re.IGNORECASE)
        if year_match:
            details['year_published'] = year_match.group(1).strip()
        else:
            # Fallback: find 4-digit year followed by number and "páginas"
            year_match = re.search(r'(\d{4})(\d+)\s*páginas', page_text, re.IGNORECASE)
            if year_match:
                details['year_published'] = year_match.group(1).strip()
        
        # Pages - look for number before "páginas" but after year
        # Pattern: "201340 páginas" - we want "40", not "201340"
        # Extract the last digits before "páginas" that are reasonable (1-9999)
        pages_match = re.search(r'(\d{4})(\d{1,4})\s*páginas', page_text, re.IGNORECASE)
        if pages_match:
            # The second group is the pages number
            details['pages'] = pages_match.group(2).strip()
        else:
            # Fallback: just find number before "páginas" (but exclude very large numbers)
            pages_match = re.search(r'(\d{1,4})\s*páginas', page_text, re.IGNORECASE)
            if pages_match:
                try:
                    pages_value = int(pages_match.group(1))
                    if pages_value < 10000:
                        details['pages'] = str(pages_value)
                except ValueError:
                    pass
        
        # Average Rating - look for rating in "Avaliações" section
        # Try "4.4 / 153" format first (more reliable)
        rating_match = re.search(r'Avaliações\s+(\d+\.?\d*)\s*/\s*\d+', page_text, re.IGNORECASE)
        if rating_match:
            details['average_rating'] = rating_match.group(1).strip()
        else:
            # Try "4.4 / 153" format anywhere (but avoid dates like "19/02/2023")
            rating_match = re.search(r'(\d+\.\d+)\s*/\s*\d{2,}', page_text)
            if rating_match:
                # Check if it's not a date (ratings are typically 0-5)
                rating_value = rating_match.group(1)
                try:
                    if float(rating_value) <= 5.0:
                        details['average_rating'] = rating_value.strip()
                except ValueError:
                    pass
        
        # Binding - look for format information (hardcover, paperback, etc.)
        # This might not be available on Skoob, but we'll try
        binding_match = re.search(r'(Capa\s+(?:dura|mole|flexível)|Hardcover|Paperback)', page_text, re.IGNORECASE)
        if binding_match:
            details['binding'] = binding_match.group(1).strip()
        
    except Exception as e:
        logger.debug(f"Error scraping book details from {book_url}: {e}")
    
    return details


def scrape_book_details_batch(book_urls, max_workers=10):
    """Scrape book details in parallel for multiple books."""
    results = {}
    
    def fetch_details(book_url):
        return book_url, scrape_book_details_http(book_url)
    
    # Use ThreadPoolExecutor to parallelize requests
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_url = {executor.submit(fetch_details, url): url for url in book_urls}
        
        # Collect results as they complete
        for future in as_completed(future_to_url):
            try:
                book_url, details = future.result()
                results[book_url] = details
            except Exception as e:
                book_url = future_to_url[future]
                logger.warning(f"Error fetching details for {book_url}: {e}")
                results[book_url] = {}
    
    return results


def convert_api_to_csv_format(api_item):
    """Scrape all books from the Estante page."""
    books = []
    page_num = 1
    # Store book IDs from API responses
    book_id_map = {}  # Maps book title/author to book ID
    
    try:
        # Intercept API responses to extract book IDs
        def handle_response(response):
            try:
                url = response.url
                # Look for bookshelf API endpoints
                if '/api/v2/bookshelf' in url or '/api/bookshelf' in url or 'bookshelf' in url.lower():
                    try:
                        json_data = response.json()
                        logger.debug(f"API Response from {url}: {str(json_data)[:500]}")
                        
                        # Try to extract book IDs from the response
                        if isinstance(json_data, dict):
                            # Look for books array in various possible locations
                            books_data = (json_data.get('books', []) or 
                                        json_data.get('data', []) or 
                                        json_data.get('items', []) or
                                        json_data.get('results', []))
                            
                            if not books_data and isinstance(json_data.get('data'), dict):
                                # Sometimes data is a dict with books inside
                                books_data = json_data['data'].get('books', []) or json_data['data'].get('items', [])
                            
                            for book in books_data:
                                if isinstance(book, dict):
                                    # Prioritize book_id over edition_id
                                    # book_id is the actual book page ID, edition_id is just for the cover image
                                    book_id = (book.get('book_id') or 
                                             book.get('bookId') or
                                             book.get('id'))  # Sometimes 'id' is the book_id
                                    
                                    # Also check nested book object
                                    if not book_id and isinstance(book.get('book'), dict):
                                        book_id = (book['book'].get('id') or 
                                                 book['book'].get('book_id') or
                                                 book['book'].get('bookId'))
                                    
                                    title = book.get('title') or book.get('name')
                                    edition_id = book.get('edition_id') or book.get('editionId')
                                    
                                    if book_id and title:
                                        book_id_map[title.lower()] = str(book_id)
                                        logger.debug(f"API: Mapped '{title}' -> book_id {book_id} (edition_id: {edition_id})")
                                    elif title:
                                        # Log when we have title but no book_id
                                        logger.warning(f"API: Found '{title}' but no book_id (has edition_id: {edition_id}, keys: {list(book.keys())})")
                    except Exception as e:
                        logger.debug(f"Error parsing API response from {url}: {e}")
            except Exception:
                pass
        
        page.on('response', handle_response)
        # Navigate to Estante page using hardcoded URL
        estante_url = ESTANTE_URL
        
        while True:
            try:
                logger.info(f"Navigating to Estante page {page_num}: {estante_url}")
                # Increase timeout and use domcontentloaded instead of networkidle for faster loading
                page.goto(estante_url, wait_until='domcontentloaded', timeout=60000)
                
                # Wait for React content to load - look for book cover images
                logger.info("Waiting for page content to load...")
                try:
                    # Wait for at least one book cover image to appear with longer timeout
                    page.wait_for_selector('img[alt^="Capa do livro"]', timeout=30000)
                    time.sleep(4)  # Additional wait for all content to render
                    logger.info("Book images detected, proceeding with scraping...")
                except PlaywrightTimeoutError:
                    logger.warning("Book images not found after waiting. Checking page content...")
                    # Try to see what's on the page
                    all_images = page.query_selector_all('img')
                    logger.info(f"Found {len(all_images)} total images on page")
                    book_images = page.query_selector_all('img[alt^="Capa do livro"]')
                    logger.info(f"Found {len(book_images)} book cover images")
                    if not book_images:
                        logger.warning(f"No book images found on page {page_num}. This page might be empty or still loading.")
                    time.sleep(3)
                
                # DEBUG: Save page information for analysis (only on first page)
                if page_num == 1:
                    logger.info("Saving debug information for page analysis...")
                    try:
                        debug_dir = Path("debug_info")
                        debug_dir.mkdir(exist_ok=True)
                        
                        # Save full page HTML
                        html_content = page.content()
                        html_file = debug_dir / f"page_{page_num}_full_html_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        logger.info(f"Saved full HTML to: {html_file}")
                        
                        # Find book containers and save their structure
                        containers = page.query_selector_all('div.relative.flex.flex-col')
                        logger.info(f"Found {len(containers)} potential book containers")
                        
                        # Analyze first few books in detail
                        debug_info = []
                        for i, container in enumerate(containers[:5]):  # Analyze first 5 books
                            try:
                                img = container.query_selector('img[alt^="Capa do livro"]')
                                if img:
                                    book_info = {
                                        'index': i,
                                        'html': container.inner_html()[:2000],  # First 2000 chars
                                        'text': container.inner_text()[:500],
                                        'attributes': {}
                                    }
                                    
                                    # Get all attributes from the container
                                    attrs = container.evaluate('''(el) => {
                                        const attrs = {};
                                        for (let attr of el.attributes) {
                                            attrs[attr.name] = attr.value;
                                        }
                                        return attrs;
                                    }''')
                                    book_info['attributes'] = attrs
                                    
                                    # Find all links in the container
                                    links_info = container.evaluate('''(container) => {
                                        const links = container.querySelectorAll('a');
                                        const result = [];
                                        links.forEach(link => {
                                            result.push({
                                                href: link.href || link.getAttribute('href'),
                                                text: link.innerText.substring(0, 100),
                                                tagName: link.tagName,
                                                className: link.className,
                                                id: link.id,
                                                onclick: link.getAttribute('onclick'),
                                                dataAttrs: {}
                                            });
                                            // Get data attributes
                                            Array.from(link.attributes).forEach(attr => {
                                                if (attr.name.startsWith('data-')) {
                                                    result[result.length - 1].dataAttrs[attr.name] = attr.value;
                                                }
                                            });
                                        });
                                        return result;
                                    }''')
                                    book_info['links'] = links_info
                                    
                                    # Try to find clickable elements
                                    clickable_info = container.evaluate('''(container) => {
                                        const clickable = container.querySelector('[onclick], [role="button"], button, [data-href]');
                                        if (clickable) {
                                            return {
                                                tagName: clickable.tagName,
                                                className: clickable.className,
                                                onclick: clickable.getAttribute('onclick'),
                                                href: clickable.href || clickable.getAttribute('href'),
                                                dataHref: clickable.getAttribute('data-href'),
                                                role: clickable.getAttribute('role'),
                                                allAttrs: {}
                                            };
                                        }
                                        return null;
                                    }''')
                                    book_info['clickable'] = clickable_info
                                    
                                    # Try React Fiber approach
                                    react_info = container.evaluate('''(container) => {
                                        const keys = Object.keys(container);
                                        const found = [];
                                        for (const key of keys) {
                                            if (key.startsWith('__reactFiber') || key.startsWith('__reactInternalInstance')) {
                                                let fiber = container[key];
                                                for (let i = 0; i < 20 && fiber; i++) {
                                                    if (fiber.memoizedProps) {
                                                        const props = fiber.memoizedProps;
                                                        if (props.href || props.bookId || props.editionId || props.to) {
                                                            found.push({
                                                                href: props.href,
                                                                bookId: props.bookId,
                                                                editionId: props.editionId,
                                                                to: props.to,
                                                                allProps: Object.keys(props)
                                                            });
                                                        }
                                                    }
                                                    fiber = fiber.return || fiber._debugOwner;
                                                }
                                            }
                                        }
                                        return found;
                                    }''')
                                    book_info['react_data'] = react_info
                                    
                                    debug_info.append(book_info)
                            except Exception as e:
                                logger.debug(f"Error analyzing container {i}: {e}")
                        
                        # Save debug info as JSON
                        debug_json = debug_dir / f"page_{page_num}_book_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(debug_json, 'w', encoding='utf-8') as f:
                            json.dump(debug_info, f, indent=2, ensure_ascii=False)
                        logger.info(f"Saved book analysis to: {debug_json}")
                        
                        # Also save a summary text file
                        summary_file = debug_dir / f"page_{page_num}_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        with open(summary_file, 'w', encoding='utf-8') as f:
                            f.write(f"Page {page_num} Debug Summary\n")
                            f.write("=" * 50 + "\n\n")
                            f.write(f"Total containers found: {len(containers)}\n")
                            f.write(f"Books analyzed: {len(debug_info)}\n\n")
                            for i, book in enumerate(debug_info):
                                f.write(f"\n--- Book {i+1} ---\n")
                                f.write(f"Attributes: {book.get('attributes', {})}\n")
                                f.write(f"Links found: {len(book.get('links', []))}\n")
                                for link in book.get('links', []):
                                    f.write(f"  - href: {link.get('href')}\n")
                                    f.write(f"    text: {link.get('text', '')[:50]}\n")
                                f.write(f"Clickable: {book.get('clickable')}\n")
                                f.write(f"React data: {book.get('react_data')}\n")
                        logger.info(f"Saved summary to: {summary_file}")
                        
                    except Exception as e:
                        logger.warning(f"Error saving debug information: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
            except PlaywrightTimeoutError as e:
                logger.error(f"Timeout while loading page {page_num}: {e}")
                logger.warning(f"Skipping page {page_num} due to timeout. Continuing to next page...")
                # Skip this page and continue to next
                page_books = []
                books.extend(page_books)
                logger.info(f"Page {page_num}: Extracted 0 books due to timeout (Total: {len(books)})")
                
                # Still try to construct next page URL
                next_page_num = page_num + 1
                if next_page_num > 18:
                    logger.info(f"Reached maximum page limit (18). Stopping pagination.")
                    break
            
                # Construct next URL, preserving filter
                base_url = estante_url.split('?')[0]
                if '?' in estante_url:
                    url_without_page = re.sub(r'[?&]page=\d+', '', estante_url)
                    if 'filter=' in url_without_page:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}"
                    else:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}&filter=read"
                else:
                    next_url = f"{base_url}?page={next_page_num}&filter=read"
                
                estante_url = next_url
                page_num += 1
                time.sleep(2)  # Brief pause before retrying
                continue
            except Exception as e:
                logger.error(f"Unexpected error loading page {page_num}: {e}")
                logger.warning(f"Skipping page {page_num} due to error. Continuing to next page...")
                # Skip this page and continue to next
                page_books = []
                books.extend(page_books)
                logger.info(f"Page {page_num}: Extracted 0 books due to error (Total: {len(books)})")
                
                # Still try to construct next page URL
                next_page_num = page_num + 1
                if next_page_num > 18:
                    logger.info(f"Reached maximum page limit (18). Stopping pagination.")
                    break
                
                # Construct next URL, preserving filter
                base_url = estante_url.split('?')[0]
                if '?' in estante_url:
                    url_without_page = re.sub(r'[?&]page=\d+', '', estante_url)
                    if 'filter=' in url_without_page:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}"
                    else:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}&filter=read"
                else:
                    next_url = f"{base_url}?page={next_page_num}&filter=read"
                
                estante_url = next_url
                page_num += 1
                time.sleep(2)  # Brief pause before retrying
                continue
            
            # Find book elements by looking for containers with book cover images
            # The structure is: div.relative.flex.flex-col contains img[alt^="Capa do livro"]
            logger.info("Looking for book containers...")
            
            # Find all containers that have book images
            # Simple approach: find all divs with the right classes that contain book images
            book_elements = []
            
            # First, check if book images exist on the page
            book_images = page.query_selector_all('img[alt^="Capa do livro"]')
            logger.info(f"Found {len(book_images)} book cover images on page")
            
            if not book_images:
                logger.warning("No book images found! Page might not have loaded correctly.")
                # Save debug page
                debug_file = f"debug_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                logger.info(f"Page HTML saved to {debug_file} for debugging")
            
            # Find all divs with the right classes that contain book images
            containers = page.query_selector_all('div')
            seen_containers = set()
            containers_checked = 0
            
            for container in containers:
                try:
                    containers_checked += 1
                    classes = container.get_attribute('class') or ''
                    if 'relative' in classes and 'flex' in classes and 'flex-col' in classes:
                        # Check if this container has a book image
                        img = container.query_selector('img[alt^="Capa do livro"]')
                        if img:
                            # Use container's object id as a unique identifier to avoid duplicates
                            container_id = id(container)
                            if container_id not in seen_containers:
                                seen_containers.add(container_id)
                                book_elements.append(container)
                except Exception as e:
                    logger.debug(f"Error checking container: {e}")
                    continue
            
            logger.info(f"Checked {containers_checked} divs, found {len(book_elements)} unique book containers")
            
            # Extract data from each book
            logger.info(f"Extracting data from {len(book_elements)} books on page {page_num}...")
            page_books = []
            book_urls_to_fetch = []
            
            # First pass: extract basic data and collect URLs
            # We'll extract data first, then click to get URLs in a second pass to avoid stale handles
            page_books = []
            
            # Extract basic data from all books first (without clicking)
            for i, book_elem in enumerate(book_elements, 1):
                try:
                    book_data = extract_book_data(book_elem, book_id_map=book_id_map)
                    if book_data.get('title'):  # Only add if we found at least a title
                        page_books.append(book_data)
                        logger.info(f"Extracted book {i}/{len(book_elements)}: {book_data.get('title', 'Unknown')} (URL: {book_data.get('book_url', 'None')})")
                    else:
                        logger.debug(f"Skipping element {i} - no title found")
                except Exception as e:
                    logger.warning(f"Error processing book {i}: {e}")
                    continue
            
            # Second pass: click each book to get the correct URL
            # Re-query elements to avoid stale handles
            book_elements = page.query_selector_all('div.relative.flex.flex-col')
            
            for i, book_data in enumerate(page_books, 1):
                try:
                    # ALWAYS click the image to intercept navigation and get the correct URL
                    # This ensures we get the book ID, not the edition ID
                    if i <= len(book_elements):
                        current_book_elem = book_elements[i-1]
                        img_elem = current_book_elem.query_selector('img[alt^="Capa do livro"]')
                        if img_elem:
                            # Click the image and wait for navigation to complete
                            # Then get the final URL from the page
                            try:
                                with page.expect_navigation(timeout=5000, wait_until='domcontentloaded') as navigation_info:
                                    img_elem.click(timeout=2000)
                                
                                # Get the final URL after navigation
                                nav_url = navigation_info.value.url if navigation_info.value else page.url
                                
                                # Filter out JavaScript chunks and other non-book URLs
                                if '/pt/book/' in nav_url or '/book/' in nav_url:
                                    # Extract just the book page URL (not JS chunks)
                                    if '/_next/' not in nav_url and '.js' not in nav_url:
                                        book_data['book_url'] = nav_url
                                        logger.debug(f"Captured URL from navigation for '{book_data['title']}': {nav_url}")
                                    else:
                                        # Try to extract book ID from URL pattern
                                        import re
                                        match = re.search(r'/book/(\d+)', nav_url)
                                        if match:
                                            book_id = match.group(1)
                                            book_data['book_url'] = f"{SKOOB_BASE_URL}/pt/book/{book_id}"
                                            logger.debug(f"Extracted book ID from URL for '{book_data['title']}': {book_data['book_url']}")
                                        else:
                                            logger.warning(f"Got non-book URL for '{book_data['title']}': {nav_url}")
                                else:
                                    logger.warning(f"Navigation did not go to book page for '{book_data['title']}': {nav_url}")
                                
                                # Navigate back to bookshelf
                                try:
                                    page.go_back(timeout=5000)
                                    # Wait for page to load
                                    page.wait_for_selector('img[alt^="Capa do livro"]', timeout=10000)
                                    # Re-query book elements after navigation to avoid stale handles
                                    book_elements = page.query_selector_all('div.relative.flex.flex-col')
                                except Exception as e:
                                    logger.warning(f"Error navigating back after clicking '{book_data['title']}': {e}")
                                    # If back fails, re-navigate to bookshelf
                                    try:
                                        page.goto(estante_url, timeout=60000, wait_until='domcontentloaded')
                                        page.wait_for_selector('img[alt^="Capa do livro"]', timeout=30000)
                                        # Re-query book elements after navigation
                                        book_elements = page.query_selector_all('div.relative.flex.flex-col')
                                    except Exception as e2:
                                        logger.error(f"Failed to return to bookshelf page: {e2}")
                            except Exception as nav_error:
                                # Navigation timeout or error - try alternative approach
                                logger.debug(f"Navigation timeout/error for '{book_data['title']}': {nav_error}")
                                # Try to get URL from the click event or element's href
                                try:
                                    # Re-query element in case it's stale
                                    book_elements = page.query_selector_all('div.relative.flex.flex-col')
                                    if i <= len(book_elements):
                                        current_book_elem = book_elements[i-1]
                                        img_elem = current_book_elem.query_selector('img[alt^="Capa do livro"]')
                                        if img_elem:
                                            # Get href from the parent link element
                                            href = img_elem.evaluate('''(img) => {
                                                let current = img;
                                                for (let i = 0; i < 10 && current; i++) {
                                                    if (current.href && (current.href.includes('/book/') || current.href.includes('/livro/'))) {
                                                        return current.href;
                                                    }
                                                    const href = current.getAttribute && current.getAttribute('href');
                                                    if (href && (href.includes('/book/') || href.includes('/livro/'))) {
                                                        return href.startsWith('/') ? 'https://www.skoob.com.br' + href : href;
                                                    }
                                                    current = current.parentElement;
                                                }
                                                return null;
                                            }''')
                                            if href and '/_next/' not in href and '.js' not in href:
                                                book_data['book_url'] = href
                                                logger.debug(f"Got URL from element href for '{book_data['title']}': {href}")
                                except Exception as e:
                                    logger.debug(f"Error getting href from element for '{book_data['title']}': {e}")
                        else:
                            logger.warning(f"Could not find image element for book {i} '{book_data['title']}'")
                    else:
                        logger.warning(f"Could not find book element at index {i-1} for '{book_data['title']}'")
                except Exception as e:
                    logger.debug(f"Error trying to get URL via click for '{book_data['title']}': {e}")
            
            # Collect URLs for detail fetching
            book_urls_to_fetch = []
            for book_data in page_books:
                if book_data.get('book_url'):
                    book_urls_to_fetch.append(book_data['book_url'])
                else:
                    logger.warning(f"Book '{book_data.get('title', 'Unknown')}' has no URL - cannot fetch details")
            
            # Second pass: fetch book details in parallel (much faster!)
            if book_urls_to_fetch:
                logger.info(f"Fetching details for {len(book_urls_to_fetch)} books in parallel...")
                start_time = time.time()
                details_results = scrape_book_details_batch(book_urls_to_fetch, max_workers=15)
                elapsed = time.time() - start_time
                logger.info(f"Fetched details for {len(details_results)} books in {elapsed:.2f} seconds")
                
                # Merge details into book_data
                merged_count = 0
                for book_data in page_books:
                    if book_data.get('book_url') and book_data['book_url'] in details_results:
                        book_details = details_results[book_data['book_url']]
                        # Merge details (book_details take precedence)
                        book_data.update(book_details)
                        merged_count += 1
                        logger.debug(f"Added details for: {book_data.get('title', 'Unknown')}")
                
                logger.info(f"Merged details for {merged_count}/{len(page_books)} books")
            else:
                logger.warning(f"No book URLs found to fetch details for! Check if book URL extraction is working.")
            
            books.extend(page_books)
            logger.info(f"Page {page_num}: Extracted {len(page_books)} books (Total: {len(books)})")
            
            # Check for pagination - construct next page URL using ?page= format
            next_page_num = page_num + 1
            
            # Check if we've reached the maximum page (18) before constructing URL
            if next_page_num > 18:
                logger.info(f"Reached maximum page limit (18). Stopping pagination.")
                break
            
            next_url = None
            try:
                # First, try to find a next page button/link
                next_selectors = [
                    'a[class*="next"]',
                    'a[class*="proximo"]',
                    '.pagination a:has-text("Próxima")',
                    '.pagination a:has-text("Next")',
                    '.pagination a:has-text(">")',
                    'a[aria-label*="próxima" i]',
                    'a[aria-label*="next" i]'
                ]
                
                for selector in next_selectors:
                    try:
                        next_button = page.query_selector(selector)
                        if next_button:
                            # Check if it's actually a next button and not disabled
                            is_disabled = next_button.get_attribute('disabled') or 'disabled' in (next_button.get_attribute('class') or '')
                            if not is_disabled and next_button.is_visible():
                                href = next_button.get_attribute('href')
                                if href:
                                    if href.startswith('/'):
                                        next_url = SKOOB_BASE_URL + href
                                    elif href.startswith('http'):
                                        next_url = href
                                    break
                    except Exception:
                        continue
                
                # If no next button found, construct next page URL manually
                if not next_url:
                    # Parse current URL to get base and preserve filter parameter
                    base_url = estante_url.split('?')[0]  # Remove query params
                    
                    # Construct next URL with ?page= parameter, preserving filter=read
                    if '?' in estante_url:
                        # Remove existing page parameter but keep filter
                        url_without_page = re.sub(r'[?&]page=\d+', '', estante_url)
                        # Check if filter is already in URL
                        if 'filter=' in url_without_page:
                            separator = '&' if '?' in url_without_page else '?'
                            next_url = f"{url_without_page}{separator}page={next_page_num}"
                    else:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}&filter=read"
                else:
                    # Add both page and filter parameters
                    next_url = f"{base_url}?page={next_page_num}&filter=read"
                
            except Exception as e:
                logger.debug(f"Pagination check error: {e}")
                # Fallback: construct next page URL, preserving filter
                base_url = estante_url.split('?')[0]
                if '?' in estante_url:
                    url_without_page = re.sub(r'[?&]page=\d+', '', estante_url)
                    if 'filter=' in url_without_page:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}"
                    else:
                        separator = '&' if '?' in url_without_page else '?'
                        next_url = f"{url_without_page}{separator}page={next_page_num}&filter=read"
                else:
                    next_url = f"{base_url}?page={next_page_num}&filter=read"
            
            if not page_books and page_num > 1:
                logger.info("No books found on this page. Scraping complete.")
                break
            
            # Verify next page exists by checking if URL is different
            if next_url == estante_url:
                logger.info("Next page URL is same as current. Stopping pagination.")
                break
            
            estante_url = next_url
            page_num += 1
            
            # Add delay between pages to respect rate limiting
            time.sleep(1)
            
            # Safety limit to prevent infinite loops
            if page_num > 100:
                logger.warning("Reached maximum page limit (100). Stopping.")
                break
        
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout while loading Estante page: {e}")
        logger.info(f"Returning {len(books)} books scraped so far")
    except Exception as e:
        logger.error(f"Error scraping Estante: {e}")
        logger.info(f"Returning {len(books)} books scraped so far")
    
    return books


def convert_api_to_csv_format(api_item):
    """
    Convert API response item to CSV format.
    
    Args:
        api_item: Dictionary from API response items array
    
    Returns:
        Dictionary with CSV-compatible field names
    """
    csv_book = {}
    
    # Direct mappings
    if 'title' in api_item:
        csv_book['title'] = api_item['title']
    if 'author' in api_item:
        csv_book['author'] = api_item['author']
    if 'rating' in api_item:
        csv_book['rating'] = api_item['rating']
    if 'year' in api_item:
        csv_book['year_published'] = api_item['year']
    if 'pages' in api_item:
        csv_book['pages'] = api_item['pages']
    if 'publisher' in api_item:
        csv_book['publisher'] = api_item['publisher']
    if 'finished_at' in api_item:
        # Convert ISO date to readable format
        try:
            if api_item['finished_at']:
                date_obj = datetime.fromisoformat(api_item['finished_at'].replace('Z', '+00:00'))
                csv_book['date_read'] = date_obj.strftime('%Y-%m-%d')
        except:
            csv_book['date_read'] = api_item['finished_at']
    if 'cover_filename' in api_item:
        csv_book['cover_url'] = api_item['cover_filename']
    
    # Construct book URL from slug
    if 'slug' in api_item:
        slug = api_item['slug']
        if slug.startswith('http'):
            csv_book['book_url'] = slug
        else:
            csv_book['book_url'] = f"{SKOOB_BASE_URL}/{slug}"
    
    # Fields not in API - will be filled later from book pages
    csv_book['isbn'] = None
    csv_book['average_rating'] = None
    csv_book['binding'] = None
    csv_book['original_publication_year'] = None
    csv_book['date_added'] = None
    csv_book['shelves'] = None
    csv_book['bookshelves'] = None
    csv_book['review'] = None
    
    return csv_book


def export_to_csv(books, filename=None):
    """Export books data to CSV file."""
    if not books:
        logger.warning("No books to export")
        return None
    
    # Generate filename with timestamp if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"skoob_estante_{timestamp}.csv"
    
    # Collect all unique field names from all books
    all_fields = set()
    for book in books:
        all_fields.update(book.keys())
    
    # Sort fields, but put common ones first
    # Fields requested: Title, Author, ISBN, My Rating, Average Rating, Publisher, 
    # Binding, Year Published, Original Publication Year, Date Read, Date Added,
    # Shelves, Bookshelves, My Review
    common_fields = [
        'title', 'author', 'isbn', 'rating', 'average_rating', 'publisher',
        'binding', 'year_published', 'original_publication_year', 'date_read',
        'date_added', 'shelves', 'bookshelves', 'review', 'pages', 'book_url'
    ]
    # Remove cover_url and raw_text from all_fields if present
    all_fields.discard('cover_url')
    all_fields.discard('raw_text')
    field_order = [f for f in common_fields if f in all_fields]
    field_order.extend(sorted([f for f in all_fields if f not in common_fields]))
    
    # Write to CSV
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_order, extrasaction='ignore')
            writer.writeheader()
            for book in books:
                writer.writerow(book)
        
        logger.info(f"Exported {len(books)} books to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return None


def main(debug=False):
    """
    Main execution function.
    
    Args:
        debug: If True, enable debug logging and save debug files
    """
    logger.info("Starting Skoob Bookshelf Scraper...")
    
    # Import API request module
    try:
        from api_request import fetch_bookshelf_data
    except ImportError as e:
        logger.error(f"Failed to import api_request module: {e}")
        logger.error("Make sure api_request.py is in the same directory")
        return
    
    # Fetch data from API
    logger.info("Fetching bookshelf data from API...")
    api_data = fetch_bookshelf_data(debug=debug)
    
    if not api_data or not api_data.get('items'):
        logger.error("Failed to fetch data from API or no items found")
        return
    
    items = api_data.get('items', [])
    logger.info(f"Fetched {len(items)} books from API")
    
    # Convert API items to CSV format
    books = []
    book_urls = []
    for item in items:
        csv_book = convert_api_to_csv_format(item)
        books.append(csv_book)
        if csv_book.get('book_url'):
            book_urls.append(csv_book['book_url'])
    
    # Fetch missing fields from individual book pages
    if book_urls:
        logger.info(f"Fetching missing details (ISBN, average_rating, binding) for {len(book_urls)} books...")
        details_results = scrape_book_details_batch(book_urls, max_workers=15)
        
        # Merge details into books
        for book in books:
            book_url = book.get('book_url')
            if book_url and book_url in details_results:
                details = details_results[book_url]
                # Update with fetched details (don't overwrite existing data)
                if details.get('isbn'):
                    book['isbn'] = details['isbn']
                if details.get('average_rating'):
                    book['average_rating'] = details['average_rating']
                if details.get('binding'):
                    book['binding'] = details['binding']
                if details.get('original_publication_year'):
                    book['original_publication_year'] = details.get('original_publication_year')
    
    if books:
        logger.info(f"Successfully processed {len(books)} books")
        # Export to CSV
        csv_file = export_to_csv(books)
        if csv_file:
            logger.info(f"Data exported successfully to {csv_file}")
        else:
            logger.error("Failed to export data to CSV")
    else:
        logger.warning("No books were processed")
    
    logger.info("Done!")


if __name__ == "__main__":
    import sys
    
    # Check for debug flag
    debug = "--debug" in sys.argv or "-d" in sys.argv
    
    # Set logging level based on debug flag
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")
    else:
        logging.getLogger().setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
    
    main(debug=debug)

