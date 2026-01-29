import requests
import time
import sys
import os
from typing import List, Dict, Any

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.helpers import setup_logger
from config.settings import settings


class ApolloEnricher:
    """
    PRODUCTION-GRADE Apollo Contact Enricher with Email Unlock
    -----------------------------------------------------------
    ✔ Works with header authentication (X-Api-Key)
    ✔ Uses /v1/mixed_people/api_search for finding contacts
    ✔ Uses /v1/people/match for unlocking emails AND getting full profile data
    ✔ Gracefully handles rate limits and errors
    ✔ Clean output structure
    
    UPDATED: Jan 2026 - Fixed to extract LinkedIn URL and location from enrichment response
    """

    def __init__(self, unlock_emails: bool = False):
        """
        Args:
            unlock_emails: If True, will spend Apollo credits to unlock emails
                          If False, will return placeholder emails (saves credits)
        """
        self.logger = setup_logger(__name__)
        self.api_key = settings.APOLLO_API_KEY
        self.base_url = "https://api.apollo.io/api/v1"
        self.unlock_emails = unlock_emails  # Control email unlocking
        
        # Track credit usage
        self.credits_used = 0

        if not self.api_key:
            raise ValueError(" ERROR: Apollo API key missing in .env file")
        
        if self.unlock_emails:
            self.logger.warning("  Email unlocking ENABLED - This will use Apollo credits!")
        else:
            self.logger.info("  Email unlocking DISABLED - Emails will be placeholders (saves credits)")

    # --------------------------------------------------------
    # HEADERS
    # --------------------------------------------------------
    def _headers(self):
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "LeadProspectingMVP/1.0"
        }

    # --------------------------------------------------------
    # Build Apollo Search Request
    # --------------------------------------------------------
    def _build_search_payload(self, domain: str, target_titles: List[str]):
        """Build API request for mixed_people search"""
        return {
            "q_organization_domains": domain,
            "page": 1,
            "per_page": 5,
            "person_titles": target_titles
        }

    # --------------------------------------------------------
    # Unlock Email AND Get Full Profile Data (COSTS CREDITS)
    # --------------------------------------------------------
    def _enrich_person(self, person_id: str) -> Dict[str, Any]:
        """
        Enrich a person using Apollo credits to get:
        - Email (unlocked)
        - LinkedIn URL
        - Location (city, state, country)
        
        NOTE: Phone number reveal requires webhook_url, so we skip it
        
        Args:
            person_id: Apollo person ID
            
        Returns:
            Dict with enriched data or None if failed
        """
        if not self.unlock_emails:
            return None  # Skip if unlocking is disabled
        
        try:
            # NOTE: Do NOT include reveal_phone_number - it requires a webhook_url
            payload = {
                "id": person_id,
                "reveal_personal_emails": True  # THIS COSTS CREDITS
            }
            
            response = requests.post(
                f"{self.base_url}/people/match",
                headers=self._headers(),
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.credits_used += 1  # Track credit usage
                data = response.json()
                person_data = data.get("person", {})
                
                self.logger.debug(f" Person enriched: {person_id}")
                
                # Extract ALL available fields from the enrichment response
                # Build location string from city, state, country
                city = person_data.get("city", "")
                state = person_data.get("state", "")
                country = person_data.get("country", "")
                
                location_parts = [p for p in [city, state, country] if p]
                location = ", ".join(location_parts)
                
                # Try to get phone from sanitized_phone field (may be available without reveal)
                phone = person_data.get("sanitized_phone", "")
                
                return {
                    "email": person_data.get("email", ""),
                    "email_verified": person_data.get("email_status") in ["verified", "guessed"],
                    "phone": phone,
                    "linkedin_url": person_data.get("linkedin_url", ""),
                    "location": location,
                    "city": city,
                    "state": state,
                    "country": country,
                    "photo_url": person_data.get("photo_url", ""),
                    "twitter_url": person_data.get("twitter_url", ""),
                    "github_url": person_data.get("github_url", ""),
                    "facebook_url": person_data.get("facebook_url", ""),
                    "headline": person_data.get("headline", ""),
                    # Also get first_name and last_name since search returns obfuscated last name
                    "first_name": person_data.get("first_name", ""),
                    "last_name": person_data.get("last_name", ""),
                    "full_name": person_data.get("name", ""),
                }
            
            elif response.status_code == 402:  # Payment required
                self.logger.error(" Out of Apollo credits! Cannot enrich more contacts.")
                self.unlock_emails = False  # Disable further attempts
                return None
            
            elif response.status_code == 429:
                self.logger.warning("  Rate limit on enrichment - waiting 3 seconds")
                time.sleep(3)
                return self._enrich_person(person_id)  # Retry
            
            else:
                self.logger.warning(f"  Enrichment failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            self.logger.error(f" Enrichment error: {e}")
            return None

    # --------------------------------------------------------
    # Select Titles Using ICP Data
    # --------------------------------------------------------
    def _extract_titles_from_icp(self, icp: Dict[str, Any]) -> List[str]:
        """Use ICP target buyers as job titles"""
        if icp.get("target_buyers"):
            return icp["target_buyers"]

        # Fallback generic titles
        return [
            "CEO", "Founder", "Director", "Manager",
            "Head", "VP", "Executive", "Lead"
        ]

    # --------------------------------------------------------
    # Parse Apollo Search Response
    # --------------------------------------------------------
    def _parse_contacts(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse people from search response and enrich with full data.
        
        NOTE: The mixed_people/api_search endpoint returns LIMITED data:
        - first_name (full)
        - last_name_obfuscated (partial, like "Smi***")
        - title
        - id
        - has_email, has_city, etc. (booleans, not actual values)
        
        To get LinkedIn URL, location, and email, we MUST call /people/match
        """
        people = data.get("people", [])
        parsed = []

        for p in people:
            person_id = p.get("id")
            first_name = p.get("first_name", "")
            # Note: last_name might be obfuscated in new API
            last_name = p.get("last_name", "") or p.get("last_name_obfuscated", "")
            name = f"{first_name} {last_name}".strip()
            title = p.get("title")

            if not first_name or not title:
                continue

            # Base contact info from search (limited data)
            contact = {
                "name": name,
                "title": title,
                "email": "email_not_unlocked@domain.com",
                "linkedin_url": "",  # Not available from search anymore
                "phone": "",
                "location": "",
                "email_verified": False,
                "person_id": person_id  # Keep for reference
            }

            # ENRICH to get full profile data (LinkedIn, location, email)
            if self.unlock_emails and person_id:
                self.logger.debug(f" Enriching {first_name}...")
                enriched_data = self._enrich_person(person_id)
                
                if enriched_data:
                    # Update with enriched data
                    contact["email"] = enriched_data.get("email") or contact["email"]
                    contact["email_verified"] = enriched_data.get("email_verified", False)
                    contact["linkedin_url"] = enriched_data.get("linkedin_url", "")
                    contact["location"] = enriched_data.get("location", "")
                    contact["phone"] = enriched_data.get("phone", "")
                    
                    # Update name with full name if available
                    if enriched_data.get("full_name"):
                        contact["name"] = enriched_data["full_name"]
                    elif enriched_data.get("last_name"):
                        contact["name"] = f"{enriched_data.get('first_name', first_name)} {enriched_data['last_name']}"
                    
                    # Optional: add extra fields
                    contact["photo_url"] = enriched_data.get("photo_url", "")
                    contact["headline"] = enriched_data.get("headline", "")
                    
                    self.logger.info(f" Enriched: {contact['name']} | {contact['email']} | {contact['linkedin_url'][:50] if contact['linkedin_url'] else 'No LinkedIn'}")
                else:
                    self.logger.debug(f"  Could not enrich {first_name}")

            parsed.append(contact)

        return parsed

    # --------------------------------------------------------
    # Main Apollo Search Function
    # --------------------------------------------------------
    def _search_apollo(self, domain: str, icp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for contacts at a company"""
        titles = self._extract_titles_from_icp(icp)
        payload = self._build_search_payload(domain, titles)

        try:
            response = requests.post(
                f"{self.base_url}/mixed_people/api_search",
                headers=self._headers(),
                json=payload,
                timeout=20
            )

            if response.status_code == 401:
                self.logger.error(" Invalid Apollo API key")
                return []

            if response.status_code == 429:
                self.logger.warning("  Rate limit hit — retrying after 3 seconds")
                time.sleep(3)
                return self._search_apollo(domain, icp)

            if response.status_code != 200:
                self.logger.warning(f"  Apollo Error {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()
            return self._parse_contacts(data)

        except Exception as e:
            self.logger.error(f" Apollo request failed: {e}")
            return []

    # --------------------------------------------------------
    # PUBLIC METHOD → Enrich competitor list
    # --------------------------------------------------------
    def enrich(self, companies: List[Dict[str, Any]], icp: Dict[str, Any]):
        """
        Enrich company list with contact data from Apollo.
        
        Args:
            companies: List of companies with 'name' and 'domain'
            icp: Ideal Customer Profile with target_buyers
            
        Returns:
            List of companies with enriched contact data
        """
        self.logger.info(f" Enriching {len(companies)} companies via Apollo...")
        
        if self.unlock_emails:
            self.logger.warning(f" Email unlocking is ENABLED - This will use ~{len(companies) * 5} Apollo credits")
        
        final_output = []
        self.credits_used = 0  # Reset counter

        for comp in companies:
            domain = comp["domain"]
            self.logger.info(f" Searching contacts for {domain}")

            contacts = self._search_apollo(domain, icp)

            if not contacts:
                self.logger.warning(f"  No contacts found for {domain}")
                final_output.append({
                    "company": comp["name"],
                    "domain": domain,
                    "contacts": []
                })
                continue

            final_output.append({
                "company": comp["name"],
                "domain": domain,
                "contacts": contacts
            })

            # Sleep to avoid rate limits
            time.sleep(1.5)
        
        if self.credits_used > 0:
            self.logger.info(f" Total Apollo credits used: {self.credits_used}")

        return final_output

    # --------------------------------------------------------
    # Get Current Credit Balance
    # --------------------------------------------------------
    def check_credit_balance(self) -> Dict[str, Any]:
        """Check remaining Apollo credits"""
        try:
            response = requests.get(
                f"{self.base_url}/auth/health",
                headers=self._headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                credits_info = {
                    "credits_remaining": data.get("credits_remaining", "Unknown"),
                    "monthly_limit": data.get("monthly_limit", "Unknown")
                }
                self.logger.info(f" Apollo Credits: {credits_info['credits_remaining']} / {credits_info['monthly_limit']}")
                return credits_info
            else:
                self.logger.warning("  Could not fetch credit balance")
                return {}
                
        except Exception as e:
            self.logger.error(f" Credit check failed: {e}")
            return {}


# --------------------------------------------------------
# TEST DRIVER
# --------------------------------------------------------
if __name__ == "__main__":
    print("\n🔧 Testing Apollo Enricher (FIXED - LinkedIn & Location)")
    print("============================================================")

    test_icp = {
        "industry": "SaaS",
        "target_buyers": ["CEO", "CTO", "VP Engineering"]
    }

    test_companies = [
        {"name": "Shopify", "domain": "shopify.com"}
    ]

    # ========================================
    # TEST WITH EMAIL UNLOCK (Gets full data)
    # ========================================
    print("\n Test: WITH Email Unlocking (Gets LinkedIn + Location)")
    print("-" * 60)
    print("  This will use Apollo credits!")
    
    response = input("\nContinue with enrichment test? (yes/no): ")
    
    if response.lower() == 'yes':
        enricher = ApolloEnricher(unlock_emails=True)
        enricher.check_credit_balance()
        
        print("\n Running enrichment...")
        result = enricher.enrich(test_companies, test_icp)
        
        print("\n" + "="*60)
        print(" RESULTS WITH FULL DATA:")
        print("="*60)
        
        for company in result:
            print(f"\n Company: {company['company']}")
            print(f" Domain: {company['domain']}")
            print(f" Contacts Found: {len(company['contacts'])}")
            
            for i, contact in enumerate(company['contacts'], 1):
                print(f"\n  #{i} Contact:")
                print(f"     Name: {contact['name']}")
                print(f"     Title: {contact['title']}")
                print(f"      Email: {contact['email']}")
                print(f"      Verified: {contact['email_verified']}")
                print(f"      Phone: {contact.get('phone', 'N/A') or 'N/A'}")
                print(f"      LinkedIn: {contact.get('linkedin_url', 'N/A') or 'N/A'}")
                print(f"      Location: {contact.get('location', 'N/A') or 'N/A'}")
        
        print(f"\n💰 Total Credits Used: {enricher.credits_used}")
    else:
        print(" Test skipped")
    
    print("\n Test complete!")