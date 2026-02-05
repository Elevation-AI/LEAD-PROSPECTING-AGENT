"""
Customer-Focused ICP Generator for B2B Lead Prospecting
========================================================
Generates ICP describing WHO would BUY the product (not what the company does)
ENHANCED: Now includes serviceable geography detection
"""

import json
from google import genai
from google.genai import types
from typing import Dict, Any
import sys
import os

# Add project root to PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.helpers import setup_logger
from config.settings import settings


class ICPGenerator:
    """
    Generates CUSTOMER-FOCUSED Ideal Customer Profile from website.

    CRITICAL: This describes WHO would BUY the product, not what the company does!
    ENHANCED: Now detects serviceable geography to filter prospects appropriately.
    """

    def __init__(self):
        self.logger = setup_logger(__name__)
        # Initialize Gemini LLM with new google.genai library
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_icp(self, website_content: str) -> Dict[str, Any]:
        """
        Main ICP generation - returns customer-focused profile.
        
        Returns schema describing the BUYER, not the seller!
        Now includes serviceable_geography for geographic filtering.
        """
        self.logger.info("Generating customer-focused B2B ICP...")

        prompt = self._build_customer_focused_prompt(website_content)

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1500
                )
            )

            icp_text = response.text.strip()
            self.logger.info("LLM response received")

            icp_data = self._parse_icp_json(icp_text)
            self._validate_customer_focus(icp_data)

            self.logger.info("Customer-focused ICP successfully generated")
            
            # Log geographic scope if detected
            geo_scope = icp_data.get('serviceable_geography', {}).get('scope', 'unclear')
            if geo_scope != 'unclear':
                self.logger.info(f"   Geographic scope detected: {geo_scope}")
                if geo_scope == 'regional':
                    regions = icp_data.get('serviceable_geography', {}).get('states_or_regions', [])
                    if regions:
                        self.logger.info(f"   Serviceable regions: {', '.join(regions)}")
            
            return icp_data

        except Exception as e:
            self.logger.error(f"ICP generation error: {str(e)}")
            raise Exception(f"Customer-focused ICP generation failed: {str(e)}")

    #  ADD NEW FUNCTION HERE (after generate_icp ends, before _build_customer_focused_prompt)
    
    def get_user_overrides(self, auto_icp: Dict) -> Dict:
        """Let user override/extend auto-generated ICP with full control (case-insensitive)"""
        print("\n" + "="*60)
        print(" AUTO-GENERATED ICP REVIEW")
        print("="*60)

        # v2.0: Show seller business type
        seller_type = auto_icp.get('seller_business_type', 'unknown')
        print(f"\n SELLER TYPE: {seller_type}")
        print(f"   (physical_service | software_saas | b2b_supplier | engineering_services | consulting)")

        print(f"\n TARGET CUSTOMERS:")
        print(f"   Industry: {auto_icp.get('customer_industry', 'N/A')}")

        geo = auto_icp.get('serviceable_geography', {})
        print(f"\n GEOGRAPHY:")
        print(f"   Scope: {geo.get('scope', 'unclear')}")

        # Always show current countries (even if empty)
        current_countries = geo.get('countries', [])
        if current_countries:
            print(f"   Countries: {', '.join(current_countries)}")
        else:
            print(f"   Countries: (none)")

        # Always show current regions (even if empty)
        current_regions = geo.get('states_or_regions', [])
        if current_regions:
            print(f"   Regions: {', '.join(current_regions)}")
        else:
            print(f"   Regions: (none)")

        print(f"\n Target Buyers: {', '.join(auto_icp.get('target_buyers', []))}")

        # v2.0: Show avoid_company_types (critical for correct prospecting)
        avoid_types = auto_icp.get('avoid_company_types', [])
        print(f"\n COMPANIES TO AVOID (competitors, wrong fit):")
        if avoid_types:
            for avoid in avoid_types[:5]:
                print(f"   - {avoid}")
        else:
            print("   (none specified - THIS MAY CAUSE ISSUES!)")

        print("\n" + "-"*60)
        print(" Want to customize? (Press Enter to skip any field)")
        
        # ==========================================
        # COUNTRIES - ALWAYS Edit Mode
        # ==========================================
        print(f"\n Current countries: {', '.join(current_countries) if current_countries else '(none)'}")
        country_action = input("   [K]eep all / [R]eplace all / [A]dd only / [E]dit (add/remove): ").strip().upper()
        
        if country_action == 'R':
            new_countries = input("   Enter new countries (e.g., USA, Canada, India): ").strip()
            if new_countries:
                auto_icp['serviceable_geography']['countries'] = [c.strip().upper() for c in new_countries.split(',')]
                auto_icp['serviceable_geography']['scope'] = 'custom'
                self.logger.info(f" Replaced countries: {', '.join(auto_icp['serviceable_geography']['countries'])}")
        
        elif country_action == 'A':
            add_countries = input("   Add which countries? (e.g., India, UK): ").strip()
            if add_countries:
                new_countries = [c.strip().upper() for c in add_countries.split(',')]
                # Avoid duplicates (case-insensitive)
                existing_upper = [c.upper() for c in auto_icp['serviceable_geography']['countries']]
                for country in new_countries:
                    if country not in existing_upper:
                        auto_icp['serviceable_geography']['countries'].append(country)
                auto_icp['serviceable_geography']['scope'] = 'custom'
                self.logger.info(f" Added countries: {', '.join(new_countries)}")
        
        elif country_action == 'E':
            if current_countries:
                remove_countries = input("   Remove which countries? (e.g., USA, Canada) [Enter to skip]: ").strip()
                if remove_countries:
                    to_remove = [c.strip().upper() for c in remove_countries.split(',')]
                    auto_icp['serviceable_geography']['countries'] = [
                        c for c in auto_icp['serviceable_geography']['countries'] 
                        if c.upper() not in to_remove
                    ]
                    self.logger.info(f" Removed countries: {', '.join(to_remove)}")
            
            add_countries = input("   Add which countries? (e.g., India, UK) [Enter to skip]: ").strip()
            if add_countries:
                new_countries = [c.strip().upper() for c in add_countries.split(',')]
                existing_upper = [c.upper() for c in auto_icp['serviceable_geography']['countries']]
                for country in new_countries:
                    if country not in existing_upper:
                        auto_icp['serviceable_geography']['countries'].append(country)
                auto_icp['serviceable_geography']['scope'] = 'custom'
                self.logger.info(f" Added countries: {', '.join(new_countries)}")
        
        # ==========================================
        # REGIONS/STATES - ALWAYS Edit Mode
        # ==========================================
        print(f"\n Current regions/states: {', '.join(current_regions) if current_regions else '(none)'}")
        region_action = input("   [K]eep all / [R]eplace all / [A]dd only / [E]dit (add/remove): ").strip().upper()
        
        if region_action == 'R':
            new_regions = input("   Enter new regions (e.g., TX, FL, Delhi, Maharashtra): ").strip()
            if new_regions:
                auto_icp['serviceable_geography']['states_or_regions'] = [r.strip() for r in new_regions.split(',')]
                auto_icp['serviceable_geography']['scope'] = 'custom'
                self.logger.info(f" Replaced regions: {', '.join(auto_icp['serviceable_geography']['states_or_regions'])}")
        
        elif region_action == 'A':
            add_regions = input("   Add which regions? (e.g., TX, FL, Mumbai): ").strip()
            if add_regions:
                new_regions = [r.strip() for r in add_regions.split(',')]
                existing_lower = [r.lower() for r in auto_icp['serviceable_geography']['states_or_regions']]
                for region in new_regions:
                    if region.lower() not in existing_lower:
                        auto_icp['serviceable_geography']['states_or_regions'].append(region)
                auto_icp['serviceable_geography']['scope'] = 'custom'
                self.logger.info(f" Added regions: {', '.join(new_regions)}")
        
        elif region_action == 'E':
            if current_regions:
                remove_regions = input("   Remove which regions? (e.g., CA, NV) [Enter to skip]: ").strip()
                if remove_regions:
                    to_remove = [r.strip().lower() for r in remove_regions.split(',')]
                    auto_icp['serviceable_geography']['states_or_regions'] = [
                        r for r in auto_icp['serviceable_geography']['states_or_regions'] 
                        if r.lower() not in to_remove
                    ]
                    self.logger.info(f" Removed regions: {', '.join(remove_regions.split(','))}")
            
            add_regions = input("   Add which regions? (e.g., TX, FL, Mumbai) [Enter to skip]: ").strip()
            if add_regions:
                new_regions = [r.strip() for r in add_regions.split(',')]
                existing_lower = [r.lower() for r in auto_icp['serviceable_geography']['states_or_regions']]
                for region in new_regions:
                    if region.lower() not in existing_lower:
                        auto_icp['serviceable_geography']['states_or_regions'].append(region)
                auto_icp['serviceable_geography']['scope'] = 'custom'
                self.logger.info(f" Added regions: {', '.join(new_regions)}")
        
        # Update geography notes
        if auto_icp['serviceable_geography'].get('countries') or auto_icp['serviceable_geography'].get('states_or_regions'):
            notes_parts = []
            if auto_icp['serviceable_geography'].get('countries'):
                notes_parts.append(f"Countries: {', '.join(auto_icp['serviceable_geography']['countries'])}")
            if auto_icp['serviceable_geography'].get('states_or_regions'):
                notes_parts.append(f"Regions: {', '.join(auto_icp['serviceable_geography']['states_or_regions'])}")
            auto_icp['serviceable_geography']['notes'] = " | ".join(notes_parts)
        
        # ==========================================
        # CUSTOMER INDUSTRY - ALWAYS Edit Mode
        # ==========================================
        current_industries = auto_icp.get('customer_industry', '')
        print(f"\n Current industries: {current_industries if current_industries else '(none)'}")
        industry_action = input("   [K]eep all / [R]eplace all / [A]dd only: ").strip().upper()
        
        if industry_action == 'R':
            new_industries = input("   Enter new industries (e.g., Retail, Healthcare): ").strip()
            if new_industries:
                auto_icp['customer_industry'] = new_industries
                self.logger.info(f" Replaced industries: {new_industries}")
        
        elif industry_action == 'A':
            add_industries = input("   Add which industries? (e.g., Manufacturing, Tech): ").strip()
            if add_industries:
                if current_industries:
                    # Check for duplicates (case-insensitive)
                    existing_lower = [i.strip().lower() for i in auto_icp['customer_industry'].split(',')]
                    new_to_add = []
                    for industry in add_industries.split(','):
                        industry_clean = industry.strip()
                        if industry_clean.lower() not in existing_lower:
                            new_to_add.append(industry_clean)
                    
                    if new_to_add:
                        auto_icp['customer_industry'] += f", {', '.join(new_to_add)}"
                        self.logger.info(f" Added industries: {', '.join(new_to_add)}")
                    else:
                        self.logger.info(" No new industries added (duplicates skipped)")
                else:
                    auto_icp['customer_industry'] = add_industries
                    self.logger.info(f" Added industries: {add_industries}")
        
        # ==========================================
        # TARGET BUYERS - ALWAYS Edit Mode
        # ==========================================
        current_buyers = auto_icp.get('target_buyers', [])
        print(f"\n Current target buyers: {', '.join(current_buyers) if current_buyers else '(none)'}")
        buyer_action = input("   [K]eep all / [R]eplace all / [A]dd only / [E]dit (add/remove): ").strip().upper()
        
        if buyer_action == 'R':
            new_buyers = input("   Enter new target buyers (e.g., CTO, VP Operations): ").strip()
            if new_buyers:
                auto_icp['target_buyers'] = [b.strip() for b in new_buyers.split(',')]
                self.logger.info(f" Replaced target buyers: {', '.join(auto_icp['target_buyers'])}")
        
        elif buyer_action == 'A':
            add_buyers = input("   Add which buyers? (e.g., Director, VP): ").strip()
            if add_buyers:
                new_buyers = [b.strip() for b in add_buyers.split(',')]
                existing_lower = [b.lower() for b in auto_icp['target_buyers']]
                for buyer in new_buyers:
                    if buyer.lower() not in existing_lower:
                        auto_icp['target_buyers'].append(buyer)
                self.logger.info(f" Added buyers: {', '.join(new_buyers)}")
        
        elif buyer_action == 'E':
            if current_buyers:
                remove_buyers = input("   Remove which buyers? (e.g., CEO, Manager) [Enter to skip]: ").strip()
                if remove_buyers:
                    to_remove = [b.strip().lower() for b in remove_buyers.split(',')]
                    auto_icp['target_buyers'] = [
                        b for b in auto_icp['target_buyers'] 
                        if b.lower() not in to_remove
                    ]
                    self.logger.info(f" Removed buyers: {', '.join(remove_buyers.split(','))}")
            
            add_buyers = input("   Add which buyers? (e.g., Director, VP) [Enter to skip]: ").strip()
            if add_buyers:
                new_buyers = [b.strip() for b in add_buyers.split(',')]
                existing_lower = [b.lower() for b in auto_icp['target_buyers']]
                for buyer in new_buyers:
                    if buyer.lower() not in existing_lower:
                        auto_icp['target_buyers'].append(buyer)
                self.logger.info(f" Added buyers: {', '.join(new_buyers)}")

        # ==========================================
        # v2.0: SELLER BUSINESS TYPE - Edit Option
        # ==========================================
        current_seller_type = auto_icp.get('seller_business_type', 'unknown')
        print(f"\n Current seller type: {current_seller_type}")
        print("   Options: physical_service | software_saas | b2b_supplier | engineering_services | consulting")
        seller_type_action = input("   [K]eep / [C]hange: ").strip().upper()

        if seller_type_action == 'C':
            print("   1. physical_service (construction, cleaning, maintenance)")
            print("   2. software_saas (tools, platforms, analytics)")
            print("   3. b2b_supplier (parts, components, materials)")
            print("   4. engineering_services (R&D, embedded software, design)")
            print("   5. consulting (strategy, advisory)")
            type_choice = input("   Enter choice [1-5]: ").strip()
            type_map = {
                "1": "physical_service",
                "2": "software_saas",
                "3": "b2b_supplier",
                "4": "engineering_services",
                "5": "consulting"
            }
            if type_choice in type_map:
                auto_icp['seller_business_type'] = type_map[type_choice]
                self.logger.info(f" Changed seller type to: {auto_icp['seller_business_type']}")

        # ==========================================
        # v2.0: AVOID COMPANY TYPES - Edit Option
        # ==========================================
        current_avoid = auto_icp.get('avoid_company_types', [])
        print(f"\n Companies to avoid: {', '.join(current_avoid) if current_avoid else '(none)'}")
        avoid_action = input("   [K]eep all / [R]eplace all / [A]dd only: ").strip().upper()

        if avoid_action == 'R':
            new_avoid = input("   Enter companies to avoid (e.g., Competitors, Consulting firms): ").strip()
            if new_avoid:
                auto_icp['avoid_company_types'] = [a.strip() for a in new_avoid.split(',')]
                self.logger.info(f" Replaced avoid list: {', '.join(auto_icp['avoid_company_types'])}")

        elif avoid_action == 'A':
            add_avoid = input("   Add which types to avoid? (e.g., Software vendors, Agencies): ").strip()
            if add_avoid:
                new_avoid = [a.strip() for a in add_avoid.split(',')]
                existing_lower = [a.lower() for a in auto_icp.get('avoid_company_types', [])]
                for avoid in new_avoid:
                    if avoid.lower() not in existing_lower:
                        if 'avoid_company_types' not in auto_icp:
                            auto_icp['avoid_company_types'] = []
                        auto_icp['avoid_company_types'].append(avoid)
                self.logger.info(f" Added to avoid list: {', '.join(new_avoid)}")

        return auto_icp
    # ----------------------------------------------------------
    # Prompt Builder - CUSTOMER FOCUSED + GEOGRAPHIC SCOPE
    # ----------------------------------------------------------

    def _build_customer_focused_prompt(self, content: str) -> str:
        """
        Build prompt that focuses on WHO would BUY, not what the company does.
        v2.0: Added business-type-aware customer identification logic.

        CRITICAL: Different business types require different customer identification!
        """
        return f"""
You are a B2B sales research expert. Your job is to identify WHO would BUY this company's product/service.

=============================================================================
STEP 1: IDENTIFY THE SELLER'S BUSINESS TYPE (Do this FIRST!)
=============================================================================

Before identifying customers, classify this company into ONE of these categories:

A. PHYSICAL SERVICE PROVIDER (construction, cleaning, maintenance, logistics)
   → Customers = Companies that COMMISSION/ORDER these services
   → NOT companies that already have facilities (they have their own maintenance)

B. SOFTWARE/SAAS COMPANY (tools, platforms, analytics)
   → Customers = Companies that have the PROBLEM this software solves
   → NOT competitors or similar software companies

C. B2B SUPPLIER (parts, components, raw materials)
   → Customers = Companies that INCORPORATE these into their products
   → NOT distributors or resellers (unless that's the model)

D. ENGINEERING/TECHNOLOGY SERVICES (embedded software, R&D, design)
   → Customers = Companies that OUTSOURCE this capability
   → NOT companies that do this in-house (they're competitors)

E. CONSULTING/ADVISORY (strategy, management, transformation)
   → Customers = Companies undergoing CHANGE who need expert guidance
   → NOT other consulting firms

=============================================================================
STEP 2: APPLY THE CORRECT CUSTOMER IDENTIFICATION LOGIC
=============================================================================

███ FOR PHYSICAL SERVICE PROVIDERS (Construction, Maintenance, etc.) ███

CRITICAL DISTINCTION - "Having facilities" vs "Commissioning new work":

WRONG CUSTOMERS (they already have facilities + maintenance teams):
- Existing manufacturers with factories (Ford, Boeing, P&G)
- Established retailers with stores (Walmart, Target)
- These companies have in-house facility management!

RIGHT CUSTOMERS (they actively commission NEW construction/work):
- Real estate DEVELOPERS building new properties (Peebles Corp, Hines, Brookfield)
- Retail chains EXPANDING to new locations (Starbucks opening new stores)
- Healthcare systems BUILDING new facilities (HCA building new hospitals)
- Hotel chains DEVELOPING new properties (Marriott expansion projects)
- Companies RELOCATING or RENOVATING headquarters

KEY INSIGHT: Look for companies in GROWTH/EXPANSION mode, not steady-state operations.

███ FOR SOFTWARE/SAAS COMPANIES ███

WRONG CUSTOMERS:
- Other software companies (they're competitors or don't need your tool)
- Generic "tech companies" (too vague)

RIGHT CUSTOMERS:
- Companies with the SPECIFIC PROBLEM your software solves
- Example: Jungle Scout → Brands selling on Amazon (not e-commerce platforms)
- Example: Slack → Companies needing team collaboration (not software vendors)

███ FOR ENGINEERING/TECHNOLOGY SERVICES (like KPIT) ███

WRONG CUSTOMERS:
- Companies that do the SAME thing (they're competitors!)
- Example: If you do automotive software → Bosch, Continental are COMPETITORS
- Generic "automotive companies"

RIGHT CUSTOMERS:
- Companies that NEED this service but don't have in-house capability
- OEMs who OUTSOURCE software development
- Companies TRANSITIONING to new technology (EV, autonomous)
- Example: KPIT → Car OEMs needing ADAS software (Honda, GM, Ford)
- NOT → Bosch, Continental, Aptiv (they SELL similar services = COMPETITORS)

███ FOR B2B SUPPLIERS ███

WRONG CUSTOMERS:
- Distributors (unless that's your go-to-market)
- End consumers

RIGHT CUSTOMERS:
- Manufacturers who INCORPORATE your products
- Companies in industries that USE your materials

=============================================================================
STEP 3: EXAMPLES BY BUSINESS TYPE
=============================================================================

EXAMPLE 1: Construction Company (SBAR Construction)
Seller Type: Physical Service Provider

WRONG ICP:
{{
  "customer_industry": "Manufacturing facilities, Industrial companies, Commercial real estate"
  // WRONG! These companies HAVE facilities, they don't commission new construction
}}

CORRECT ICP:
{{
  "what_they_sell": "Commercial construction, tenant improvements, and renovation services",
  "customer_industry": "Commercial real estate developers, Retail chains expanding locations, Healthcare systems building new facilities, Hotel/hospitality companies developing new properties, Corporate headquarters relocations",
  "ideal_customer_characteristics": [
    "Actively developing or expanding real estate portfolio",
    "Has announced new location openings or expansions",
    "Undergoing corporate relocation or renovation",
    "Growing company needing new/larger facilities"
  ],
  "avoid_company_types": [
    "Other construction companies (competitors)",
    "Architecture/engineering firms (partners, not customers)",
    "Manufacturers with existing facilities (have in-house maintenance)",
    "Property management companies (maintain, don't build)"
  ]
}}

EXAMPLE 2: Automotive Software Company (KPIT Technologies)
Seller Type: Engineering/Technology Services

WRONG ICP:
{{
  "customer_industry": "Automotive companies, Mobility companies"
  // WRONG! Too vague and would include competitors
}}

CORRECT ICP:
{{
  "what_they_sell": "Automotive software development, ADAS, autonomous driving, EV solutions",
  "customer_industry": "Automotive OEMs (car manufacturers), Electric vehicle startups, Commercial vehicle manufacturers, Automotive Tier-1 suppliers needing software expertise",
  "ideal_customer_characteristics": [
    "Developing electric or autonomous vehicles",
    "Needs to OUTSOURCE software development",
    "Transitioning from ICE to EV platforms",
    "Does NOT have large in-house software team"
  ],
  "avoid_company_types": [
    "Automotive software companies (COMPETITORS: Bosch, Continental, Aptiv, ZF)",
    "Tier-1 suppliers with own software divisions",
    "IT services companies",
    "Automotive consulting firms"
  ]
}}

EXAMPLE 3: Amazon Seller Tools (Jungle Scout)
Seller Type: Software/SaaS

CORRECT ICP:
{{
  "what_they_sell": "Amazon seller optimization and analytics software",
  "customer_industry": "Consumer product brands selling on Amazon, DTC brands expanding to Amazon, Private label sellers, Retail brands with Amazon storefronts",
  "ideal_customer_characteristics": [
    "Actively sells products on Amazon marketplace",
    "Manages multiple SKUs on Amazon",
    "Wants to improve Amazon search rankings and sales",
    "Annual Amazon revenue $500K+"
  ],
  "avoid_company_types": [
    "E-commerce platforms (Shopify, BigCommerce - not sellers)",
    "Amazon aggregators (they acquire brands, different model)",
    "Marketing agencies (they serve sellers, not sell on Amazon)",
    "Amazon itself"
  ]
}}

EXAMPLE 4: Team Collaboration Software (Slack)
Seller Type: Software/SaaS

CORRECT ICP:
{{
  "what_they_sell": "Team messaging and collaboration platform",
  "customer_industry": "Technology companies, Professional services firms, Media companies, Remote-first organizations, Fast-growing startups",
  "ideal_customer_characteristics": [
    "Has distributed or remote teams",
    "Values real-time communication",
    "Uses multiple SaaS tools (needs integrations)",
    "Growing headcount requiring better coordination"
  ],
  "avoid_company_types": [
    "Other collaboration software companies (Microsoft, Google - competitors)",
    "Very small businesses (<10 employees)",
    "Heavily regulated industries requiring on-premise (some banks)"
  ]
}}

=============================================================================
WEBSITE CONTENT TO ANALYZE:
=============================================================================
{content[:5000]}

=============================================================================
OUTPUT FORMAT - Return ONLY this JSON:
=============================================================================

{{
  "seller_business_type": "physical_service | software_saas | b2b_supplier | engineering_services | consulting",
  "what_they_sell": "Specific product/service description",
  "customer_industry": "Specific types of companies that would BUY (use guidance above)",
  "customer_company_size": "Size of buyer companies",
  "target_buyers": ["Job title 1", "Job title 2", "Job title 3"],
  "pain_points_solved": ["Problem 1", "Problem 2", "Problem 3"],
  "ideal_customer_characteristics": [
    "Trait that makes them a BUYER (active need)",
    "Trait that makes them a BUYER",
    "Trait that makes them a BUYER"
  ],
  "customer_geography": "Where customers are located",
  "serviceable_geography": {{
    "scope": "regional | national | global | unclear",
    "countries": ["USA"],
    "states_or_regions": ["CA", "TX"] or [],
    "notes": "Geographic limitation details"
  }},
  "customer_business_model": "developer | expanding_retailer | outsourcing_oem | end_user_brand | other",
  "avoid_company_types": [
    "COMPETITORS (companies selling similar products/services)",
    "Companies that do this IN-HOUSE",
    "Wrong industry/model companies",
    "Service providers to the industry (not buyers)"
  ]
}}

=============================================================================
CRITICAL VALIDATION CHECKLIST (Before returning):
=============================================================================

☐ Did I identify the SELLER'S business type first?
☐ For SERVICE companies: Am I targeting companies that COMMISSION work, not those that HAVE facilities?
☐ For SOFTWARE companies: Am I targeting companies with the PROBLEM, not competitors?
☐ For ENGINEERING services: Did I EXCLUDE companies that do the same thing (competitors)?
☐ Is customer_industry SPECIFIC enough? (Not just "automotive" or "retail")
☐ Does avoid_company_types include COMPETITORS?
☐ Would these companies actually SPEND MONEY on this product/service?

Return ONLY the JSON, no other text.
"""

    # ----------------------------------------------------------
    # JSON Parsing
    # ----------------------------------------------------------

    def _parse_icp_json(self, text: str) -> Dict[str, Any]:
        """Extract and validate customer-focused JSON from LLM response."""
        try:
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")

            json_str = text[start:end]
            icp = json.loads(json_str)

            # Required fields for new schema
            required_fields = [
                "what_they_sell",
                "customer_industry",
                "customer_company_size",
                "target_buyers",
                "pain_points_solved",
                "ideal_customer_characteristics"
            ]

            missing = [f for f in required_fields if f not in icp]
            if missing:
                self.logger.warning(f"Missing fields: {missing}")

                # Add defaults for missing fields
                if "what_they_sell" not in icp:
                    icp["what_they_sell"] = "Unknown product/service"
                if "customer_industry" not in icp:
                    icp["customer_industry"] = "Various industries"
                if "customer_company_size" not in icp:
                    icp["customer_company_size"] = "SMB to Enterprise"
                if "pain_points_solved" not in icp:
                    icp["pain_points_solved"] = []
                if "ideal_customer_characteristics" not in icp:
                    icp["ideal_customer_characteristics"] = []

            # v2.0: Add seller_business_type with default
            if "seller_business_type" not in icp:
                icp["seller_business_type"] = "unknown"
            else:
                # Validate seller_business_type
                valid_types = ["physical_service", "software_saas", "b2b_supplier",
                               "engineering_services", "consulting", "unknown"]
                if icp["seller_business_type"] not in valid_types:
                    self.logger.warning(f"Unknown seller_business_type: {icp['seller_business_type']}")

            # Validate list fields
            list_fields = ["target_buyers", "pain_points_solved", "ideal_customer_characteristics", "avoid_company_types"]
            for field in list_fields:
                if field in icp and not isinstance(icp[field], list):
                    icp[field] = [icp[field]] if icp[field] else []

            # Add optional fields with defaults
            if "customer_geography" not in icp:
                icp["customer_geography"] = "Global"

            # Add serviceable geography defaults
            if "serviceable_geography" not in icp:
                icp["serviceable_geography"] = {
                    "scope": "unclear",
                    "countries": [],
                    "states_or_regions": [],
                    "notes": "No geographic information detected"
                }
            else:
                # Validate serviceable_geography structure
                geo = icp["serviceable_geography"]
                if not isinstance(geo, dict):
                    icp["serviceable_geography"] = {
                        "scope": "unclear",
                        "countries": [],
                        "states_or_regions": [],
                        "notes": "Invalid format"
                    }
                else:
                    # Ensure all required sub-fields exist
                    if "scope" not in geo:
                        geo["scope"] = "unclear"
                    if "countries" not in geo:
                        geo["countries"] = []
                    if "states_or_regions" not in geo:
                        geo["states_or_regions"] = []
                    if "notes" not in geo:
                        geo["notes"] = ""

                    # Validate scope value
                    valid_scopes = ["regional", "national", "global", "unclear"]
                    if geo["scope"] not in valid_scopes:
                        self.logger.warning(f"Invalid scope '{geo['scope']}', defaulting to 'unclear'")
                        geo["scope"] = "unclear"

                    # Ensure arrays are actually arrays
                    if not isinstance(geo["countries"], list):
                        geo["countries"] = []
                    if not isinstance(geo["states_or_regions"], list):
                        geo["states_or_regions"] = []

            if "avoid_company_types" not in icp:
                icp["avoid_company_types"] = []

            return icp

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON from LLM: {text[:500]}")
            raise ValueError(f"Could not parse JSON: {e}")
        except Exception as e:
            self.logger.error(f"JSON parsing error: {e}")
            raise

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------

    def _validate_customer_focus(self, icp: Dict[str, Any]):
        """
        Validate that ICP is customer-focused, not company-focused.
        v2.0: Added business-type-aware validation for correct customer identification.
        """
        seller_type = icp.get("seller_business_type", "unknown")
        customer_industry = icp.get("customer_industry", "").lower()
        avoid_types = icp.get("avoid_company_types", [])

        self.logger.info(f"   Seller business type: {seller_type}")

        # Check if we got meaningful customer characteristics
        if not icp.get("ideal_customer_characteristics"):
            self.logger.warning("No customer characteristics defined - ICP may be too generic")

        # Ensure we have specific buyer info
        if not icp.get("target_buyers") or len(icp["target_buyers"]) == 0:
            self.logger.warning("No target buyers defined")

        # v2.0: Business-type-specific validation
        if seller_type == "physical_service":
            # For construction/maintenance - check for ACTIVE NEED indicators
            active_need_keywords = ["developing", "expanding", "building", "growing", "opening", "relocating"]
            has_active_need = any(kw in customer_industry for kw in active_need_keywords)

            # Check for common mistakes
            passive_keywords = ["manufacturing", "industrial facilities", "existing facilities"]
            has_passive_mistake = any(kw in customer_industry for kw in passive_keywords)

            if has_passive_mistake and not has_active_need:
                self.logger.warning(
                    "  POTENTIAL ICP ISSUE: For physical services (construction/maintenance), "
                    "customers should be companies COMMISSIONING work, not those that HAVE facilities. "
                    f"Current: '{customer_industry[:100]}...'"
                )
                self.logger.warning(
                    "   Better targets: Real estate developers, Retail chains EXPANDING, "
                    "Healthcare systems BUILDING new facilities"
                )

        elif seller_type == "engineering_services":
            # For engineering services - check competitor exclusion
            competitor_keywords = ["competitor", "similar service", "same type"]
            has_competitor_exclusion = any(kw in str(avoid_types).lower() for kw in competitor_keywords)

            if not has_competitor_exclusion:
                self.logger.warning(
                    "  POTENTIAL ICP ISSUE: For engineering services, "
                    "avoid_company_types should explicitly list COMPETITORS. "
                    "Companies that provide similar services are NOT customers!"
                )

        elif seller_type == "software_saas":
            # For SaaS - check for problem-based targeting
            problem_keywords = ["need", "problem", "challenge", "pain", "struggle"]
            characteristics = str(icp.get("ideal_customer_characteristics", [])).lower()
            has_problem_focus = any(kw in characteristics for kw in problem_keywords)

            if not has_problem_focus:
                self.logger.warning(
                    "  POTENTIAL ICP ISSUE: For software/SaaS, "
                    "ideal_customer_characteristics should describe the PROBLEM they have. "
                    "Target companies with specific pain points, not just industries."
                )

        # Warn if customer_industry is too vague
        vague_industries = ["software", "technology", "services", "business", "companies"]
        if any(vague == customer_industry.strip() for vague in vague_industries):
            self.logger.warning(
                f"Customer industry is too vague: '{customer_industry}'. "
                "Be more specific about buyer types."
            )

        # Check if avoid_company_types is populated (should always have competitors)
        if not avoid_types or len(avoid_types) == 0:
            self.logger.warning(
                "  avoid_company_types is empty! "
                "You should always exclude competitors and wrong-fit companies."
            )
        
        # Check if pain points are defined
        if not icp.get("pain_points_solved") or len(icp["pain_points_solved"]) == 0:
            self.logger.warning("No pain points defined - prospect finder may struggle")
        
        # NEW: Validate serviceable geography
        geo = icp.get("serviceable_geography", {})
        scope = geo.get("scope", "unclear")
        
        if scope == "regional":
            regions = geo.get("states_or_regions", [])
            if not regions:
                self.logger.warning(
                    "Geographic scope is 'regional' but no specific regions defined. "
                    "Prospect filtering may not work as expected."
                )
            else:
                self.logger.info(f"Regional scope detected: {len(regions)} regions specified")
        
        elif scope == "unclear":
            self.logger.info(
                "Geographic scope unclear - will accept prospects from all locations. "
                "This may result in leads outside serviceable area."
            )

    # ----------------------------------------------------------
    # Backward Compatibility Helper
    # ----------------------------------------------------------
    
    def get_legacy_format(self, icp: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert new customer-focused format to old format for backward compatibility.
        Only use this if you need to support old code.
        """
        return {
            "industry": icp.get("customer_industry", ""),
            "target_buyers": icp.get("target_buyers", []),
            "company_size": icp.get("customer_company_size", ""),
            "geo": icp.get("customer_geography", "Global"),
            "keywords_include": (
                [icp.get("what_they_sell", "")] + 
                icp.get("ideal_customer_characteristics", [])[:3]
            ),
            "keywords_exclude": icp.get("avoid_company_types", [])
        }
    
    # ----------------------------------------------------------
    # Geographic Scope Helper
    # ----------------------------------------------------------
    
    def get_geographic_summary(self, icp: Dict[str, Any]) -> str:
        """
        Get human-readable summary of geographic scope.
        Useful for logging and user-facing displays.
        """
        geo = icp.get("serviceable_geography", {})
        scope = geo.get("scope", "unclear")
        
        if scope == "global":
            return "Global service area - no geographic restrictions"
        
        elif scope == "national":
            countries = geo.get("countries", [])
            if countries:
                return f"National service in: {', '.join(countries)}"
            return "National service area"
        
        elif scope == "regional":
            regions = geo.get("states_or_regions", [])
            countries = geo.get("countries", [])
            
            parts = []
            if countries:
                parts.append(f"Countries: {', '.join(countries)}")
            if regions:
                if len(regions) <= 5:
                    parts.append(f"Regions: {', '.join(regions)}")
                else:
                    parts.append(f"Regions: {', '.join(regions[:5])} and {len(regions)-5} more")
            
            if parts:
                return f"Regional service - {' | '.join(parts)}"
            return "Regional service area (specific regions not identified)"
        
        else:
            return "Geographic scope unclear - no filtering applied"


# --------------------------------------------------------------
# Integration Test
# --------------------------------------------------------------
if __name__ == "__main__":
    print("\n Testing Customer-Focused ICP Generator (with Geographic Scope)")
    print("="*70 + "\n")

    from src.scraper.website_scraper import WebsiteScraper

    scraper = WebsiteScraper()
    icp_gen = ICPGenerator()

    # Test with Jungle Scout
    url = input("Enter website URL (or press Enter for SBAR Construction): ").strip()
    if not url:
        url = "https://sbarconstruction.com"
    
    print(f"\n Scraping: {url}")
    result = scraper.scrape_website(url)

    content = result.get("combined_text", "")
    if not content or len(content) < 200:
        print("\n Not enough content scraped.")
        exit()

    print(f" Scraped {len(content):,} characters\n")
    print(" Generating customer-focused ICP with geographic scope...\n")
    
    icp = icp_gen.generate_icp(content)
    
    print("\n" + "="*70)
    print(" CUSTOMER-FOCUSED ICP RESULT:")
    print("="*70 + "\n")
    print(json.dumps(icp, indent=2))

    icp = icp_gen.get_user_overrides(icp)
    
    print("\n" + "="*70)
    print(" FINAL CUSTOMIZED ICP:")
    print("="*70 + "\n")
    print(json.dumps(icp, indent=2))
    
    print("\n" + "="*70)
    
   