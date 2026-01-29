import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Central configuration management for the entire application"""

    # LLM Settings - Gemini (Primary)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

    # LLM Settings - Groq (Legacy)
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
    
    # Search Settings
    SEARCH_API = os.getenv('SEARCH_API', 'duckduckgo')
    SEARCH_MAX_RESULTS = int(os.getenv('SEARCH_MAX_RESULTS', 50))

    # Add to settings.py
    PHANTOMBUSTER_API_KEY = os.getenv('PHANTOMBUSTER_API_KEY')
    PHANTOMBUSTER_PHANTOM_ID = os.getenv('PHANTOMBUSTER_PHANTOM_ID')
    LINKEDIN_SESSION_COOKIE = os.getenv('LINKEDIN_SESSION_COOKIE')

    # Add to settings.py
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

    # Add this line
    # GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
    GOOGLE_OAUTH_CREDENTIALS_PATH = os.getenv('GOOGLE_OAUTH_CREDENTIALS_PATH')
    GOOGLE_OAUTH_TOKEN_PATH = os.getenv('GOOGLE_OAUTH_TOKEN_PATH')

    
    # 🆕 ADD THESE GOOGLE SETTINGS:
    GOOGLE_SEARCH_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY')
    GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
    
    # Apollo Settings
    APOLLO_API_KEY = os.getenv('APOLLO_API_KEY')
    
    # Application Settings
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 30))
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', 5))

# Global settings instance
settings = Settings()

if __name__ == "__main__":
    # Driver code to verify settings are loading correctly
    print(" Testing Settings Configuration:")
    print(f"Gemini Model: {settings.GEMINI_MODEL}")
    print(f"Gemini API Key: {settings.GEMINI_API_KEY[:20]}...")
    print(f"Search API: {settings.SEARCH_API}")
    print(f"Max Results: {settings.SEARCH_MAX_RESULTS}")
    print(" Settings loaded successfully!")