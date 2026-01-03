#!/usr/bin/env python3
"""Test script to debug book URL extraction from bookshelf page."""

from playwright.sync_api import sync_playwright
import time

def test_book_url_extraction():
    """Test extracting book URLs from a bookshelf page."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Navigate to bookshelf (assuming already logged in)
            url = "https://www.skoob.com.br/pt/user/67bd0d5270c4abc337699ac9/bookshelf?filter=read"
            print(f"Navigating to: {url}")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(5)  # Wait for content to load
            
            # Wait for book images
            print("Waiting for book images...")
            page.wait_for_selector('img[alt^="Capa do livro"]', timeout=30000)
            
            # Find book containers
            print("Finding book containers...")
            containers = page.query_selector_all('div.relative.flex.flex-col')
            
            print(f"Found {len(containers)} containers")
            
            # Test first book
            if containers:
                first_book = containers[0]
                print("\n=== Testing first book ===")
                
                # Get all HTML to see structure
                html = first_book.inner_html()
                print(f"HTML length: {len(html)}")
                print(f"First 500 chars of HTML:\n{html[:500]}")
                
                # Try to find links
                links = first_book.query_selector_all('a')
                print(f"\nFound {len(links)} <a> tags")
                for i, link in enumerate(links):
                    href = link.get_attribute('href')
                    text = link.inner_text()[:50]
                    print(f"  Link {i+1}: href='{href}', text='{text}'")
                
                # Try JavaScript evaluation
                print("\n=== JavaScript evaluation ===")
                try:
                    result = first_book.evaluate('''(container) => {
                        const result = {
                            links: [],
                            clickable: [],
                            dataAttrs: {}
                        };
                        
                        // Find all links
                        const links = container.querySelectorAll('a');
                        links.forEach(link => {
                            result.links.push({
                                href: link.href,
                                text: link.innerText.substring(0, 50),
                                hasOnClick: !!link.onclick
                            });
                        });
                        
                        // Find clickable elements
                        const clickable = container.querySelector('[onclick], [role="button"], button');
                        if (clickable) {
                            result.clickable.push({
                                tag: clickable.tagName,
                                onclick: clickable.getAttribute('onclick'),
                                href: clickable.href || clickable.getAttribute('href'),
                                dataHref: clickable.getAttribute('data-href')
                            });
                        }
                        
                        // Get all data attributes
                        const allElements = container.querySelectorAll('*');
                        allElements.forEach(el => {
                            Array.from(el.attributes).forEach(attr => {
                                if (attr.name.startsWith('data-')) {
                                    result.dataAttrs[attr.name] = attr.value;
                                }
                            });
                        });
                        
                        return result;
                    }''')
                    print(f"Links found: {len(result['links'])}")
                    for link in result['links']:
                        print(f"  - href: {link['href']}, text: {link['text']}")
                    print(f"\nClickable elements: {result['clickable']}")
                    print(f"\nData attributes: {result['dataAttrs']}")
                except Exception as e:
                    print(f"Error in JavaScript evaluation: {e}")
                
                # Try React Fiber approach
                print("\n=== React Fiber approach ===")
                try:
                    react_data = first_book.evaluate('''(container) => {
                        const keys = Object.keys(container);
                        for (const key of keys) {
                            if (key.startsWith('__reactFiber') || key.startsWith('__reactInternalInstance')) {
                                let fiber = container[key];
                                const found = [];
                                for (let i = 0; i < 20 && fiber; i++) {
                                    if (fiber.memoizedProps) {
                                        const props = fiber.memoizedProps;
                                        if (props.href || props.bookId || props.editionId) {
                                            found.push({
                                                href: props.href,
                                                bookId: props.bookId,
                                                editionId: props.editionId
                                            });
                                        }
                                    }
                                    fiber = fiber.return || fiber._debugOwner;
                                }
                                return found;
                            }
                        }
                        return [];
                    }''')
                    print(f"React data: {react_data}")
                except Exception as e:
                    print(f"Error in React Fiber: {e}")
                
                print("\nPress Enter to continue...")
                input()
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    test_book_url_extraction()

