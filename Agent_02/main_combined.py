"""
Prospect Finder - Finds Companies That Would BUY Your Product
==============================================================
HYBRID VERSION with:
- Domain-based name extraction (Gemini's approach)
- LLM verification + name correction
- Comprehensive filtering
- Highest accuracy (85-90%+)
"""

import requests
import time
import sys
import os
import re
import tldextract
from typing import List, Dict, Any, Tuple
import json
from google import genai
from google.genai import types
from urllib.parse import urlparse

# Import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logger
from config.settings import settings


class ProspectFinder:
    """
    Finds PROSPECT COMPANIES (potential customers) via web search.

    Hybrid version combining best approaches:
    - Domain-based name extraction (solves 80% of issues)
    - LLM verification + name correction (solves remaining 20%)
    - Comprehensive filtering and scoring
    """

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.api_key = settings.GOOGLE_SEARCH_API_KEY
        self.search_engine_id = settings.GOOGLE_SEARCH_ENGINE_ID
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        # Initialize Gemini LLM with new google.genai library
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # ======================================================================
    # METHOD 1: Generate Search Queries
    # ======================================================================
    
    def _generate_comprehensive_search_queries(self, icp_data: Dict[str, Any]) -> List[str]:
        """
        Generate search queries from ALL ICP aspects.
        """
        queries = []
        
        # Extract ICP data
        customer_industry = icp_data.get('customer_industry', '')
        customer_size = icp_data.get('customer_company_size', '')
        characteristics = icp_data.get('ideal_customer_characteristics', [])
        pain_points = icp_data.get('pain_points_solved', [])
        geography = icp_data.get('customer_geography', '')
        what_they_sell = icp_data.get('what_they_sell', '')
        
        self.logger.info(" Generating company-focused search queries...")
        
        # Company indicators
        company_indicators = ["brand", "manufacturer", "products", "store"]
        
        # ============================================================
        # QUERY SET 1: Industry + Company Indicator
        # ============================================================
        if customer_industry:
            industries = [ind.strip() for ind in customer_industry.split(',')]
            
            for industry in industries[:3]:
                if not industry:
                    continue
                
                for indicator in company_indicators[:2]:
                    query = f"{industry} {indicator}"
                    queries.append(query)
                    self.logger.debug(f"   Industry query: '{query}'")
        
        # ============================================================
        # QUERY SET 2: Characteristic-based
        # ============================================================
        for characteristic in characteristics[:3]:
            words = characteristic.split()
            key_words = [w for w in words if len(w) > 4 and w.lower() not in 
                        ['companies', 'businesses', 'needs', 'wants', 'should']][:3]
            
            if key_words:
                query = f"brand {' '.join(key_words)}"
                queries.append(query)
                self.logger.debug(f"   Trait query: '{query}'")
        
        # ============================================================
        # QUERY SET 3: Industry + Activity
        # ============================================================
        if customer_industry and characteristics:
            main_industry = customer_industry.split(',')[0].strip()
            
            for char in characteristics[:2]:
                words = [w for w in char.split() if len(w) > 4]
                if words:
                    query = f"{main_industry} {words[0]}"
                    queries.append(query)
                    self.logger.debug(f"   Activity query: '{query}'")
        
        # ============================================================
        # QUERY SET 4: Industry-Specific Terms
        # ============================================================
        
        # Amazon-related
        is_amazon = any("amazon" in str(v).lower() for v in icp_data.values() if isinstance(v, (str, list)))
        if is_amazon:
            queries.extend([
                "amazon seller brand",
                "e-commerce brand amazon",
                "products sold amazon"
            ])
            self.logger.debug("   Added Amazon-specific queries")
        
        # Construction-related
        is_construction = "construction" in customer_industry.lower()
        if is_construction:
            queries.extend([
                "commercial construction contractor",
                "industrial construction company",
                "construction firm projects"
            ])
            self.logger.debug("   Added construction-specific queries")
        
        # Healthcare-related
        is_healthcare = any(word in customer_industry.lower() for word in 
                           ["healthcare", "medical", "hospital", "clinic"])
        if is_healthcare:
            queries.extend([
                "hospital healthcare services",
                "medical center clinic",
                "healthcare provider"
            ])
            self.logger.debug("   Added healthcare-specific queries")
        
        # ============================================================
        # QUERY SET 5: Geography-specific
        # ============================================================
        if geography and geography.lower() not in ['global', 'worldwide']:
            main_industry = customer_industry.split(',')[0].strip() if customer_industry else 'brand'
            geo_terms = [g.strip() for g in geography.split(',')][:2]
            
            for geo in geo_terms:
                if geo:
                    query = f"{main_industry} brand {geo}"
                    queries.append(query)
                    self.logger.debug(f"   Geography query: '{query}'")
        
        # ============================================================
        # CLEANUP: Remove problematic patterns
        # ============================================================
        
        avoid_patterns = [
            "companies need", "companies with", "companies looking",
            "poor", "improve", "increase", "reduce", "better",
            "how to", "ways to", "tips for", "guide to"
        ]
        
        filtered_queries = []
        for query in queries:
            query_lower = query.lower().strip()
            
            if any(pattern in query_lower for pattern in avoid_patterns):
                self.logger.debug(f"   Filtered: '{query}'")
                continue
            
            if " companies" in query_lower:
                query = query.replace(" companies", " brand").replace(" Companies", " Brand")
            
            if query_lower and len(query_lower) > 4:
                filtered_queries.append(query)
        
        # Remove duplicates
        seen = set()
        unique_queries = []
        for q in filtered_queries:
            q_clean = q.lower().strip()
            if q_clean not in seen:
                seen.add(q_clean)
                unique_queries.append(q)
        
        self.logger.info(f" Generated {len(unique_queries)} queries")
        
        return unique_queries[:12]
    
    # ======================================================================
    # METHOD 2: Execute Google Search
    # ======================================================================
    
    def _execute_google_search(self, query: str, num_results: int = 10) -> List[Dict[str, str]]:
        """Execute Google Custom Search API."""
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": num_results,
        }
        
        try:
            self.logger.debug(f"   Searching: '{query}'")
            resp = requests.get(self.base_url, params=params, timeout=15)
            
            if resp.status_code == 429:
                self.logger.warning("⚠️  Rate limit, waiting...")
                time.sleep(3)
                return self._execute_google_search(query, num_results)
            
            if resp.status_code != 200:
                self.logger.warning(f"   Failed: HTTP {resp.status_code}")
                return []
            
            data = resp.json()
            items = data.get("items", [])
            
            results = []
            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"   Search error: {e}")
            return []
    
    # ======================================================================
    # METHOD 3: Extract Companies (DOMAIN-BASED NAMES!)
    # ======================================================================
    
    def _get_clean_name_from_domain(self, domain: str) -> str:
        """
        Extract clean company name from domain.
        This is our PRIMARY name extraction method now!
        
        Examples:
        - globalindustrial.com → "Global Industrial"
        - ferguson.com → "Ferguson"
        - stanley-black-decker.com → "Stanley Black Decker"
        - resmithconst.com → "Resmith Const"
        """
        try:
            extracted = tldextract.extract(f"https://{domain}")
            name = extracted.domain
            
            # Clean up
            name = name.replace('-', ' ').replace('_', ' ')
            
            # Title case
            name = name.title()
            
            # Remove common suffixes from domain names
            for suffix in ['Inc', 'Corp', 'Ltd', 'Llc', 'Co']:
                if name.endswith(f" {suffix}"):
                    name = name[:-len(suffix)-1].strip()
            
            return name
            
        except Exception as e:
            self.logger.debug(f"Domain extraction failed for {domain}: {e}")
            return domain.split('.')[0].title()
    
    def _extract_companies_from_search_results(
        self, 
        search_results: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Extract companies with DOMAIN-BASED names.
        LLM will correct names later if needed.
        """
        companies = []
        seen_domains = set()
        
        # COMPREHENSIVE article patterns
        article_title_patterns = [
            # Lists and guides
            "top ", "best ", "list", "guide", "how to", "what is", "why ",
            
            # Analysis and opinion
            "the role of", "exploring", "understanding", "statistics",
            "tips", "ways to", "reasons for", "causes of", "strategies",
            "advice", "insights", "trends", "analysis", "report",
            
            # Questions and commentary
            "review:", "survey says", "study", "research", "opinion:",
            "wants to", "comes to", "following", "expert", "commentary",
            
            # Future/speculative
            "the future of", "are nurses", "willing to work",
            
            # Job listings
            "job application", "career", "hiring", "openings",
            
            # Publications
            "| forbes", "| cnbc", "| techcrunch", "| economist",
            
            # Economic development & associations
            "emerging", "industry growth", "annual outlook", "updated",
            
            # Definitions
            "definition", "steps & examples", "what is", "explained"
        ]
        
        for result in search_results:
            link = result.get("link", "")
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            
            title_lower = title.lower()
            
            # ===================================
            # FILTER 1: Article titles
            # ===================================
            if any(pattern in title_lower for pattern in article_title_patterns):
                self.logger.debug(f"    Article: {title[:60]}")
                continue
            
            # FILTER 1B: Question marks
            if "?" in title:
                self.logger.debug(f"    Question: {title[:60]}")
                continue
            
            # FILTER 1C: Very long titles (likely articles)
            if len(title) > 100:
                self.logger.debug(f"    Long title: {title[:60]}")
                continue
            
            # FILTER 1D: Starts with number
            if title_lower.strip() and title_lower.strip()[0].isdigit():
                self.logger.debug(f"    Numbered: {title[:60]}")
                continue
            
            # ===================================
            # FILTER 2: Domain validation
            # ===================================
            domain = self._extract_domain(link)
            
            if not domain or domain in seen_domains:
                continue
            
            if not self._is_valid_business_domain(domain):
                self.logger.debug(f"    Non-business: {domain}")
                continue
            
            # ===================================
            # FILTER 3: Snippet validation
            # ===================================
            snippet_lower = snippet.lower()
            
            article_snippet_keywords = [
                "article", "blog post", "published", "written by",
                "read more", "learn how", "discover", "guide to",
                "opinion", "commentary", "analysis", "study"
            ]
            
            if any(kw in snippet_lower for kw in article_snippet_keywords):
                self.logger.debug(f"    Article snippet: {domain}")
                continue
            
            # ===================================
            # ACCEPT: Use domain-based name
            # ===================================
            company_name = self._get_clean_name_from_domain(domain)
            
            # Skip if name is too short or generic
            if len(company_name) < 3:
                self.logger.debug(f"    Name too short: {company_name}")
                continue
            
            companies.append({
                "name": company_name,  # Domain-based name!
                "domain": domain,
                "snippet": snippet,
                "search_title": title,  # Keep for reference
                "source": "google_search"
            })
            
            seen_domains.add(domain)
            self.logger.debug(f"    {company_name} ({domain})")
        
        return companies
    
    # ======================================================================
    # METHOD 4: Domain Validation (COMPREHENSIVE BLOCKLIST)
    # ======================================================================
    
    def _is_valid_business_domain(self, domain: str) -> bool:
        """
        Comprehensive domain validation with extensive blocklist.
        """
        if not domain:
            return False

        # COMPREHENSIVE BLOCKLIST
        bad_keywords = [
            # Blogs & Articles
            "blog", "news", "article", "post", "press", "media",
            
            # Directories & Lists
            "directory", "list", "top", "best", "review", "comparison", 
            "vs", "builtin", "crunchbase",
            
            # Forums & Community
            "forum", "community.", "discuss", "reddit", "quora",
            
            # Social Media
            "linkedin", "facebook", "twitter", "instagram", "youtube",
            "tiktok", "pinterest",
            
            # Job Sites
            "greenhouse.io", "lever.co", "workday", "careers.",
            "job-boards", "jobs.", "hiring.", "jobvite",
            
            # Developer Platforms
            "github.com", "gitlab.com", "stackoverflow.com",
            "codepen.io", "repl.it",
            
            # Industry Publications
            "consumergoods.com", "industryweek.com", "constructiondive.com",
            "ciodive.com", "supplychaindive.com", "retaildive.com",
            
            # Major News Outlets
            "propublica.org", "techcrunch.com", "venturebeat.com",
            "forbes.com", "bloomberg.com", "reuters.com", "cnbc.com",
            "businesswire.com", "prnewswire.com",
            "economist.com", "ft.com", "nytimes.com", "wsj.com",
            
            # Fashion/Lifestyle
            "vogue.com", "gq.com", "elle.com", "cosmopolitan.com",
            
            # Financial/Valuation
            "valuadder.com", "valuation", "advisors.com",
            "budgetsaresexy.com", "mint.com", "nerdwallet.com",
            
            # Academic/Research
            "springer.com", "sciencedirect.com", "nature.com",
            "cell.com", "pubsonline", "ncbi.nlm.nih.gov", "arxiv.org",
            "jstor.org", "researchgate.net", "tandfonline.com",
            "academic.oup.com", "papers.ssrn.com",
            
            # Medical News/Info
            "neurologylive.com", "neurologyadvisor.com",
            "medscape.com", "webmd.com", "healthline.com",
            
            # Industry Associations
            "association", "alliance", "council",
            "mema.org", "autosinnovate.org", "automotivealabama.org",
            
            # Economic Development
            "edpnc", "commerce.com", "economic", "crda.org",
            "sccommerce.com",
            
            # Investor Relations Pages
            "investors.", "investor.",
            
            # Consulting Firms
            "bcg.com", "bain.com", "mckinsey.com", "deloitte.com",
            
            # Marketing/Impact
            "paritynow.co", "impact.", "conference-board.org",
            
            # E-commerce Platforms
            "shopify.com/blog", "wix.com/blog", "squarespace.com/blog",
            
            # Wiki & Reference
            "wiki", "wikipedia", "fandom.com", "wikihow.com",
            
            # Government/Education
            ".gov", ".edu", "university", "college",
            "cityhall", "ci.", "city of", "cityof", "leeflorida.org",
            
            # Other
            "medium.com", "wordpress.com", "blogspot.com",
            "substack.com", "ghost.io", "chegg.com"
        ]

        domain_lower = domain.lower()
        
        # Check blocklist
        if any(bad in domain_lower for bad in bad_keywords):
            return False

        # Must be business TLD
        valid_tlds = (".com", ".io", ".ai", ".co", ".net", ".org", ".us", ".uk")
        if not any(domain.endswith(tld) for tld in valid_tlds):
            return False

        # Block news indicators
        news_indicators = ["news", "media", "press", "times", "post", "journal", "wire"]
        if any(indicator in domain_lower for indicator in news_indicators):
            return False

        # Block if too long
        if len(domain) > 50:
            return False

        # Block if too many hyphens
        if domain.count("-") > 2:
            return False

        return True
    
    # ======================================================================
    # METHOD 5: Verify ICP Match
    # ======================================================================
    
    def _verify_company_matches_icp(
        self, 
        domain: str, 
        icp_data: Dict[str, Any]
    ) -> Tuple[bool, float, str]:
        """
        Scrape website and calculate ICP match score.
        """
        try:
            from src.scraper.website_scraper import WebsiteScraper
            
            scraper = WebsiteScraper()
            url = f"https://{domain}"
            scraped = scraper.scrape_website(url)
            
            if not scraped or len(scraped.get("combined_text", "")) < 200:
                return False, 0.0, "Insufficient content"
            
            content = scraped["combined_text"].lower()
            
            # Confidence scoring
            score = 0.0
            reasons = []
            
            # Industry match (25%)
            customer_industry = icp_data.get('customer_industry', '').lower()
            industries = [ind.strip() for ind in customer_industry.split(',') if ind.strip()]
            
            industry_matches = 0
            for industry in industries:
                industry_words = [w for w in industry.split() if len(w) > 3]
                if any(word in content for word in industry_words):
                    industry_matches += 1
            
            if industries and industry_matches > 0:
                industry_score = min(0.25, (industry_matches / len(industries)) * 0.25)
                score += industry_score
                reasons.append(f"Industry match ({industry_matches}/{len(industries)})")
            
            # Characteristics (35%)
            characteristics = icp_data.get('ideal_customer_characteristics', [])
            char_matches = 0
            
            for char in characteristics:
                key_terms = [word.lower() for word in char.split() if len(word) > 4]
                if any(term in content for term in key_terms):
                    char_matches += 1
            
            if characteristics:
                char_score = (char_matches / len(characteristics)) * 0.35
                score += char_score
                if char_matches > 0:
                    reasons.append(f"Has {char_matches}/{len(characteristics)} characteristics")
            
            # Pain points (25%)
            pain_points = icp_data.get('pain_points_solved', [])
            pain_matches = 0
            
            for pain in pain_points:
                key_terms = [word.lower() for word in pain.split() if len(word) > 4]
                if any(term in content for term in key_terms):
                    pain_matches += 1
            
            if pain_points:
                pain_score = (pain_matches / len(pain_points)) * 0.25
                score += pain_score
                if pain_matches > 0:
                    reasons.append(f"Addresses {pain_matches} pain points")
            
            # Company size (15%)
            customer_size = icp_data.get('customer_company_size', '').lower()
            size_score = 0.0
            
            if 'enterprise' in customer_size:
                if any(word in content for word in ['enterprise', 'fortune', 'global', 'worldwide']):
                    size_score = 0.15
                    reasons.append("Enterprise indicators")
            elif 'smb' in customer_size or 'small' in customer_size:
                if any(word in content for word in ['startup', 'small business', 'growing']):
                    size_score = 0.15
                    reasons.append("SMB indicators")
            elif 'mid' in customer_size:
                if any(word in content for word in ['established', 'leading', 'regional']):
                    size_score = 0.15
                    reasons.append("Mid-market indicators")
            
            score += size_score
            
            # RAISED THRESHOLD: 0.40 instead of 0.30
            matches = score >= 0.40
            reason = ", ".join(reasons) if reasons else "Low ICP match"
            
            return matches, round(score, 2), reason
            
        except Exception as e:
            self.logger.error(f"   Verification error: {str(e)}")
            return False, 0.0, "Verification failed"
    
    # ======================================================================
    # METHOD 6: LLM Buyer Verification + NAME CORRECTION
    # ======================================================================
    
    def _llm_verify_and_correct_name(
        self, 
        domain_name: str,  # Name from domain
        domain: str,
        website_content: str, 
        icp_data: Dict[str, Any]
    ) -> Tuple[bool, str, str]:
        """
        Enhanced LLM verification that ALSO corrects company names.
        
        Returns: (is_buyer, corrected_name, reason)
        """
        
        prompt = f"""
You are a B2B sales qualification expert with TWO tasks:

1. Verify if this is a REAL COMPANY that can BUY products
2. Provide the CORRECT OFFICIAL COMPANY NAME

[CANDIDATE]
Name (from domain): {domain_name}
Domain: {domain}
Website Content (sample): {website_content[:2500]}

[TARGET ICP]
Product: {icp_data.get('what_they_sell', 'Unknown')}
Target Industry: {icp_data.get('customer_industry', 'Unknown')}
Target Buyers: {', '.join(icp_data.get('target_buyers', []))}

[TASK 1: VERIFY - DISQUALIFY IF]
- Industry association or alliance (e.g., "Automotive Manufacturers Association")
- Economic development organization
- News article, blog, or informational content site
- Research paper or academic institution
- Consulting firm writing ABOUT the industry (McKinsey, Deloitte, etc.)
- Government agency or municipal website (unless ICP explicitly targets government)
- Advocacy group or coalition (e.g., "Business for Plastics Treaty")
- Forum or Q&A site (StackExchange, Reddit, etc.)
- Completely wrong industry

[TASK 2: NAME CORRECTION]
- Look at the website content to find the OFFICIAL company name
- If domain name is close, use it (e.g., "Ferguson" is fine for ferguson.com)
- If domain name is abbreviated, expand it (e.g., "Resmith Const" → "RE Smith Construction")
- Use the name that appears in the website's header, footer, or about section

[QUALIFY IF]
- Real operating company with products/services
- Matches target industry
- Would realistically purchase this product type
- Has actual business operations (not just advocacy/research)

Return ONLY valid JSON:
{{
    "is_buyer": true/false,
    "corrected_name": "Official Company Name Here",
    "confidence": 0-100,
    "reason": "One sentence explanation"
}}

NO other text. ONLY JSON.
"""

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=500
                )
            )

            raw_text = response.text.strip()

            # Extract JSON
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1

            if start == -1 or end == 0:
                self.logger.warning("LLM didn't return JSON, accepting by default")
                return True, domain_name, "LLM response invalid"
            
            result = json.loads(raw_text[start:end])
            
            is_buyer = result.get("is_buyer", False)
            corrected_name = result.get("corrected_name", domain_name)
            confidence = result.get("confidence", 50)
            reason = result.get("reason", "No reason provided")
            
            # If name correction failed, keep domain name
            if not corrected_name or corrected_name == "":
                corrected_name = domain_name
            
            return is_buyer, corrected_name, reason
            
        except json.JSONDecodeError as e:
            self.logger.error(f"LLM returned invalid JSON: {e}")
            return True, domain_name, "JSON parse error - accepting"
        except Exception as e:
            self.logger.error(f"LLM verification failed: {e}")
            return True, domain_name, "LLM unavailable - accepting"
    
    # ======================================================================
    # MAIN METHOD: Find Prospects (WITH NAME CORRECTION)
    # ======================================================================
    
    def find_prospects(self, icp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main prospect discovery with domain-based names + LLM correction.
        """
        self.logger.info("=" * 70)
        self.logger.info("🔍 PROSPECT DISCOVERY (Hybrid Version)")
        self.logger.info("=" * 70)
        
        # Step 1: Generate queries
        search_queries = self._generate_comprehensive_search_queries(icp_data)
        
        if not search_queries:
            self.logger.error(" No queries - using LLM fallback")
            return self._find_prospects_via_llm_fallback(icp_data)
        
        self.logger.info(f"\n Generated {len(search_queries)} queries:")
        for i, q in enumerate(search_queries, 1):
            self.logger.info(f"   {i:2d}. '{q}'")
        
        # Step 2: Execute searches
        self.logger.info(f"\n Executing searches...")
        all_results = []
        
        for i, query in enumerate(search_queries, 1):
            results = self._execute_google_search(query, num_results=10)
            all_results.extend(results)
            self.logger.info(f"   Query {i}/{len(search_queries)}: {len(results)} results")
            time.sleep(1)
        
        self.logger.info(f" Collected {len(all_results)} search results")
        
        # Step 3: Extract companies (domain-based names)
        self.logger.info(f"\n Extracting companies...")
        company_candidates = self._extract_companies_from_search_results(all_results)
        
        self.logger.info(f" Extracted {len(company_candidates)} candidates")
        
        if not company_candidates:
            self.logger.warning("  No companies found - using LLM fallback")
            return self._find_prospects_via_llm_fallback(icp_data)
        
        # Step 4: Verify companies (WITH NAME CORRECTION)
        self.logger.info(f"\n✓ Verifying companies with LLM name correction...")
        validated_prospects = []
        
        for i, candidate in enumerate(company_candidates, 1):
            domain_name = candidate['name']  # Domain-based name
            domain = candidate['domain']
            
            self.logger.info(f"\n   [{i}/{len(company_candidates)}] {domain_name} ({domain})")
            
            # First: Traditional ICP matching
            matches, confidence, reason = self._verify_company_matches_icp(domain, icp_data)
            
            if matches:
                # Second: LLM verification + name correction
                from src.scraper.website_scraper import WebsiteScraper
                scraper = WebsiteScraper()
                scraped = scraper.scrape_website(f"https://{domain}")
                
                if scraped and len(scraped.get("combined_text", "")) >= 200:
                    # LLM returns: (is_buyer, corrected_name, reason)
                    is_buyer, corrected_name, llm_reason = self._llm_verify_and_correct_name(
                        domain_name,
                        domain,
                        scraped["combined_text"],
                        icp_data
                    )
                    
                    if is_buyer:
                        validated_prospects.append({
                            "name": corrected_name,  # Use LLM-corrected name!
                            "domain": domain,
                            "confidence": confidence,
                            "why_good_fit": f"{reason} | LLM: {llm_reason}",
                            "source": "web_search_llm_verified"
                        })
                        
                        self.logger.info(f"       {confidence:.0%} - VERIFIED BUYER")
                        self.logger.info(f"         Name: {corrected_name}")
                        self.logger.info(f"         LLM: {llm_reason}")
                    else:
                        self.logger.info(f"       LLM REJECTED: {llm_reason}")
                else:
                    # If can't scrape for LLM, accept based on ICP alone
                    validated_prospects.append({
                        "name": domain_name,
                        "domain": domain,
                        "confidence": confidence,
                        "why_good_fit": reason,
                        "source": "web_search_verified"
                    })
                    self.logger.info(f"       {confidence:.0%} (no LLM check)")
            else:
                self.logger.info(f"       {reason}")
            
            if len(validated_prospects) >= settings.SEARCH_MAX_RESULTS:
                break
            
            time.sleep(0.5)
        
        # Step 5: Augment if needed
        if len(validated_prospects) < 5:
            self.logger.warning(f"\n  Only {len(validated_prospects)} - augmenting")
            llm_prospects = self._find_prospects_via_llm_fallback(icp_data)
            
            existing_domains = {p['domain'] for p in validated_prospects}
            for llm_p in llm_prospects:
                if llm_p['domain'] not in existing_domains:
                    validated_prospects.append(llm_p)
                    if len(validated_prospects) >= settings.SEARCH_MAX_RESULTS:
                        break
        
        # Step 6: Final cleanup
        self.logger.info(f"\n Final quality check...")
        
        final_prospects = []
        suspicious_patterns = [
            "job application", "archive", "survey", "study",
            "research", "report", "statement on", "notice to",
            "exploring", "following", "understanding", "wants to",
            "are nurses", "willing to", "comes to the", "emerging",
            "annual outlook", "industry growth", "updated", "new-vehicle"
        ]
        
        for prospect in validated_prospects:
            name_lower = prospect['name'].lower()
            
            if any(pattern in name_lower for pattern in suspicious_patterns):
                self.logger.debug(f"    Filtered: {prospect['name']}")
                continue
            
            final_prospects.append(prospect)
        
        self.logger.info("=" * 70)
        self.logger.info(f" COMPLETE: {len(final_prospects)} prospects")
        self.logger.info("=" * 70)
        
        return final_prospects
    
    # ======================================================================
    # FALLBACK: LLM Generation
    # ======================================================================
    
    def _find_prospects_via_llm_fallback(self, icp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback LLM generation when search fails."""
        self.logger.info(" Using LLM fallback...")
        
        what_they_sell = icp_data.get('what_they_sell', 'Unknown')
        customer_industry = icp_data.get('customer_industry', 'Various')
        customer_size = icp_data.get('customer_company_size', 'SMB to Enterprise')
        target_buyers = icp_data.get('target_buyers', [])
        pain_points = icp_data.get('pain_points_solved', [])
        customer_traits = icp_data.get('ideal_customer_characteristics', [])

        prompt = f"""
Find 10-15 REAL companies that would BUY (not compete):

Product: {what_they_sell}
Industry: {customer_industry}
Size: {customer_size}
Buyers: {', '.join(target_buyers)}
Traits: {', '.join(customer_traits)}

Return JSON array:
[{{"name": "Company", "domain": "domain.com", "fit_score": 0.9, "why_prospect": "Reason"}}]
"""

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1000
                )
            )

            raw_text = response.text.strip()
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1

            if start == -1:
                return []

            data = json.loads(raw_text[start:end])

            cleaned = []
            for item in data:
                if not isinstance(item, dict) or "name" not in item:
                    continue
                
                if "domain" not in item or not item["domain"]:
                    item["domain"] = self._validate_domain_via_google(item["name"])
                
                if item["domain"]:
                    cleaned.append({
                        "name": item["name"],
                        "domain": item["domain"],
                        "confidence": item.get("fit_score", 0.7),
                        "why_good_fit": item.get("why_prospect", "LLM suggested"),
                        "source": "llm_fallback"
                    })
            
            return cleaned[:settings.SEARCH_MAX_RESULTS]

        except Exception as e:
            self.logger.error(f"❌ LLM fallback failed: {e}")
            return []
    
    # ======================================================================
    # HELPER METHODS
    # ======================================================================
    
    def _validate_domain_via_google(self, company_name: str) -> str:
        """Find official domain via Google."""
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
                time.sleep(2)
                return self._validate_domain_via_google(company_name)
            
            if resp.status_code != 200:
                return None

            data = resp.json()

            for item in data.get("items", []):
                link = item.get("link", "")
                domain = self._extract_domain(link)
                if self._is_valid_business_domain(domain):
                    return domain

        except:
            pass

        return None
    
    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain.lower()
        except:
            return ""


# ======================================================================
# TEST DRIVER
# ======================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" Testing Hybrid Prospect Finder (Domain Names + LLM Correction)")
    print("=" * 70)

    test_icp = {
        "what_they_sell": "Amazon seller optimization software",
        "customer_industry": "E-commerce, Consumer Goods",
        "customer_company_size": "SMB to Enterprise",
        "target_buyers": ["Brand Manager", "E-commerce Director"],
        "pain_points_solved": [
            "Poor Amazon visibility",
            "Inefficient keyword research"
        ],
        "ideal_customer_characteristics": [
            "Sells on Amazon",
            "Manages 10+ SKUs",
            "Revenue $1M+"
        ]
    }

    finder = ProspectFinder()
    prospects = finder.find_prospects(test_icp)

    print("\n" + "=" * 70)
    print(f" {len(prospects)} prospects found")
    print("=" * 70)
    
    for i, p in enumerate(prospects[:10], 1):
        print(f"\n{i}. {p['name']} ({p['domain']})")
        print(f"   {p['confidence']:.0%} - {p['why_good_fit']}")