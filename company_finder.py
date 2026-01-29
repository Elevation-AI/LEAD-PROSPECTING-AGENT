"""
Prospect Finder - Finds Companies That Would BUY Your Product
==============================================================
NOT competitors - actual potential customers!
"""

import requests
import time
import sys
import os
from typing import List, Dict, Any
import json
from google import genai
from google.genai import types

# Import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logger
from config.settings import settings


class ProspectFinder:
    """
    Finds PROSPECT COMPANIES (potential customers), NOT competitors.

    Flow:
    1. Takes ICP describing WHO would buy the product
    2. Uses LLM to generate list of companies matching that profile
    3. Validates domains via Google Search
    4. Returns real companies that fit the customer profile
    """

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.api_key = settings.GOOGLE_SEARCH_API_KEY
        self.search_engine_id = settings.GOOGLE_SEARCH_ENGINE_ID
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        # Initialize Gemini LLM with new google.genai library
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # ----------------------------------------------------------------------
    # LAYER 1 - LLM PROSPECT GENERATION
    # ----------------------------------------------------------------------
    def _generate_prospect_companies(self, icp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Use LLM to find PROSPECT companies (companies that would BUY).
        
        CRITICAL: This finds CUSTOMERS, not competitors!
        """
        
        # Extract ICP fields with fallbacks
        what_they_sell = icp_data.get('what_they_sell', icp_data.get('industry', 'Unknown product'))
        customer_industry = icp_data.get('customer_industry', icp_data.get('industry', 'Various industries'))
        customer_size = icp_data.get('customer_company_size', icp_data.get('company_size', 'SMB to Enterprise'))
        target_buyers = icp_data.get('target_buyers', ['Manager', 'Director'])
        pain_points = icp_data.get('pain_points_solved', [])
        customer_traits = icp_data.get('ideal_customer_characteristics', [])

        prompt = f"""
You are a B2B sales research expert finding PROSPECTIVE CUSTOMERS.

CRITICAL INSTRUCTION: Find companies that would BUY this product, NOT competitors.

Product Being Sold: {what_they_sell}
Customer Industry: {customer_industry}
Customer Company Size: {customer_size}
Target Buyer Roles: {', '.join(target_buyers)}
Pain Points Solved: {', '.join(pain_points) if pain_points else 'N/A'}
Ideal Customer Traits: {', '.join(customer_traits) if customer_traits else 'N/A'}

YOUR TASK:
Find 10-15 REAL companies that:
1. Are IN the customer industry (not selling similar products)
2. Match the customer size/profile
3. Would BENEFIT from buying this product
4. Are potential BUYERS (not competitors or vendors)

EXAMPLES TO CLARIFY:

Example 1: If selling "Amazon seller optimization software"
 CORRECT PROSPECTS: Nike, Anker, PopSockets (they sell on Amazon, need tools)
 WRONG: Helium 10, Jungle Scout (they compete, won't buy)

Example 2: If selling "Team collaboration software"
 CORRECT PROSPECTS: Startup tech companies, agencies (they need collaboration)
 WRONG: Slack, Microsoft Teams (they compete, won't buy)

Example 3: If selling "CRM for real estate"
 CORRECT PROSPECTS: RE/MAX offices, Keller Williams franchises (they need CRM)
 WRONG: Salesforce, HubSpot (they compete, won't buy)

RETURN FORMAT:
Return ONLY a valid JSON array. Each object must have:
- name: Company name (string)
- domain: Company domain without www (string or null if unknown)
- fit_score: How well they match (0.0 to 1.0)
- why_prospect: Why they'd buy this product (1 sentence)

Example output:
[
  {{
    "name": "Anker Innovations",
    "domain": "anker.com",
    "fit_score": 0.95,
    "why_prospect": "Major Amazon seller with 1000+ products, needs optimization tools"
  }},
  {{
    "name": "PopSockets LLC",
    "domain": "popsockets.com",
    "fit_score": 0.88,
    "why_prospect": "E-commerce brand with strong Amazon presence, needs analytics"
  }}
]

NO text before or after the JSON array.
Return ONLY valid JSON.
"""

        try:
            self.logger.info(" Using LLM to find PROSPECT companies (potential customers)...")

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Slightly higher for more diverse results
                    max_output_tokens=1500
                )
            )

            raw_text = response.text.strip()

            # Extract JSON from response
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1

            if start == -1 or end == 0:
                self.logger.error(" LLM did not return JSON array")
                return []

            json_str = raw_text[start:end]
            data = json.loads(json_str)

            # Validate and clean results
            cleaned = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                # Required fields
                if "name" not in item:
                    continue
                
                # Add defaults for missing fields
                if "fit_score" not in item:
                    item["fit_score"] = 0.7
                if "why_prospect" not in item:
                    item["why_prospect"] = "Matches customer profile"
                if "domain" not in item:
                    item["domain"] = None

                cleaned.append(item)
            
            self.logger.info(f" LLM generated {len(cleaned)} prospect candidates")
            return cleaned

        except json.JSONDecodeError as e:
            self.logger.error(f" Failed to parse LLM JSON response: {e}")
            self.logger.debug(f"Raw response: {raw_text[:500]}")
            return []
        except Exception as e:
            self.logger.error(f" LLM prospect generation failed: {e}")
            return []

    # ----------------------------------------------------------------------
    # LAYER 2: GOOGLE SEARCH VALIDATION
    # ----------------------------------------------------------------------
    def _validate_domain_via_google(self, company_name: str) -> str:
        """
        Use Google Search to find the official domain for a company.
        """
        query = f"{company_name} official website"
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": 5,
        }

        try:
            resp = requests.get(self.base_url, params=params, timeout=15)
            
            if resp.status_code == 429:
                self.logger.warning(" Google API rate limit hit, waiting...")
                time.sleep(2)
                return self._validate_domain_via_google(company_name)
            
            if resp.status_code != 200:
                self.logger.warning(f" Google search failed with status {resp.status_code}")
                return None

            data = resp.json()

            # Look through search results for valid domain
            for item in data.get("items", []):
                link = item.get("link", "")
                if not link:
                    continue

                domain = self._extract_domain(link)
                if self._is_valid_business_domain(domain):
                    self.logger.debug(f" Found valid domain: {domain}")
                    return domain

        except Exception as e:
            self.logger.error(f" Google validation error for {company_name}: {e}")

        return None

    # ----------------------------------------------------------------------
    # MAIN PUBLIC METHOD
    # ----------------------------------------------------------------------
    def find_prospects(self, icp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main method: Find prospect companies based on ICP.
        
        Args:
            icp_data: Dictionary containing customer profile information
            
        Returns:
            List of prospect companies with validated domains
        """
        self.logger.info(" Starting prospect discovery...")
        self.logger.info(f" Looking for companies in: {icp_data.get('customer_industry', 'various industries')}")
        
        # Step 1: Generate prospects using LLM
        prospect_candidates = self._generate_prospect_companies(icp_data)

        if not prospect_candidates:
            self.logger.warning(" LLM returned no prospects")
            return []

        # Step 2: Validate domains
        validated_prospects = []

        for prospect in prospect_candidates:
            name = prospect["name"]
            self.logger.info(f" Validating domain for: {name}")

            # Use LLM-provided domain or search for it
            domain = prospect.get("domain")
            
            if not domain or domain == "null":
                self.logger.debug(f"No domain provided, searching Google for {name}")
                domain = self._validate_domain_via_google(name)

            if not domain:
                self.logger.warning(f" Could not find valid domain for {name}")
                continue

            if not self._is_valid_business_domain(domain):
                self.logger.debug(f" Domain rejected: {domain}")
                continue

            # Add to validated list
            validated_prospects.append({
                "name": name,
                "domain": domain,
                "confidence": prospect["fit_score"],
                "why_good_fit": prospect["why_prospect"],
                "source": "llm_prospect_finder"
            })

            # Respect rate limits
            time.sleep(0.3)

            # Stop if we have enough
            if len(validated_prospects) >= settings.SEARCH_MAX_RESULTS:
                break

        self.logger.info(f" Found {len(validated_prospects)} validated prospects")
        return validated_prospects

    # ----------------------------------------------------------------------
    # HELPER METHODS
    # ----------------------------------------------------------------------
    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain.lower()
        except:
            return ""

    def _is_valid_business_domain(self, domain: str) -> bool:
        """
        Validate that domain is a real business (not spam, blog, etc.)
        """
        if not domain:
            return False

        # Filter out non-business domains
        bad_keywords = [
            "blog", "news", "review", "comparison", "vs", "directory",
            "medium.com", "wordpress", "blogspot",
            "linkedin.com", "facebook.com", "twitter.com",
            "wikipedia", "reddit", "quora"
        ]

        domain_lower = domain.lower()
        
        if any(bad in domain_lower for bad in bad_keywords):
            return False

        # Must end with common business TLDs
        valid_tlds = (".com", ".io", ".ai", ".co", ".net", ".org")
        if not domain.endswith(valid_tlds):
            return False

        # Domain shouldn't be too long or have weird patterns
        if len(domain) > 50 or domain.count("-") > 2:
            return False

        return True


# ----------------------------------------------------------------------
# TEST DRIVER
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🔧 Testing Prospect Finder (Finds CUSTOMERS, not competitors)")
    print("=" * 70)

    # Test Case 1: Amazon Seller Tools
    test_icp_1 = {
        "what_they_sell": "Amazon seller optimization and analytics software",
        "customer_industry": "E-commerce, Consumer Goods, Retail brands selling on Amazon",
        "customer_company_size": "SMB to Enterprise with Amazon presence",
        "target_buyers": ["Brand Manager", "E-commerce Director", "Amazon Account Manager"],
        "pain_points_solved": [
            "Poor Amazon search visibility",
            "Inefficient keyword research",
            "Lost revenue opportunities"
        ],
        "ideal_customer_characteristics": [
            "Sells products on Amazon",
            "Annual revenue $1M+",
            "Manages 10+ SKUs on Amazon"
        ]
    }

    print("\n Test Case 1: Finding prospects for Amazon seller tools")
    print("Expected: E-commerce brands like Anker, PopSockets, Herschel")
    print("NOT: Helium 10, Jungle Scout (competitors)\n")

    finder = ProspectFinder()
    prospects_1 = finder.find_prospects(test_icp_1)

    print(f"\n Found {len(prospects_1)} prospects:")
    for p in prospects_1[:5]:  # Show first 5
        print(f"  • {p['name']} ({p['domain']})")
        print(f"    Why: {p['why_good_fit']}")
        print(f"    Confidence: {p['confidence']:.0%}\n")

    # Validation check
    competitor_keywords = ['helium', 'jungle', 'viral', 'amzscout', 'sellics']
    found_competitors = [p for p in prospects_1 
                        if any(kw in p['name'].lower() for kw in competitor_keywords)]
    
    if found_competitors:
        print(f" WARNING: Found {len(found_competitors)} competitors in results (should be 0):")
        for c in found_competitors:
            print(f"   {c['name']} - This is a competitor, not a prospect!")
    else:
        print(" VALIDATION PASSED: No competitors found (all are prospects)")

    print("\n" + "="*70)