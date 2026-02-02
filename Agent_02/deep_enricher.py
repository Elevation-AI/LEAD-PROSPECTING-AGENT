"""
Deep Enricher - Orchestrates all enrichment steps
==================================================
Combines LinkedIn scraping + Tech stack detection
"""

import sys
import os
from typing import List, Dict
import time

# Get the directory where main.py is located (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (lead-prospecting-agent)
project_root = os.path.dirname(current_dir)

# Add the project root to sys.path so 'src' can be found
if project_root not in sys.path:
    sys.path.insert(0, project_root)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.helpers import setup_logger
from linkedin_scraper import LinkedInScraper
from tech_stack_detector import TechStackDetector


class DeepEnricher:
    """
    Main orchestrator for Agent 02
    
    Takes basic contacts from Agent 01 and enriches them with:
    - LinkedIn data (bio, tenure, location)
    - Tech stack (company technologies)
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.linkedin_scraper = LinkedInScraper()
        self.tech_detector = TechStackDetector()
        
        # Cache for tech stacks (avoid re-scraping same company)
        self.tech_cache = {}
    
    def _get_unique_companies(self, contacts: List[Dict]) -> List[str]:
        """Extract unique company domains from contact list"""
        domains = set()
        for contact in contacts:
            domain = contact.get('domain')
            if domain:
                domains.add(domain)
        return list(domains)
    
    def _enrich_company_tech(self, domain: str) -> Dict:
        """
        Get tech stack for a company (with caching)
        """
        # Check cache first
        if domain in self.tech_cache:
            self.logger.info(f" Using cached tech for {domain}")
            return self.tech_cache[domain]
        
        # Detect tech stack
        self.logger.info(f" Detecting tech for {domain}")
        tech_data = self.tech_detector.detect(f"https://{domain}")
        
        # Cache result
        if tech_data:
            self.tech_cache[domain] = tech_data
            return tech_data
        
        # Return empty if failed
        return {
            "domain": domain,
            "tech_stack": [],
            "categories": {}
        }
    
    def _enrich_contact_linkedin(self, contact: Dict) -> Dict:
        """
        Enrich single contact with LinkedIn data
        """
        linkedin_url = contact.get('linkedin_url')
        
        if not linkedin_url:
            self.logger.warning(f" No LinkedIn URL for {contact.get('name')}")
            return {}
        
        # Scrape LinkedIn
        self.logger.info(f" Scraping LinkedIn for {contact.get('name')}")
        linkedin_data = self.linkedin_scraper.scrape_profile(linkedin_url)
        
        return linkedin_data or {}
    
    def enrich(self, contacts: List[Dict]) -> List[Dict]:
        """
        Main enrichment method
        
        Args:
            contacts: List of contacts from Agent 01
            
        Returns:
            List of enriched contacts
        """
        self.logger.info(f" Starting deep enrichment for {len(contacts)} contacts")
        
        # Step 1: Get unique companies
        unique_domains = self._get_unique_companies(contacts)
        self.logger.info(f" Found {len(unique_domains)} unique companies")
        
        # Step 2: Enrich all companies (tech stack)
        self.logger.info(" Enriching company tech stacks...")
        for domain in unique_domains:
            self._enrich_company_tech(domain)
            time.sleep(2)  # Rate limiting
        
        # Step 3: Enrich each contact
        self.logger.info(" Enriching individual contacts...")
        enriched_contacts = []
        
        for i, contact in enumerate(contacts, 1):
            self.logger.info(f" Processing contact {i}/{len(contacts)}: {contact.get('name')}")
            
            # Start with original contact data
            enriched = contact.copy()
            
            # Add LinkedIn data
            try:
                linkedin_data = self._enrich_contact_linkedin(contact)
                enriched.update(linkedin_data)
            except Exception as e:
                self.logger.error(f" LinkedIn enrichment failed: {e}")
            
            # Add company tech stack + company summary
            domain = contact.get('domain')
            if domain and domain in self.tech_cache:
                tech_data = self.tech_cache[domain]
                enriched['company_tech_stack'] = tech_data.get('tech_stack', [])
                enriched['company_description'] = tech_data.get('categories', {})
                enriched['about_company'] = tech_data.get('company_summary', 'N/A')
            
            enriched_contacts.append(enriched)
            
            # Rate limiting
            time.sleep(3)
        
        self.logger.info(f" Enrichment complete! {len(enriched_contacts)} contacts enriched")
        
        return enriched_contacts


# --------------------------------------------------------
# TEST DRIVER
# --------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔧 Deep Enricher Test")
    print("="*70)
    
    # Sample Agent 01 output (2 contacts from same company)
    agent01_output = [
    
        {
            "name": "Patrick Joyce",
            "title": "VP of Engineering",
            "email": "patrick@greenhouse.io",
            "email_verified": True,
            "linkedin_url": "http://www.linkedin.com/in/patricktobinjoyce",
            "company": "Greenhouse",
            "domain": "greenhouse.io"
        },
            {
        "name": "Kaz Nejatian",
        "title": "VP of Product",
        "email": "kaz@shopify.com",
        "email_verified": True,
        "linkedin_url": "https://www.linkedin.com/in/kaz",
        "company": "Shopify",
        "domain": "shopify.com"
    }
    ]
    
    # Run deep enrichment
    enricher = DeepEnricher()
    enriched = enricher.enrich(agent01_output)
    
    # Display results
    print("\n ENRICHED RESULTS:")
    print("="*70)
    
    for contact in enriched:
        print(f"\n {contact['name']}")
        print(f"   Title: {contact['title']}")
        print(f"   Email: {contact['email']}")
        print(f"   Bio: {contact.get('bio_snippet', 'N/A')[:50]}...")
        print(f"   Time in Role: {contact.get('time_in_role', 'N/A')}")
        print(f"   Location: {contact.get('location', 'N/A')}")
        print(f"   Company Tech: {', '.join(contact.get('company_tech_stack', [])[:3])}")
    
    print("\n" + "="*70)