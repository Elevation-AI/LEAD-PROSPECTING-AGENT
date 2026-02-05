"""
JavaScript-enabled scraper with multiple fallback options
"""

import sys
import os
from typing import Optional
import time
import requests
from bs4 import BeautifulSoup

# Fix import path - add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.helpers import setup_logger, clean_text

class JavaScriptScraper:
    """
    Scraper for JavaScript-heavy websites with multiple approaches
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape_with_multiple_methods(self, url: str) -> Optional[str]:
        """
        Try multiple methods to scrape JavaScript sites
        Returns the best result
        """
        methods = [
            self._try_selenium,  # Try Selenium first (more reliable)
            self._try_requests_html,
            self._try_cloudscraper,
            self._try_simple_request  # Last resort
        ]
        
        for method in methods:
            self.logger.debug(f" Trying method: {method.__name__}")
            result = method(url)
            if result and len(result) > 500:
                self.logger.info(f" {method.__name__} successful: {len(result)} chars")
                return result
        
        return None
    
    def _try_requests_html(self, url: str) -> Optional[str]:
        """Try requests-html with local Chromium"""
        try:
            from requests_html import HTMLSession
            
            session = HTMLSession()
            response = session.get(url, timeout=30)
            
            # Try to render with JavaScript
            try:
                response.html.render(timeout=30, sleep=2)
                html_content = response.html.html
            except Exception as render_error:
                self.logger.debug(f"requests-html render failed: {render_error}")
                # Use initial HTML if render fails
                html_content = response.html.html
            
            session.close()
            
            # Parse and clean
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            return clean_text(text)
            
        except Exception as e:
            self.logger.debug(f"requests-html failed: {str(e)[:100]}")
            return None
    
    def _try_selenium(self, url: str) -> Optional[str]:
        """Try Selenium WebDriver with automatic driver management"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            try:
                # Selenium 4.6+ has built-in driver management
                driver = webdriver.Chrome(options=options)
            except Exception as chrome_error:
                self.logger.debug(f"Chrome driver error: {chrome_error}")
                return None
            
            try:
                driver.get(url)
                
                # Wait for page to load
                time.sleep(3)
                
                # Get page source
                html_content = driver.page_source
                
                # Parse and clean
                soup = BeautifulSoup(html_content, 'html.parser')
                for script in soup(["script", "style", "noscript"]):
                    script.decompose()
                
                text = soup.get_text(separator=' ', strip=True)
                cleaned_text = clean_text(text)
                
                return cleaned_text
                
            finally:
                driver.quit()
            
        except Exception as e:
            self.logger.debug(f"Selenium failed: {str(e)[:100]}")
            return None
    
    def _try_cloudscraper(self, url: str) -> Optional[str]:
        """Try cloudscraper for Cloudflare-protected sites"""
        try:
            import cloudscraper
            
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            
            response = scraper.get(url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            return clean_text(text)
            
        except ImportError:
            self.logger.debug("cloudscraper not installed")
            return None
        except Exception as e:
            self.logger.debug(f"cloudscraper failed: {str(e)[:100]}")
            return None
    
    def _try_simple_request(self, url: str) -> Optional[str]:
        """Simple request as last resort"""
        try:
            response = self.session.get(url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to extract JSON-LD
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                import json
                try:
                    data = json.loads(json_ld.string)
                    if isinstance(data, dict):
                        text = ' '.join(str(v) for v in data.values() if v)
                        if len(text) > 100:
                            return clean_text(text)
                except:
                    pass
            
            # Extract meta tags
            meta_content = []
            for meta in soup.find_all('meta'):
                name = meta.get('name', '') or meta.get('property', '')
                content = meta.get('content', '')
                if content and len(content) > 20:
                    meta_content.append(f"{name}: {content}")
            
            # Get title
            title = soup.find('title')
            if title:
                meta_content.append(f"Title: {title.get_text()}")
            
            if meta_content:
                return clean_text(' '.join(meta_content))
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Simple request failed: {str(e)[:100]}")
            return None
    
    def scrape_javascript_sync(self, url: str) -> Optional[str]:
        """Main method to scrape JavaScript sites"""
        self.logger.info(f" Attempting to scrape JavaScript site: {url}")
        
        result = self.scrape_with_multiple_methods(url)
        
        if result:
            self.logger.info(f" JavaScript scraping successful: {len(result)} chars")
            return result
        else:
            self.logger.warning("  All JavaScript scraping methods failed")
            return None

if __name__ == "__main__":
    """Test JavaScript scraper"""
    # Set console encoding for Windows
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("Testing JavaScript Scraper")
    print("=" * 60)

    scraper = JavaScriptScraper()

    # Test URLs
    test_urls = ["https://neuralink.com"]

    for url in test_urls:
        print(f"\nTesting: {url}")
        print("-" * 40)

        result = scraper.scrape_javascript_sync(url)

        if result:
            print(f"Success! Got {len(result)} characters")
            preview = result[:500] + "..." if len(result) > 500 else result
            print(f"Preview:\n{preview}")
        else:
            print("Failed to scrape")