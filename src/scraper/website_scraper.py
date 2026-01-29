"""Extract comprehensive business information from any company website"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from typing import Dict, List, Optional
import sys
import os
import chardet

# Fix import path - add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.helpers import setup_logger, clean_text, normalize_url
from config.settings import settings
from src.scraper.javascript_scraper import JavaScriptScraper

class WebsiteScraper:
    """
    Professional website scraper with JavaScript fallback
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.js_scraper = JavaScriptScraper()  # Initialize JavaScript scraper
    
    def scrape_website(self, url: str) -> Dict[str, str]:
        """
        Main method to scrape website with JavaScript fallback
        """
        # Normalize URL first
        url = normalize_url(url)
        self.logger.info(f" Starting scrape for: {url}")
        
        # Check if it's likely a JavaScript site
        is_js_site = self.detect_javascript_site(url)
        
        if is_js_site:
            self.logger.info(" Detected JavaScript-heavy site, using JavaScript scraper")
            js_content = self.js_scraper.scrape_javascript_sync(url)
            
            if js_content and len(js_content) > 500:
                return {
                    'homepage': js_content,
                    'about_page': '',
                    'combined_text': clean_text(js_content),
                    'method': 'javascript',
                    'content_length': len(js_content),
                    'is_javascript_site': True
                }
        
        try:
            # Step 1: Try regular scraping first
            homepage_content = self._scrape_page(url)
            about_content = self._find_and_scrape_about_page(url)
            combined = f"{homepage_content} {about_content}"
            
            # Step 2: Check if we got meaningful content
            if len(combined) < 500:  # Threshold for insufficient content
                self.logger.warning(f"  Low content ({len(combined)} chars). Trying JavaScript fallback...")
                
                # Try JavaScript scraping
                js_content = self.js_scraper.scrape_javascript_sync(url)
                if js_content and len(js_content) > 500:
                    self.logger.info(f" JavaScript scraping successful: {len(js_content)} chars")
                    
                    return {
                        'homepage': js_content,
                        'about_page': '',
                        'combined_text': clean_text(js_content),
                        'method': 'javascript_fallback',
                        'content_length': len(js_content),
                        'is_javascript_site': True
                    }
            
            # Return regular scraping results
            return {
                'homepage': homepage_content,
                'about_page': about_content,
                'combined_text': clean_text(combined),
                'method': 'regular',
                'content_length': len(combined),
                'is_javascript_site': is_js_site
            }
            
        except Exception as e:
            self.logger.error(f" Scraping failed for {url}: {str(e)}")
            
            # Last resort: Try JavaScript
            try:
                self.logger.info(" Trying JavaScript as last resort...")
                js_content = self.js_scraper.scrape_javascript_sync(url)
                if js_content:
                    return {
                        'homepage': js_content,
                        'about_page': '',
                        'combined_text': clean_text(js_content),
                        'method': 'javascript_emergency',
                        'content_length': len(js_content),
                        'is_javascript_site': True
                    }
            except:
                pass
            
            return {
                'homepage': '', 
                'about_page': '', 
                'combined_text': '', 
                'method': 'failed',
                'content_length': 0,
                'is_javascript_site': False
            }
    
    def _scrape_page(self, url: str) -> str:
        """Scrape individual page content with encoding handling"""
        try:
            response = self.session.get(url, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Detect encoding
            encoding = self._detect_encoding(response)
            response.encoding = encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text from important sections
            text_parts = []
            
            # Get title
            title = soup.find('title')
            if title:
                text_parts.append(f"Page Title: {title.get_text()}")
            
            # Get meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                text_parts.append(f"Meta Description: {meta_desc.get('content', '')}")
            
            # Get main content from common content containers
            content_selectors = [
                'main', 'article', '.content', '#content', 
                '.main-content', '[role="main"]', 'section',
                'h1', 'h2', 'p', 'div[class*="content"]', 'div[class*="text"]'
            ]
            
            for selector in content_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(separator=' ', strip=True)
                    if len(text) > 50:  # Only add substantial content
                        text_parts.append(text)
            
            # If no substantial content found, get body text
            if not any(len(part) > 100 for part in text_parts):
                body = soup.find('body')
                if body:
                    text_parts.append(body.get_text(separator=' ', strip=True))
            
            return clean_text(' '.join(text_parts))
            
        except Exception as e:
            self.logger.error(f"Failed to scrape {url}: {str(e)}")
            return ""
    
    def _detect_encoding(self, response) -> str:
        """Detect proper encoding for the response"""
        # Try from response headers
        if response.encoding:
            return response.encoding
        
        # Try to detect from content
        try:
            detected = chardet.detect(response.content)
            if detected['encoding']:
                return detected['encoding']
        except:
            pass
        
        # Fallback encodings
        fallback_encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'windows-1252']
        
        for encoding in fallback_encodings:
            try:
                response.content.decode(encoding)
                return encoding
            except:
                continue
        
        # Default to utf-8 with error replacement
        return 'utf-8'
    
    def _find_about_page_url(self, base_url: str) -> Optional[str]:
        """Find About page URL without scraping it"""
        about_patterns = [
            '/about', '/about-us', '/about/', '/company',
            '/our-story', '/team', '/who-we-are', '/about/company',
            '/about-us/', '/company/about', '/about/team', '/team/about'
        ]
        
        for pattern in about_patterns:
            about_url = urljoin(base_url, pattern)
            try:
                # Just check if page exists (HEAD request)
                response = self.session.head(about_url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    return about_url
            except:
                continue
        
        return None
    
    def _find_and_scrape_about_page(self, base_url: str) -> str:
        """Find and scrape About page"""
        about_url = self._find_about_page_url(base_url)
        if about_url:
            self.logger.info(f" Found About page: {about_url}")
            return self._scrape_page(about_url)
        
        self.logger.info(" No About page found")
        return ""
    
    def detect_javascript_site(self, url: str) -> bool:
        """Better detection of JavaScript-heavy sites"""
        try:
            response = self.session.get(url, timeout=10)
            
            # Remove www. for consistency in checking
            cleaned_url = url.replace('https://www.', 'https://').replace('http://www.', 'http://')
            
            # Known JavaScript-heavy domains
            known_js_domains = [
                'neuralink.com',
                'reactjs.org',
                'vuejs.org',
                'angular.io',
                'svelte.dev',
                'nextjs.org',
                'shopify.com',
                'vercel.com',
                'netlify.com'
            ]
            
            # Check if domain is in known list
            domain = cleaned_url.split('//')[-1].split('/')[0]
            if domain in known_js_domains:
                return True
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts from soup copy for text analysis
            soup_copy = BeautifulSoup(response.text, 'html.parser')
            for script in soup_copy(["script", "style", "noscript", "meta"]):
                script.decompose()
            
            # Get text without scripts
            clean_text = soup_copy.get_text(separator=' ', strip=True)
            
            # Get all scripts
            scripts = soup.find_all('script')
            
            # Rule 1: Very little text but many scripts
            if len(clean_text) < 500 and len(scripts) > 5:
                self.logger.debug(f"JS Detection: Little text ({len(clean_text)} chars) but many scripts ({len(scripts)})")
                return True
            
            # Rule 2: Common SPA indicators in HTML
            html_lower = response.text.lower()
            spa_indicators = [
                '<div id="root"',
                '<div id="app"',
                '<div id="__next"',
                'react-app',
                'vue-app',
                'ng-app',
                'data-reactroot',
                '__nextjs',
                'nextjs-warmup'
            ]
            
            for indicator in spa_indicators:
                if indicator in html_lower:
                    self.logger.debug(f"JS Detection: Found SPA indicator: {indicator}")
                    return True
            
            # Rule 3: Mostly script tags
            total_tags = len(soup.find_all())
            if total_tags > 0 and len(scripts) > total_tags * 0.3:  # 30%+ are scripts
                self.logger.debug(f"JS Detection: High script ratio ({len(scripts)}/{total_tags} = {len(scripts)/total_tags:.1%})")
                return True
            
            # Rule 4: Common JavaScript framework patterns in script sources
            script_sources = ' '.join([script.get('src', '') for script in scripts])
            script_sources_lower = script_sources.lower()
            framework_patterns = [
                '.jsx', '.tsx', 'chunk', 'bundle', 'webpack',
                'react', 'vue', 'angular', 'svelte', 'next',
                'runtime', 'framework', '_app', '_document'
            ]
            
            for pattern in framework_patterns:
                if pattern in script_sources_lower:
                    self.logger.debug(f"JS Detection: Found framework pattern: {pattern}")
                    return True
            
            # Rule 5: Check for specific meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name', '').lower()
                content = meta.get('content', '').lower()
                if 'generator' in name and any(fw in content for fw in ['next', 'gatsby', 'nuxt', 'react']):
                    self.logger.debug(f"JS Detection: Found generator: {content}")
                    return True
            
            self.logger.debug(f"JS Detection: Not a JavaScript site (text: {len(clean_text)} chars, scripts: {len(scripts)})")
            return False
            
        except Exception as e:
            self.logger.debug(f"JS Detection failed: {str(e)}")
            # If detection fails, assume it might need JavaScript (safer)
            return True
    
    def quick_test(self, url: str) -> Dict[str, any]:
        """Quick test with detailed diagnostics"""
        url = normalize_url(url)
        
        print(f"\n Quick Test: {url}")
        print("-" * 40)
        
        # Detect
        is_js = self.detect_javascript_site(url)
        print(f"JavaScript Detection: {' Yes' if is_js else ' No'}")
        
        # Scrape
        result = self.scrape_website(url)
        
        print(f"Method Used: {result.get('method', 'unknown')}")
        print(f"Content Length: {result.get('content_length', 0):,} chars")
        
        if result['combined_text']:
            preview = result['combined_text'][:200] + "..." if len(result['combined_text']) > 200 else result['combined_text']
            print(f"Preview: {preview}")
        
        return result

if __name__ == "__main__":
    # Set console encoding for Windows
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("Testing Enhanced Website Scraper")
    print("=" * 60)

    scraper = WebsiteScraper()

    # Mix of traditional and JavaScript sites
    test_urls = [
        "https://neuralink.com",
        "https://www.shopify.com",
        "https://www.hubspot.com",
        "https://kpit.com"
    ]

    for url in test_urls:
        print(f"\nTesting: {url}")
        print("-" * 40)

        result = scraper.quick_test(url)

        print("-" * 40)