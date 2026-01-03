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
    total = len(book_urls)
    completed = 0
    
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
                completed += 1
                # Log progress every 10 books or on completion
                if completed % 10 == 0 or completed == total:
                    percentage = (completed / total) * 100
                    logger.info(f"Progress: {completed}/{total} books processed ({percentage:.1f}%)")
            except Exception as e:
                book_url = future_to_url[future]
                logger.warning(f"Error fetching details for {book_url}: {e}")
                results[book_url] = {}
                completed += 1
                # Log progress even on errors
                if completed % 10 == 0 or completed == total:
                    percentage = (completed / total) * 100
                    logger.info(f"Progress: {completed}/{total} books processed ({percentage:.1f}%)")
    
    return results


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

