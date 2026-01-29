import re
import logging
from typing import Dict, Any
from urllib.parse import urlparse

def setup_logger(name: str) -> logging.Logger:
    """Setup standardized logging across all modules"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def clean_text(text: str) -> str:
    """Clean and normalize text for LLM processing"""
    if not text:
        return ""
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def validate_url(url: str) -> bool:
    """Better URL validation with auto-fix"""
    # Clean the URL first
    url = url.strip()
    
    # Add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    
    # Parse and validate
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def normalize_url(url: str) -> str:
    """Normalize URL to proper format"""
    url = url.strip()
    
    # Remove any quotes
    url = url.strip('"\'').strip()
    
    # Add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    
    # Remove www. for consistency
    url = url.replace('http://www.', 'https://')
    url = url.replace('https://www.', 'https://')
    
    return url

if __name__ == "__main__":
    # Driver code for helpers
    print("🔧 Testing Helper Functions:")
    
    # Test URL validation and normalization
    test_urls = [
        "neuralink.com",
        "https://neuralink.com",
        "www.neuralink.com", 
        "http://neuralink.com",
        "invalid-url",
        "https://example.com/path"
    ]
    
    for url in test_urls:
        normalized = normalize_url(url)
        valid = validate_url(normalized)
        print(f"Original: {url}")
        print(f"Normalized: {normalized}")
        print(f"Valid: {valid}")
        print("-" * 40)
    
    # Test text cleaning
    dirty_text = "  Hello    world!  \n\nThis is   messy.  "
    print(f"\nCleaned text: '{clean_text(dirty_text)}'")
    
    # Test logger
    logger = setup_logger("test_logger")
    logger.info("Logger test successful!")