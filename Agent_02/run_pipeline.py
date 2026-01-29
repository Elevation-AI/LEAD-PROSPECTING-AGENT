"""
Agent 01 + Agent 02 Combined Pipeline
======================================
Simple script - just like src/main.py but with Agent 02 added.
Run: python run_pipeline.py
"""

import sys
import os
import json
from datetime import datetime

# =============================================================================
# PATH SETUP
# =============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# =============================================================================
# IMPORTS - Agent 01 (from src/)
# =============================================================================
from src.scraper.website_scraper import WebsiteScraper
from src.icp.icp_generator import ICPGenerator
from src.search.company_finder import ProspectFinder
from src.enrichment.apollo_enricher import ApolloEnricher
from src.utils.helpers import validate_url

# =============================================================================
# IMPORTS - Agent 02 (from Agent_02/)
# =============================================================================
from deep_enricher import DeepEnricher
from sheets_exporter import SheetsExporterOAuth


def save_full_output(url, icp, prospects, apollo_enriched, deep_enriched, sheet_url, output_dir="output"):
    """Save all pipeline output to a single JSON file"""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_slug = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0]

    full_output = {
        "generated_at": datetime.now().isoformat(),
        "source_url": url,
        "pipeline_version": "Agent01 + Agent02",
        "icp": icp,
        "prospects_found": len(prospects),
        "prospects": prospects,
        "apollo_enriched": apollo_enriched,
        "deep_enriched": deep_enriched,
        "google_sheet_url": sheet_url,
        "total_contacts": len(deep_enriched) if deep_enriched else 0
    }

    filename = f"{company_slug}_full_pipeline_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(full_output, f, indent=4, ensure_ascii=False)

    print(f"\n💾 All output saved to: {filepath}")
    return filepath


def main():
    print("\n" + "=" * 60)
    print("🚀 Lead Prospecting Pipeline")
    print("   Agent 01 + Agent 02 Combined")
    print("=" * 60)

    # ---------------------------------------------------
    # GET URL FROM USER
    # ---------------------------------------------------
    url = input("\nEnter company website URL: ").strip()

    if not validate_url(url):
        print("❌ Invalid URL format. Example: https://asana.com")
        return

    # ===================================================
    # AGENT 01: STEP 1 - SCRAPE WEBSITE
    # ===================================================
    print("\n" + "-" * 60)
    print("📥 STEP 1: Scraping website content...")
    print("-" * 60)

    scraper = WebsiteScraper()
    scraped = scraper.scrape_website(url)

    if not scraped or len(scraped["combined_text"]) < 200:
        print("❌ Could not extract useful content from website.")
        return

    print(f"✅ Scraping successful! Extracted {scraped['content_length']} characters.")

    # ===================================================
    # AGENT 01: STEP 2 - GENERATE ICP
    # ===================================================
    print("\n" + "-" * 60)
    print("🎯 STEP 2: Generating ICP using LLM...")
    print("-" * 60)

    icp_gen = ICPGenerator()

    try:
        icp = icp_gen.generate_icp(scraped["combined_text"])
        print("\n✅ ICP Generated Successfully:\n")
        print(json.dumps(icp, indent=4))

        # Ask user for overrides
        icp = icp_gen.get_user_overrides(icp)
        print("\n📋 FINAL ICP (After User Customization):\n")
        print(json.dumps(icp, indent=4))

    except Exception as e:
        print(f"❌ ICP generation failed: {e}")
        return

    # ===================================================
    # AGENT 01: STEP 3 - FIND PROSPECTS
    # ===================================================
    print("\n" + "-" * 60)
    print("🔍 STEP 3: Discovering Prospect Companies...")
    print("-" * 60)

    finder = ProspectFinder()
    prospects = finder.find_prospects(icp)

    if not prospects:
        print("❌ No prospect companies found.")
        return

    print("\n✅ PROSPECTS Found:")
    for c in prospects:
        print(f"   - {c['name']} ({c['domain']}) — Confidence: {c['confidence']:.2f}")

    # ===================================================
    # AGENT 01: STEP 4 - APOLLO ENRICHMENT
    # ===================================================
    print("\n" + "-" * 60)
    print("📧 STEP 4: Enriching prospects using Apollo API...")
    print("-" * 60)

    unlock = input("Unlock emails? (costs credits) [yes/no]: ").lower() == 'yes'
    enricher = ApolloEnricher(unlock_emails=unlock)
    apollo_enriched = enricher.enrich(prospects, icp)

    print("\n✅ Apollo Enrichment Results:\n")
    print(json.dumps(apollo_enriched, indent=4))

    # ===================================================
    # AGENT 02: STEP 5 - DEEP ENRICHMENT (LinkedIn + Tech Stack)
    # ===================================================
    print("\n" + "-" * 60)
    print("🔗 STEP 5: Deep Enrichment (LinkedIn + Tech Stack)...")
    print("-" * 60)

    # Flatten contacts from Apollo output
    all_contacts = []
    for company in apollo_enriched:
        company_name = company.get("company_name", "Unknown")
        domain = company.get("domain", "")

        for contact in company.get("contacts", []):
            contact_data = {
                "name": contact.get("name", ""),
                "title": contact.get("title", ""),
                "email": contact.get("email", ""),
                "email_verified": contact.get("email_status") == "verified",
                "linkedin_url": contact.get("linkedin_url", ""),
                "company": company_name,
                "domain": domain
            }
            all_contacts.append(contact_data)

    if not all_contacts:
        print("⚠️ No contacts to deep enrich")
        deep_enriched = []
    else:
        # =================================================================
        # LINKEDIN LIMIT - CHANGE THIS FOR PRODUCTION
        # =================================================================
        # For TESTING: Set to 5 (saves time and API credits)
        # For PRODUCTION: Set to 0 (processes ALL LinkedIn profiles)
        #
        # LINE TO CHANGE: Change the number below
        MAX_LINKEDIN_PROFILES = 5  # ← CHANGE THIS: 5 for testing, 0 for ALL
        # =================================================================

        # Separate contacts with/without LinkedIn
        contacts_with_linkedin = [c for c in all_contacts if c.get("linkedin_url")]
        contacts_without_linkedin = [c for c in all_contacts if not c.get("linkedin_url")]

        total_linkedin = len(contacts_with_linkedin)
        print(f"📊 Found {total_linkedin} contacts with LinkedIn URLs")

        # Apply limit
        if MAX_LINKEDIN_PROFILES > 0 and total_linkedin > MAX_LINKEDIN_PROFILES:
            print(f"⚠️  LIMITING to {MAX_LINKEDIN_PROFILES} LinkedIn profiles (for testing)")
            print(f"   To process ALL: Change MAX_LINKEDIN_PROFILES to 0 in run_pipeline.py line ~191")
            contacts_with_linkedin = contacts_with_linkedin[:MAX_LINKEDIN_PROFILES]
        elif MAX_LINKEDIN_PROFILES == 0:
            print(f"🚀 Processing ALL {total_linkedin} LinkedIn profiles (production mode)")

        # Combine: limited LinkedIn + all non-LinkedIn contacts
        contacts_to_process = contacts_with_linkedin + contacts_without_linkedin
        print(f"📊 Processing {len(contacts_to_process)} total contacts...")

        deep_enricher = DeepEnricher()
        deep_enriched = deep_enricher.enrich(contacts_to_process)

        print(f"\n✅ Deep enriched {len(deep_enriched)} contacts")

    # ===================================================
    # AGENT 02: STEP 6 - EXPORT TO GOOGLE SHEETS
    # ===================================================
    print("\n" + "-" * 60)
    print("📊 STEP 6: Export to Google Sheets...")
    print("-" * 60)

    sheet_url = None
    if deep_enriched:
        export_sheets = input("Export to Google Sheets? [yes/no]: ").lower() == 'yes'

        if export_sheets:
            company_slug = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0]
            sheet_name = f"Leads_{company_slug}_{datetime.now():%Y%m%d_%H%M}"

            sheets_exporter = SheetsExporterOAuth()
            sheet_url = sheets_exporter.export(deep_enriched, sheet_name)

            print(f"\n✅ Exported to Google Sheets: {sheet_url}")
        else:
            print("⏭️ Skipping Google Sheets export")
    else:
        print("⚠️ No data to export")

    # ===================================================
    # SAVE LOCAL OUTPUT
    # ===================================================
    save_full_output(
        url=url,
        icp=icp,
        prospects=prospects,
        apollo_enriched=apollo_enriched,
        deep_enriched=deep_enriched,
        sheet_url=sheet_url,
        output_dir=os.path.join(PROJECT_ROOT, "output")
    )

    # ===================================================
    # DONE!
    # ===================================================
    print("\n" + "=" * 60)
    print("✅ FULL PIPELINE COMPLETE!")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   • Prospects found: {len(prospects)}")
    print(f"   • Contacts enriched: {len(deep_enriched)}")
    if sheet_url:
        print(f"   • Google Sheet: {sheet_url}")
    print("\n")


if __name__ == "__main__":
    main()
