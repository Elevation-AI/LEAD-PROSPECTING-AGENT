"""
Tech Stack Detector using Firecrawl + LLM
==========================================
Intelligent technology detection using AI analysis
"""

import sys
import os
from typing import Dict, List, Optional
import json
import time
from firecrawl import FirecrawlApp
from google import genai
from google.genai import types

# Get the directory where main.py is located (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (lead-prospecting-agent)
project_root = os.path.dirname(current_dir)

# Add the project root to sys.path so 'src' can be found
if project_root not in sys.path:
    sys.path.insert(0, project_root)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logger
from config.settings import settings


class TechStackDetector:
    """
    Detect technologies used by a website using Firecrawl + LLM analysis

    Approach:
    1. Firecrawl scrapes the website
    2. Extract key technical indicators
    3. LLM analyzes and identifies technologies
    4. Return structured tech stack
    """

    def __init__(self):
        self.logger = setup_logger(__name__)

        # Initialize Firecrawl
        if not settings.FIRECRAWL_API_KEY:
            raise ValueError(" FIRECRAWL_API_KEY missing in .env")
        self.firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)

        # Initialize Gemini LLM with new google.genai library
        if not settings.GEMINI_API_KEY:
            raise ValueError(" GEMINI_API_KEY missing in .env")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    def _scrape_website(self, url: str) -> Optional[Dict]:
        """
        Scrape website using Firecrawl Python SDK
        (Fix: handle Document object correctly)
        """
        try:
            self.logger.info(f" Scraping {url} with Firecrawl...")

            doc = self.firecrawl.scrape(
                url=url,
                formats=["html", "markdown"],
                only_main_content=False
            )

            # Firecrawl SDK returns a Document object
            if not doc or not getattr(doc, "html", None):
                self.logger.error(f" Firecrawl returned no HTML for {url}")
                return None

            self.logger.info(f" Scraped {len(doc.html)} chars")

            # Normalize Document → dict (so rest of your code stays unchanged)
            return {
                "html": doc.html,
                "markdown": getattr(doc, "markdown", ""),
                "metadata": getattr(doc, "metadata", {}),
            }

        except Exception as e:
            self.logger.error(f" Firecrawl error for {url}: {e}")
            return None


    
    def _extract_tech_indicators(self, scraped_data: Dict) -> str:
        """
        Extract key technical indicators from scraped data
        
        This reduces token usage by only sending relevant parts to LLM
        """
        html = scraped_data.get('html', '')
        
        indicators = []
        
        # Extract script tags (first 15)
        import re
        scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)[:15]
        if scripts:
            indicators.append(f"Script Sources: {', '.join(scripts)}")
        
        # Extract meta tags
        meta_tags = re.findall(r'<meta[^>]*name=["\']([^"\']+)["\'][^>]*content=["\']([^"\']+)["\']', html)[:10]
        if meta_tags:
            indicators.append(f"Meta Tags: {dict(meta_tags)}")
        
        # Extract inline script snippets (look for common patterns)
        analytics_patterns = [
            'google-analytics', 'gtag', 'ga(', 'dataLayer',
            'segment', 'mixpanel', 'amplitude', 'heap'
        ]
        found_analytics = [p for p in analytics_patterns if p in html.lower()]
        if found_analytics:
            indicators.append(f"Analytics Found: {', '.join(found_analytics)}")
        
        # Framework indicators
        framework_patterns = [
            'react', 'vue', 'angular', 'next.js', 'nuxt',
            'gatsby', 'svelte', 'ember'
        ]
        found_frameworks = [f for f in framework_patterns if f in html.lower()]
        if found_frameworks:
            indicators.append(f"Framework Indicators: {', '.join(found_frameworks)}")
        
        # CMS indicators
        cms_patterns = [
            'wp-content', 'wordpress', 'drupal', 'joomla',
            'shopify', 'wix', 'squarespace', 'webflow'
        ]
        found_cms = [c for c in cms_patterns if c in html.lower()]
        if found_cms:
            indicators.append(f"CMS Indicators: {', '.join(found_cms)}")
        
        # CDN/Hosting patterns
        hosting_patterns = [
            'cloudflare', 'fastly', 'akamai', 'amazonaws',
            'vercel', 'netlify', 'heroku'
        ]
        found_hosting = [h for h in hosting_patterns if h in html.lower()]
        if found_hosting:
            indicators.append(f"Hosting/CDN: {', '.join(found_hosting)}")
        
        # Payment/CRM integrations
        integration_patterns = [
            'stripe', 'paypal', 'salesforce', 'hubspot',
            'intercom', 'zendesk', 'auth0'
        ]
        found_integrations = [i for i in integration_patterns if i in html.lower()]
        if found_integrations:
            indicators.append(f"Integrations: {', '.join(found_integrations)}")
        
        # Sample of HTML structure (first 2000 chars)
        html_sample = html[:2000]
        indicators.append(f"\nHTML Sample:\n{html_sample}")
        
        return "\n".join(indicators)
    
    def _analyze_with_llm(self, tech_indicators: str, domain: str) -> Optional[Dict]:
        """
        Use LLM to analyze technical indicators and detect technologies
        
        Args:
            tech_indicators: Extracted technical signals
            domain: Company domain
            
        Returns:
            Structured tech stack dictionary
        """
        prompt = f"""You are a technology detection expert. Analyze the following technical indicators from {domain} and identify ALL technologies used.

TECHNICAL INDICATORS:
{tech_indicators}

YOUR TASK:
Detect and categorize ALL technologies with HIGH CONFIDENCE based on EVIDENCE in the indicators.

CRITICAL RULES:
1. ONLY include technologies you have EVIDENCE for
2. DO NOT guess or hallucinate
3. If uncertain, mark confidence as "low" or omit
4. Be specific (e.g., "Next.js" not just "React")
5. Infer relationships (e.g., Next.js implies React and Node.js)

RETURN FORMAT (JSON only, no other text):
{{
  "frontend_framework": "string or null",
  "backend_technology": "string or null",
  "programming_languages": ["string"],
  "hosting_provider": "string or null",
  "cdn": "string or null",
  "analytics_tools": ["string"],
  "crm_tools": ["string"],
  "payment_processing": ["string"],
  "other_integrations": ["string"],
  "cms": "string or null",
  "confidence": "high/medium/low",
  "reasoning": "Brief explanation of key detections"
}}

EXAMPLES:
- If you see "next/router" → frontend_framework: "Next.js", backend: "Node.js"
- If you see "wp-content" → cms: "WordPress", backend: "PHP"
- If you see "gtag" → analytics_tools: ["Google Analytics"]
- If you see "stripe.js" → payment_processing: ["Stripe"]

Return ONLY the JSON object, no additional text.
"""

        try:
            self.logger.info(" Analyzing with LLM...")

            # Combine system instruction with prompt for Gemini
            full_prompt = "You are a technology detection expert. Return only valid JSON.\n\n" + prompt

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=1000
                )
            )

            # Extract JSON from response
            llm_output = response.text.strip()
            
            # Remove markdown code blocks if present
            if llm_output.startswith('```'):
                llm_output = llm_output.split('```')[1]
                if llm_output.startswith('json'):
                    llm_output = llm_output[4:]
            
            # Parse JSON
            tech_stack = json.loads(llm_output)
            
            self.logger.info(f" LLM detected {len([v for v in tech_stack.values() if v])} tech categories")
            
            return tech_stack
            
        except json.JSONDecodeError as e:
            self.logger.error(f" Failed to parse LLM JSON: {e}")
            self.logger.debug(f"LLM output: {llm_output[:500]}")
            return None
        except Exception as e:
            self.logger.error(f" LLM analysis error: {e}")
            return None
    
    def _format_tech_stack(self, raw_tech_stack: Dict, domain: str) -> Dict:
        """
        Format tech stack into clean output for Agent 02
        
        Args:
            raw_tech_stack: Raw LLM output
            domain: Company domain
            
        Returns:
            Clean, formatted tech stack
        """
        # Create simple list of all technologies
        tech_list = []
        
        # Add all non-null, non-empty values
        for key, value in raw_tech_stack.items():
            if key in ['confidence', 'reasoning']:
                continue
            
            if isinstance(value, list):
                tech_list.extend(value)
            elif value and value != "null":
                tech_list.append(value)
        
        # Remove duplicates while preserving order
        tech_list = list(dict.fromkeys(tech_list))
        
        return {
            "domain": domain,
            "tech_stack": tech_list,
            "categories": {
                "frontend": raw_tech_stack.get("frontend_framework"),
                "backend": raw_tech_stack.get("backend_technology"),
                "hosting": raw_tech_stack.get("hosting_provider"),
                "analytics": raw_tech_stack.get("analytics_tools", []),
                "crm": raw_tech_stack.get("crm_tools", []),
                "cms": raw_tech_stack.get("cms")
            },
            "confidence": raw_tech_stack.get("confidence", "medium"),
            "detection_method": "firecrawl_llm",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def detect(self, url: str) -> Optional[Dict]:
        """
        Main method: Detect tech stack for a website
        
        Args:
            url: Full website URL (e.g., "https://greenhouse.io")
            
        Returns:
            Dictionary with tech stack or None if failed
        """
        # Normalize URL to get domain
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace('www.', '')
        
        self.logger.info(f" Detecting tech stack for {domain}")
        
        # Step 1: Scrape website
        scraped_data = self._scrape_website(url)
        if not scraped_data:
            return None
        
        # Step 2: Extract technical indicators
        tech_indicators = self._extract_tech_indicators(scraped_data)
        
        # Step 3: Analyze with LLM
        raw_tech_stack = self._analyze_with_llm(tech_indicators, domain)
        if not raw_tech_stack:
            return None
        
        # Step 4: Format output
        formatted = self._format_tech_stack(raw_tech_stack, domain)
        
        self.logger.info(f" Detected {len(formatted['tech_stack'])} technologies for {domain}")
        
        return formatted
    
    def detect_batch(self, urls: List[str]) -> List[Dict]:
        """
        Detect tech stack for multiple websites
        
        Args:
            urls: List of website URLs
            
        Returns:
            List of tech stack dictionaries
        """
        results = []
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f" Processing {i}/{len(urls)}: {url}")
            
            tech_stack = self.detect(url)
            
            if tech_stack:
                results.append(tech_stack)
            else:
                self.logger.warning(f" Failed to detect tech for {url}")
            
            # Rate limiting (respect API limits)
            if i < len(urls):
                self.logger.debug(" Waiting 2 seconds...")
                time.sleep(2)
        
        self.logger.info(f" Detected tech for {len(results)}/{len(urls)} websites")
        return results


# --------------------------------------------------------
# TEST DRIVER
# --------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔧 Tech Stack Detector (Firecrawl + LLM)")
    print("="*70)
    
    detector = TechStackDetector()
    
    # Test URLs
    test_urls = [
        #"https://greenhouse.io",
        #"https://www.shopify.com",
        #"https://stripe.com"
        "https://www.openai.com",
        "https://www.zomato.com"
    ]
    
    for url in test_urls:
        print(f"\n Testing: {url}")
        print("-" * 70)
        
        result = detector.detect(url)
        
        if result:
            print("\n SUCCESS\n")
            print(f"Domain: {result['domain']}")
            print(f"Confidence: {result['confidence']}")
            print(f"\n Tech Stack ({len(result['tech_stack'])} technologies):")
            for tech in result['tech_stack']:
                print(f"  • {tech}")
            
            print(f"\n Categories:")
            for category, value in result['categories'].items():
                if value:
                    print(f"  {category}: {value}")
        else:
            print("\n FAILED")
        
        print("\n" + "="*70)