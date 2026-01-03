# Skoob Bookshelf Scraper

A Python script to scrape your book collection from Skoob (https://www.skoob.com.br) and export it to CSV.

## Features

- Scrapes all books from your Skoob bookshelf (read books only, filtered)
- Extracts detailed book information including ISBN, publisher, publication year, pages, ratings, and more
- Handles books with and without cover images
- Parallel processing for faster data retrieval
- Automatic pagination through all pages
- Exports to CSV with UTF-8 encoding

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

## Usage

1. Edit `skoob_scraper.py` and update the `ESTANTE_URL` constant with your Skoob bookshelf URL:
```python
ESTANTE_URL = "https://www.skoob.com.br/pt/user/YOUR_USER_ID/bookshelf?filter=read"
```

2. Run the script:
```bash
python skoob_scraper.py
```

3. The script will open a browser window to the Skoob login page.

4. Log in manually in the browser window.

5. Once logged in, return to the terminal and press Enter to continue.

6. The script will automatically navigate to your Estante (bookshelf) and scrape all book information.

7. The data will be exported to a CSV file with a timestamp (e.g., `skoob_estante_20240101_120000.csv`).

## Output

The CSV file will contain all available book information including:
- Title
- Author(s)
- ISBN
- Publisher
- Year Published
- Original Publication Year
- Pages
- Binding
- Average Rating
- My Rating
- Date Read
- Date Added
- Shelves
- Bookshelves
- My Review
- Book URL

## Notes

- The script filters for "read" books only using `?filter=read`
- Parallel processing is used to fetch book details faster
- All data is exported with UTF-8 encoding to properly handle Portuguese characters
- The browser window will remain open during scraping so you can monitor progress
- Books without cover images are handled automatically
