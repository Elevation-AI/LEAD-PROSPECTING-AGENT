"""
Prospect Finder v7.0 - Simplified Single-Pass Architecture
==============================================================
Key Changes from v6.x:
- Single comprehensive LLM classification (no conflicting heuristics)
- Minimal pre-filtering (only obvious blocklist)
- Temperature=0 for deterministic results
- Fixed NoneType bugs
- Better ICP and geographic matching
- Reduced volatility between runs
"""

import requests
import time
import sys
import os
from typing import List, Dict, Any, Tuple
import json
import google.genai as genai
from google.genai import types
from urllib.parse import urlparse

# Import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logger
from config.settings import settings
from src.scraper.website_scraper import WebsiteScraper


class ProspectFinder:
    """
    Prospect Finder v7.0 - Simplified Architecture

    Core Principles:
    1. Let LLM make intelligent decisions (not dumb heuristics)
    2. Single comprehensive classification per candidate
    3. Deterministic settings (temperature=0)
    4. Proper ICP and geographic matching
    """

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.api_key = settings.GOOGLE_SEARCH_API_KEY
        self.search_engine_id = settings.GOOGLE_SEARCH_ENGINE_ID
        self.base_url = "https://www.googleapis.com/customsearch/v1"

        # Initialize Gemini LLM
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.scraper = WebsiteScraper()

        # v7.0: Minimal blocklist - only truly irrelevant domains
        self.BLOCKLIST = [
            # Social media
            "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
            "youtube.com", "tiktok.com", "pinterest.com", "x.com",
            # News/Media (actual news sites)
            "reuters.com", "bloomberg.com", "forbes.com", "techcrunch.com",
            "businessinsider.com", "cnbc.com", "wsj.com", "nytimes.com",
            "cnn.com", "bbc.com", "foxnews.com",
            # Directories/Reviews
            "crunchbase.com", "glassdoor.com", "indeed.com", "yelp.com",
            "g2.com", "capterra.com", "trustpilot.com", "bbb.org",
            "yellowpages.com", "manta.com",
            # Developer platforms
            "github.com", "gitlab.com", "stackoverflow.com", "npmjs.com",
            # Reference/Wiki
            "wikipedia.org", "medium.com", "quora.com", "reddit.com",
            # Job boards
            "greenhouse.io", "lever.co", "workday.com", "jobvite.com",
            "ziprecruiter.com", "monster.com", "careerbuilder.com",
            # Academic
            "sciencedirect.com", "researchgate.net", "academia.edu",
            "springer.com", "elsevier.com",
            # Directories
            "clutch.co", "goodfirms.co", "toptal.com"
        ]

    # ======================================================================
    # PHASE 1: SEARCH QUERY GENERATION (Deterministic + LLM)
    # ======================================================================

    def _generate_search_queries(self, icp_data: Dict[str, Any]) -> List[str]:
        """
        v7.0: Generate search queries using templates + LLM
        More deterministic than pure LLM generation
        """
        self.logger.info(" Generating search queries...")

        what_they_sell = icp_data.get('what_they_sell', '')
        customer_industry = icp_data.get('customer_industry', '')
        geo = icp_data.get('serviceable_geography', {})

        # Extract industries as list
        industries = [ind.strip() for ind in customer_industry.split(',') if ind.strip()][:5]

        # Get geographic terms
        geo_terms = []
        if geo.get('scope') == 'regional':
            geo_terms = geo.get('states_or_regions', [])[:5]
        elif geo.get('scope') == 'national':
            geo_terms = geo.get('countries', ['USA'])[:3]

        # Template-based queries (deterministic)
        template_queries = []
        for industry in industries:
            template_queries.extend([
                f'largest {industry} companies USA',
                f'top {industry} companies headquarters',
                f'leading {industry} companies',
                f'{industry} companies with facilities',
            ])
            # Add geographic queries
            for geo_term in geo_terms[:2]:
                template_queries.append(f'{industry} companies {geo_term}')

        # LLM-generated queries for diversity
        llm_queries = self._llm_generate_queries(icp_data)

        # Combine and deduplicate
        all_queries = list(dict.fromkeys(template_queries + llm_queries))

        self.logger.info(f" Generated {len(all_queries)} queries ({len(template_queries)} template + {len(llm_queries)} LLM)")

        return all_queries[:25]

    def _llm_generate_queries(self, icp_data: Dict[str, Any]) -> List[str]:
        """Generate additional queries via LLM"""
        what_they_sell = icp_data.get('what_they_sell', '')
        customer_industry = icp_data.get('customer_industry', '')

        prompt = f"""Generate 10 Google search queries to find companies that would BUY this service:

SERVICE: {what_they_sell}
TARGET INDUSTRIES: {customer_industry}

Rules:
- Find companies that NEED this service (end-users with facilities)
- DO NOT find companies that SELL similar services (competitors)
- DO NOT include words like "software", "platform", "tool", "solution"
- Focus on finding manufacturers, retailers, property owners, facility operators

Return ONLY a JSON array of 10 queries:
["query 1", "query 2", ...]"""

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low temperature for consistency
                    max_output_tokens=500
                )
            )

            raw_text = response.text.strip()
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1

            if start != -1 and end > start:
                queries = json.loads(raw_text[start:end])
                return [q for q in queries if isinstance(q, str) and len(q) > 5][:10]
        except Exception as e:
            self.logger.debug(f"LLM query generation error: {e}")

        return []

    # ======================================================================
    # PHASE 2: SEARCH EXECUTION
    # ======================================================================

    def _execute_search(self, query: str) -> List[Dict[str, str]]:
        """Execute Google Custom Search"""
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": 10,
        }

        try:
            resp = requests.get(self.base_url, params=params, timeout=15)

            if resp.status_code == 429:
                self.logger.warning("Rate limit, waiting 5s...")
                time.sleep(5)
                return self._execute_search(query)

            if resp.status_code != 200:
                return []

            items = resp.json().get("items", [])
            return [{"title": item.get("title", ""), "link": item.get("link", "")} for item in items]

        except Exception as e:
            self.logger.debug(f"Search error: {e}")
            return []

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "").lower()
            parts = domain.split(".")
            if len(parts) > 2 and parts[-2] not in ['co', 'com']:
                domain = ".".join(parts[-2:])
            return domain
        except:
            return ""

    def _is_valid_domain(self, domain: str) -> bool:
        """v7.0: Minimal domain validation - only block obvious non-businesses"""
        if not domain or len(domain) < 4:
            return False

        domain_lower = domain.lower()

        # Check blocklist
        if any(blocked in domain_lower for blocked in self.BLOCKLIST):
            return False

        # Block government/education (but NOT .org - some legitimate businesses use it)
        if domain_lower.endswith(('.gov', '.edu', '.mil')):
            return False

        # Valid TLDs
        valid_tlds = ['.com', '.io', '.co', '.net', '.org', '.ai', '.tech', '.us', '.ca', '.uk', '.de', '.in', '.biz']
        if not any(domain_lower.endswith(tld) for tld in valid_tlds):
            return False

        return True

    # ======================================================================
    # PHASE 3: SINGLE COMPREHENSIVE LLM CLASSIFICATION (v7.1 Core)
    # ======================================================================

    def _get_business_type_guidance(self, seller_type: str, what_they_sell: str) -> str:
        """
        v7.1: Generate business-type-specific classification guidance.
        This helps the LLM understand the correct customer identification logic.
        """
        if seller_type == "physical_service":
            return f"""
=== PHYSICAL SERVICE PROVIDER GUIDANCE ===
The seller provides: {what_they_sell}

QUALIFIED PROSPECTS (companies that COMMISSION work):
✓ Real estate DEVELOPERS actively building properties
✓ Retail chains EXPANDING to new locations
✓ Healthcare systems BUILDING new facilities
✓ Hotel chains DEVELOPING new properties
✓ Companies RELOCATING or RENOVATING headquarters
✓ Growing companies needing NEW facilities

NOT QUALIFIED (companies that just HAVE facilities):
✗ Manufacturers with existing factories (they have maintenance teams)
✗ Established retailers with existing stores (steady state)
✗ Companies not in growth/expansion mode
✗ Service providers to the same industry (consultants, software vendors)
✗ Other construction/maintenance companies (COMPETITORS)
✗ Facilities management companies (they MANAGE, not BUILD)
✗ Trade associations / industry groups (not actual companies)
✗ Oil & gas / energy companies (specialized in-house teams)
✗ Large corporations with in-house construction divisions

KEY QUESTION: Is this company actively COMMISSIONING new construction/services, or do they just EXIST?
"""
        elif seller_type == "engineering_services":
            return f"""
=== ENGINEERING/TECHNOLOGY SERVICES GUIDANCE ===
The seller provides: {what_they_sell}

QUALIFIED PROSPECTS (companies that OUTSOURCE this work):
✓ OEMs who need external engineering support
✓ Companies TRANSITIONING to new technology
✓ Companies WITHOUT large in-house engineering teams
✓ Startups needing development expertise
✓ Companies with specific project needs beyond capacity

NOT QUALIFIED (COMPETITORS or companies with in-house capability):
✗ Companies that PROVIDE similar engineering services (COMPETITORS!)
✗ Large tech companies with massive in-house teams
✗ IT consulting firms (they're competitors, not customers)
✗ Software development agencies (competitors)

CRITICAL COMPETITOR CHECK:
- If the candidate provides similar services → REJECT as COMPETITOR
- Bosch, Continental, Aptiv for automotive software → COMPETITORS
- Infosys, TCS, Wipro for IT services → COMPETITORS
"""
        elif seller_type == "software_saas":
            return f"""
=== SOFTWARE/SAAS GUIDANCE ===
The seller provides: {what_they_sell}

QUALIFIED PROSPECTS (companies with the PROBLEM this solves):
✓ Companies actively selling on relevant platforms
✓ Companies with the specific pain point this addresses
✓ Companies using complementary tools (integration opportunity)
✓ Growing companies needing better tooling

NOT QUALIFIED:
✗ Other software companies (often competitors or don't need this)
✗ Companies without the specific problem
✗ Companies too small to afford/need the solution
✗ Platforms/marketplaces (they're not end users)
"""
        elif seller_type == "b2b_supplier":
            return f"""
=== B2B SUPPLIER GUIDANCE ===
The seller provides: {what_they_sell}

QUALIFIED PROSPECTS (companies that USE/INCORPORATE these products):
✓ Manufacturers who need these components
✓ Companies in industries that consume these materials
✓ OEMs who incorporate into their products

NOT QUALIFIED:
✗ Distributors/resellers (unless that's the model)
✗ Companies in unrelated industries
✗ Other suppliers of similar products (competitors)
"""
        elif seller_type == "consulting":
            return f"""
=== CONSULTING/ADVISORY GUIDANCE ===
The seller provides: {what_they_sell}

QUALIFIED PROSPECTS:
✓ Companies undergoing transformation/change
✓ Companies entering new markets
✓ Companies with strategic challenges
✓ Companies without internal expertise in this area

NOT QUALIFIED:
✗ Other consulting firms (competitors)
✗ Companies with strong internal capabilities
✗ Companies not in growth/change mode
"""
        else:
            return """
=== GENERAL GUIDANCE ===
Check if this company would genuinely BUY the product/service.

REJECT if:
- They SELL similar products/services (COMPETITOR)
- They serve the same market but don't need this themselves
- They're a platform/software that serves the industry but isn't a buyer
"""

    def _classify_company(
        self,
        domain: str,
        website_content: str,
        icp_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        v7.1: Business-type-aware classification

        Uses seller_business_type to provide specific guidance for different industries.
        """
        what_they_sell = icp_data.get('what_they_sell', '')
        customer_industry = icp_data.get('customer_industry', '')
        target_buyers = icp_data.get('target_buyers', [])
        ideal_characteristics = icp_data.get('ideal_customer_characteristics', [])
        avoid_types = icp_data.get('avoid_company_types', [])
        seller_type = icp_data.get('seller_business_type', 'unknown')

        # Geographic constraints
        geo = icp_data.get('serviceable_geography', {})
        geo_scope = geo.get('scope', 'global')
        geo_countries = geo.get('countries', [])
        geo_regions = geo.get('states_or_regions', [])

        geo_constraint = ""
        if geo_scope == 'regional' and geo_regions:
            geo_constraint = f"GEOGRAPHIC REQUIREMENT: Company must operate in: {', '.join(geo_regions)}"
        elif geo_scope == 'national' and geo_countries:
            geo_constraint = f"GEOGRAPHIC REQUIREMENT: Company must operate in: {', '.join(geo_countries)}"

        # v7.1: Build business-type-specific guidance
        business_type_guidance = self._get_business_type_guidance(seller_type, what_they_sell)

        prompt = f"""You are a B2B sales qualification expert. Analyze if this company is a QUALIFIED PROSPECT.

=== SELLER INFORMATION ===
Business Type: {seller_type}
Product/Service: {what_they_sell}

=== IDEAL CUSTOMER PROFILE (ICP) ===
Target Industries: {customer_industry}
Target Buyer Titles: {', '.join(target_buyers[:5])}
Ideal Characteristics: {', '.join(ideal_characteristics[:5])}
{geo_constraint}

=== COMPANIES TO REJECT (CRITICAL!) ===
{chr(10).join('- ' + avoid for avoid in avoid_types) if avoid_types else '- Competitors selling similar products/services'}

{business_type_guidance}

=== CANDIDATE COMPANY ===
Domain: {domain}
Website Content (excerpt):
{website_content[:3500]}

=== CLASSIFICATION TASK ===

Step 1: What does this company ACTUALLY DO?
- What is their primary business model?
- Are they a BUYER or a COMPETITOR/VENDOR?

Step 2: COMPETITOR CHECK (CRITICAL!)
- Does this company SELL similar products/services to our seller?
- If YES → REJECT as COMPETITOR
- Companies in "avoid_company_types" list must be REJECTED

Step 3: Would they BUY the seller's product/service?
- Do they have an ACTIVE NEED?
- For services: Are they DEVELOPING/EXPANDING/BUILDING? (not just existing)
- For software: Do they have the PROBLEM this solves?

Step 4: Geographic Match
- Are they in the serviceable geography?

=== OUTPUT ===
Return ONLY this JSON:
{{
    "is_qualified_prospect": true/false,
    "company_name": "Official company name from website",
    "what_they_do": "Brief description of their actual business (1 sentence)",
    "primary_business_type": "developer | expanding_company | oem | brand | manufacturer | retailer | software_company | service_provider | other",
    "is_competitor": true/false,
    "has_active_need": true/false,
    "matches_target_industry": true/false,
    "matches_geography": true/false,
    "would_buy_reasoning": "Why they would or wouldn't buy this service (1 sentence)",
    "confidence": 0-100,
    "rejection_reason": "Only if is_qualified_prospect is false - specific reason"
}}"""

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,  # Deterministic
                    max_output_tokens=500
                )
            )

            raw_text = response.text.strip()
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1

            if start == -1 or end <= start:
                return self._default_classification("Failed to parse LLM response")

            result = json.loads(raw_text[start:end])

            # Validate required fields
            if "is_qualified_prospect" not in result:
                result["is_qualified_prospect"] = False
            if "confidence" not in result:
                result["confidence"] = 50
            if "company_name" not in result:
                result["company_name"] = domain.split('.')[0].title()

            return result

        except json.JSONDecodeError as e:
            self.logger.debug(f"JSON parse error for {domain}: {e}")
            return self._default_classification("JSON parse error")
        except Exception as e:
            self.logger.debug(f"Classification error for {domain}: {e}")
            return self._default_classification(str(e))

    def _default_classification(self, reason: str) -> Dict[str, Any]:
        """Return default classification on error"""
        return {
            "is_qualified_prospect": False,
            "company_name": "",
            "what_they_do": "Unknown",
            "confidence": 0,
            "rejection_reason": reason
        }

    # ======================================================================
    # PHASE 4: LLM-BASED PROSPECT GENERATION (Fallback)
    # ======================================================================

    def _generate_prospects_via_llm(self, icp_data: Dict[str, Any], count: int = 15) -> List[Dict[str, Any]]:
        """
        v7.0: Generate prospect suggestions directly via LLM
        Used when search doesn't find enough candidates
        """
        self.logger.info(f" Generating {count} prospects via LLM...")

        what_they_sell = icp_data.get('what_they_sell', '')
        customer_industry = icp_data.get('customer_industry', '')
        geo = icp_data.get('serviceable_geography', {})

        geo_constraint = ""
        if geo.get('scope') == 'regional':
            regions = geo.get('states_or_regions', [])
            if regions:
                geo_constraint = f"MUST be located in or operate in: {', '.join(regions[:10])}"
        elif geo.get('scope') == 'national':
            countries = geo.get('countries', ['USA'])
            geo_constraint = f"MUST be located in: {', '.join(countries)}"

        prompt = f"""Generate {count} REAL companies that would BUY this service.

SERVICE BEING SOLD: {what_they_sell}
TARGET CUSTOMER INDUSTRIES: {customer_industry}
{geo_constraint if geo_constraint else 'No geographic restriction'}

REQUIREMENTS:
1. Companies must be REAL and currently operating
2. They must NEED this service for their OWN operations
3. They must have PHYSICAL facilities (stores, factories, warehouses, offices)
4. Include a MIX of:
   - Large well-known companies (Fortune 500)
   - Mid-size regional companies
   - Growing companies in target industry

DO NOT INCLUDE:
- Companies that SELL similar services (competitors)
- Software/SaaS companies (unless they have significant physical operations)
- Consulting firms
- Companies outside the geographic area (if specified)

EXAMPLES of what to include for CONSTRUCTION services:
✓ Walmart, Target, Costco (retailers with stores)
✓ Amazon, FedEx, UPS (logistics with warehouses)
✓ Toyota, GM, Ford (manufacturers with factories)
✓ Marriott, Hilton, Hyatt (hotels needing renovation)
✓ HCA Healthcare, Kaiser (hospitals needing facility work)
✓ Starbucks, McDonald's (chains needing buildouts)

Return ONLY a JSON array:
[
    {{
        "name": "Company Name",
        "domain": "company.com",
        "industry": "Their industry",
        "why_buyer": "Why they would buy this service (1 sentence)",
        "estimated_confidence": 70-95
    }}
]"""

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=2000
                )
            )

            raw_text = response.text.strip()
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1

            if start == -1 or end <= start:
                return []

            data = json.loads(raw_text[start:end])

            prospects = []
            for item in data:
                if not isinstance(item, dict) or "name" not in item:
                    continue

                domain = item.get("domain", "")
                if not domain or not self._is_valid_domain(domain):
                    continue

                prospects.append({
                    "name": item["name"],
                    "domain": domain,
                    "confidence": min(item.get("estimated_confidence", 70), 85) / 100,
                    "why_good_fit": item.get("why_buyer", "Matches target customer profile"),
                    "source": "llm_generated",
                    "needs_verification": True
                })

            self.logger.info(f" LLM generated {len(prospects)} prospect suggestions")
            return prospects[:count]

        except Exception as e:
            self.logger.error(f"LLM generation error: {e}")
            return []

    def _verify_llm_prospect(self, prospect: Dict, icp_data: Dict) -> Dict[str, Any]:
        """Verify an LLM-generated prospect by scraping and classifying"""
        domain = prospect.get('domain', '')

        try:
            scraped = self.scraper.scrape_website(f"https://{domain}")

            if not scraped or len(scraped.get("combined_text", "")) < 200:
                return None

            classification = self._classify_company(domain, scraped["combined_text"], icp_data)

            if classification.get("is_qualified_prospect") and classification.get("confidence", 0) >= 60:
                return {
                    "name": classification.get("company_name") or prospect.get("name"),
                    "domain": domain,
                    "confidence": classification.get("confidence", 70) / 100,
                    "why_good_fit": classification.get("would_buy_reasoning") or prospect.get("why_good_fit"),
                    "source": "llm_verified"
                }
        except Exception as e:
            self.logger.debug(f"Verification error for {domain}: {e}")

        return None

    # ======================================================================
    # MAIN PIPELINE
    # ======================================================================

    def find_prospects(self, icp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        v7.0: Simplified single-pass prospect discovery
        """
        self.logger.info("=" * 70)
        self.logger.info(" PROSPECT FINDER v7.0 - SIMPLIFIED ARCHITECTURE")
        self.logger.info("=" * 70)

        # Log ICP summary
        self.logger.info(f" Target: {icp_data.get('customer_industry', 'Various')[:80]}...")

        geo = icp_data.get('serviceable_geography', {})
        geo_scope = geo.get('scope', 'global')
        if geo_scope != 'global':
            regions = geo.get('states_or_regions', []) or geo.get('countries', [])
            self.logger.info(f" Geography: {geo_scope} - {', '.join(regions[:5])}")

        # STAGE 1: Generate Search Queries
        self.logger.info("\n STAGE 1: Generating search queries...")
        queries = self._generate_search_queries(icp_data)

        # STAGE 2: Execute Searches and Collect Candidates
        self.logger.info(f"\n STAGE 2: Executing {len(queries)} searches...")

        seen_domains = set()
        candidates = []

        for i, query in enumerate(queries, 1):
            results = self._execute_search(query)

            for result in results:
                domain = self._extract_domain(result['link'])
                if domain and domain not in seen_domains and self._is_valid_domain(domain):
                    candidates.append({"domain": domain, "title": result['title']})
                    seen_domains.add(domain)

            if i % 5 == 0:
                self.logger.info(f"   Progress: {i}/{len(queries)} queries ({len(candidates)} candidates)")

            time.sleep(1.0)

        self.logger.info(f" Collected {len(candidates)} unique candidates")

        # STAGE 3: Classify Candidates (Single LLM Call Each)
        self.logger.info(f"\n STAGE 3: Classifying candidates...")

        prospects = []
        processed = 0
        accepted = 0
        rejected_reasons = {"not_buyer": 0, "wrong_industry": 0, "wrong_geo": 0, "low_confidence": 0, "error": 0}

        max_to_process = min(50, len(candidates))

        for i, candidate in enumerate(candidates[:max_to_process], 1):
            domain = candidate['domain']

            self.logger.info(f"\n   [{i}/{max_to_process}] {domain}")
            processed += 1

            try:
                # Scrape website
                scraped = self.scraper.scrape_website(f"https://{domain}")

                if not scraped or len(scraped.get("combined_text", "")) < 200:
                    self.logger.info(f"        Skipped: insufficient content")
                    rejected_reasons["error"] += 1
                    continue

                content = scraped["combined_text"]

                # Single comprehensive classification
                classification = self._classify_company(domain, content, icp_data)

                is_qualified = classification.get("is_qualified_prospect", False)
                confidence = classification.get("confidence", 0)
                company_name = classification.get("company_name", domain.split('.')[0].title())

                if is_qualified and confidence >= 60:
                    prospects.append({
                        "name": company_name,
                        "domain": domain,
                        "confidence": confidence / 100,
                        "why_good_fit": classification.get("would_buy_reasoning", "Matches ICP"),
                        "what_they_do": classification.get("what_they_do", ""),
                        "source": "web_search_verified"
                    })
                    accepted += 1
                    self.logger.info(f"        ✓ ACCEPTED ({confidence}%): {company_name}")
                    self.logger.info(f"          {classification.get('would_buy_reasoning', '')[:80]}")
                else:
                    reason = classification.get("rejection_reason", "Does not match ICP")
                    self.logger.info(f"        ✗ REJECTED: {reason[:60]}")

                    # Track rejection reasons
                    if "geography" in reason.lower() or "location" in reason.lower():
                        rejected_reasons["wrong_geo"] += 1
                    elif "industry" in reason.lower():
                        rejected_reasons["wrong_industry"] += 1
                    elif confidence < 60:
                        rejected_reasons["low_confidence"] += 1
                    else:
                        rejected_reasons["not_buyer"] += 1

            except Exception as e:
                self.logger.debug(f"        Error: {e}")
                rejected_reasons["error"] += 1
                continue

            # Check if we have enough
            if len(prospects) >= 20:
                self.logger.info(f"\n   Target reached: {len(prospects)} prospects")
                break

            time.sleep(0.3)

        # STAGE 4: Augment with LLM if needed
        if len(prospects) < 10:
            self.logger.info(f"\n STAGE 4: Augmenting with LLM-generated prospects...")

            llm_prospects = self._generate_prospects_via_llm(icp_data, 20)

            # Verify LLM-generated prospects
            existing_domains = {p['domain'] for p in prospects}
            verified_count = 0

            for llm_prospect in llm_prospects:
                if llm_prospect['domain'] in existing_domains:
                    continue

                self.logger.info(f"   Verifying: {llm_prospect['name']} ({llm_prospect['domain']})")

                verified = self._verify_llm_prospect(llm_prospect, icp_data)
                if verified:
                    prospects.append(verified)
                    existing_domains.add(verified['domain'])
                    verified_count += 1
                    self.logger.info(f"        ✓ Verified: {verified['confidence']:.0%}")

                    if len(prospects) >= 20:
                        break
                else:
                    self.logger.info(f"        ✗ Not verified")

                time.sleep(0.5)

            self.logger.info(f"   Verified {verified_count} LLM-generated prospects")

        # Sort by confidence
        prospects.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        # Summary
        self.logger.info("\n" + "=" * 70)
        self.logger.info(f" COMPLETE: {len(prospects)} qualified prospects")
        self.logger.info(f"   Processed: {processed} candidates")
        self.logger.info(f"   Accepted: {accepted} from web search")
        self.logger.info(f"   Rejected: {sum(rejected_reasons.values())} total")
        self.logger.info(f"     - Not a buyer: {rejected_reasons['not_buyer']}")
        self.logger.info(f"     - Wrong industry: {rejected_reasons['wrong_industry']}")
        self.logger.info(f"     - Wrong geography: {rejected_reasons['wrong_geo']}")
        self.logger.info(f"     - Low confidence: {rejected_reasons['low_confidence']}")
        self.logger.info(f"     - Errors: {rejected_reasons['error']}")

        if prospects:
            avg_confidence = sum(p.get('confidence', 0) for p in prospects) / len(prospects)
            self.logger.info(f"   Avg confidence: {avg_confidence:.0%}")

        self.logger.info("=" * 70)

        return prospects[:settings.SEARCH_MAX_RESULTS]


# ======================================================================
# STANDALONE TEST
# ======================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" PROSPECT FINDER v7.0 - STANDALONE TEST")
    print("=" * 70)

    # Test ICP for construction
    test_icp = {
        "what_they_sell": "Commercial construction, renovation, and interior construction services",
        "customer_industry": "Commercial real estate developers, Manufacturing companies, Retail chains, Healthcare systems, Hospitality companies, Distribution centers",
        "customer_company_size": "Mid-market to Enterprise ($10M - $500M+ revenue)",
        "target_buyers": ["Facilities Manager", "VP of Operations", "Real Estate Director", "COO"],
        "pain_points_solved": [
            "Need for quality construction work",
            "Projects completed on time and budget",
            "Facility expansion requirements"
        ],
        "ideal_customer_characteristics": [
            "Owns or operates commercial facilities",
            "Has multiple locations or properties",
            "Regular construction/renovation needs"
        ],
        "serviceable_geography": {
            "scope": "national",
            "countries": ["USA"],
            "states_or_regions": [],
            "notes": "Nationwide USA"
        },
        "avoid_company_types": [
            "Construction software companies",
            "Other construction contractors",
            "Architecture/engineering firms"
        ]
    }

    finder = ProspectFinder()
    prospects = finder.find_prospects(test_icp)

    print("\n" + "=" * 70)
    print(f" RESULTS: {len(prospects)} Prospects Found")
    print("=" * 70)

    for i, p in enumerate(prospects, 1):
        print(f"\n{i}. {p['name']} ({p['domain']})")
        print(f"   Confidence: {p['confidence']:.0%}")
        print(f"   Why: {p['why_good_fit']}")
        if p.get('what_they_do'):
            print(f"   Business: {p['what_they_do']}")
        print(f"   Source: {p['source']}")



