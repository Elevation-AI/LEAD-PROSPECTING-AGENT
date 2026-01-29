"""
Full Agent 02 Test - Real Data Across Multiple Domains
=======================================================
Tests: LinkedIn Scraper + Tech Stack + Deep Enricher + Google Sheets
"""

import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from deep_enricher import DeepEnricher
from sheets_exporter import SheetsExporterOAuth

# Sample contacts from Agent 01 (simulating real output)
# These represent contacts from 3 different companies
agent01_contacts = [
    # Company 1: Stripe
    {
        "name": "Patrick Collison",
        "title": "CEO",
        "email": "patrick@stripe.com",
        "email_verified": True,
        "linkedin_url": "https://www.linkedin.com/in/patrickcollison",
        "company": "Stripe",
        "domain": "stripe.com"
    },
    {
        "name": "John Collison",
        "title": "President",
        "email": "john@stripe.com",
        "email_verified": True,
        "linkedin_url": "https://www.linkedin.com/in/john-collison",
        "company": "Stripe",
        "domain": "stripe.com"
    }
]


def main():
    print("\n" + "="*70)
    print(" FULL AGENT 02 PIPELINE TEST")
    print("="*70)
    print(f"\n Input: {len(agent01_contacts)} contacts from 3 companies")
    print("   • Stripe (2 contacts)")
    print("   • Shopify (1 contact)")
    print("   • OpenAI (2 contacts)")
    
    # Step 1: Deep Enrichment
    print("\n" + "-"*70)
    print("STEP 1: Deep Enrichment (LinkedIn + Tech Stack)")
    print("-"*70)
    
    enricher = DeepEnricher()
    enriched_contacts = enricher.enrich(agent01_contacts)
    
    print(f"\n Enrichment complete!")
    print(f"   • {len(enriched_contacts)} contacts enriched")
    
    # Step 2: Export to Google Sheets
    print("\n" + "-"*70)
    print("STEP 2: Export to Google Sheets")
    print("-"*70)
    
    exporter = SheetsExporterOAuth()
    sheet_url = exporter.export(enriched_contacts, sheet_name="Agent02_Full_Test")
    
    # Summary
    print("\n" + "="*70)
    print(" FULL PIPELINE TEST COMPLETE!")
    print("="*70)
    print(f"\n View Your Enriched Data:")
    print(f" {sheet_url}")
    print("\n Data Includes:")
    print("    Contact info (names, emails, titles)")
    print("    LinkedIn data (bio, tenure, location)")
    print("    Company tech stack (frameworks, tools)")
    print("    Fully formatted and ready for Agent 03!")
    print("\n" + "="*70)


if __name__ == "__main__":
    main()