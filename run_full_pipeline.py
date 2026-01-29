"""
Full Lead Prospecting Pipeline: Agent 01 + Agent 02 + Agent 03
===============================================================
Complete end-to-end pipeline that:
1. Agent 01: Scrapes website → Generates ICP → Finds prospects → Apollo enrichment
2. Agent 02: Deep enrichment (LinkedIn + Tech Stack) → Google Sheet
3. Agent 03: Generates personalized outreach emails → Google Sheet

Usage:
    python run_full_pipeline.py

One command to go from URL to ready-to-send email drafts!
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List

# =============================================================================
# PATH SETUP
# =============================================================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Add Agent folders to path
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Agent_02"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Agent_03"))

# =============================================================================
# IMPORTS - Agent 01 (from src/)
# =============================================================================
from src.scraper.website_scraper import WebsiteScraper
from src.icp.icp_generator import ICPGenerator
from src.search.company_finder import ProspectFinder
from src.enrichment.apollo_enricher import ApolloEnricher
from src.utils.helpers import validate_url, setup_logger



# =============================================================================
# IMPORTS - Agent 02 (from Agent_02/)
# =============================================================================
from deep_enricher import DeepEnricher
from sheets_exporter import SheetsExporterOAuth

# =============================================================================
# IMPORTS - Agent 03 (from Agent_03/)
# =============================================================================
from email_generator import EmailGenerator
from sheets_output import EmailSheetsExporter

logger = setup_logger(__name__)


def save_full_output(data: Dict, output_dir: str = "output") -> str:
    """Save complete pipeline output to JSON file"""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url = data.get("source_url", "unknown")
    company_slug = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0]

    filename = f"{company_slug}_full_pipeline_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"\n💾 Full output saved to: {filepath}")
    return filepath


def main():
    print("\n" + "=" * 70)
    print("🚀 FULL LEAD PROSPECTING PIPELINE")
    print("   Agent 01 + Agent 02 + Agent 03")
    print("   URL → Research → Enrichment → Personalized Emails")
    print("=" * 70)

    # =========================================================================
    # GET INPUT URL
    # =========================================================================
    url = input("\n📌 Enter company website URL: ").strip()

    if not validate_url(url):
        print("❌ Invalid URL format. Example: https://asana.com")
        return

    # =========================================================================
    # AGENT 01: STEP 1 - SCRAPE WEBSITE
    # =========================================================================
    print("\n" + "=" * 70)
    print("📥 AGENT 01 - STEP 1: Scraping Website")
    print("=" * 70)

    scraper = WebsiteScraper()
    scraped = scraper.scrape_website(url)

    if not scraped or len(scraped.get("combined_text", "")) < 200:
        print("❌ Could not extract useful content from website.")
        return

    print(f"✅ Scraped {scraped['content_length']} characters")

    # =========================================================================
    # AGENT 01: STEP 2 - GENERATE ICP
    # =========================================================================
    print("\n" + "=" * 70)
    print("🎯 AGENT 01 - STEP 2: Generating ICP")
    print("=" * 70)

    icp_gen = ICPGenerator()

    try:
        icp = icp_gen.generate_icp(scraped["combined_text"])
        print("\n✅ ICP Generated:")
        print(json.dumps(icp, indent=2))

        # Ask for customization
        icp = icp_gen.get_user_overrides(icp)
        print("\n📋 Final ICP confirmed")

    except Exception as e:
        print(f"❌ ICP generation failed: {e}")
        return

    # =========================================================================
    # AGENT 01: STEP 3 - FIND PROSPECTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("🔍 AGENT 01 - STEP 3: Finding Prospects")
    print("=" * 70)

    finder = ProspectFinder()
    prospects = finder.find_prospects(icp)

    if not prospects:
        print("❌ No prospect companies found.")
        return

    print(f"\n✅ Found {len(prospects)} prospects:")
    for c in prospects[:5]:
        print(f"   - {c['name']} ({c['domain']}) — Confidence: {c['confidence']:.2f}")
    if len(prospects) > 5:
        print(f"   ... and {len(prospects) - 5} more")

    # =========================================================================
    # AGENT 01: STEP 4 - APOLLO ENRICHMENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("📧 AGENT 01 - STEP 4: Apollo Enrichment")
    print("=" * 70)

    unlock = input("Unlock emails? (costs Apollo credits) [yes/no]: ").lower() == 'yes'
    enricher = ApolloEnricher(unlock_emails=unlock)
    apollo_enriched = enricher.enrich(prospects, icp)

    total_contacts = sum(len(c.get("contacts", [])) for c in apollo_enriched)
    print(f"\n✅ Apollo enriched {len(apollo_enriched)} companies with {total_contacts} contacts")

    # =========================================================================
    # AGENT 02: STEP 5 - DEEP ENRICHMENT (LinkedIn + Tech Stack)
    # =========================================================================
    print("\n" + "=" * 70)
    print("🔗 AGENT 02 - STEP 5: Deep Enrichment (LinkedIn + Tech Stack)")
    print("=" * 70)

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
        MAX_LINKEDIN_PROFILES = 10  # ← CHANGE THIS: 10 for testing, 0 for ALL
        # =================================================================

        contacts_with_linkedin = [c for c in all_contacts if c.get("linkedin_url")]
        contacts_without_linkedin = [c for c in all_contacts if not c.get("linkedin_url")]

        total_linkedin = len(contacts_with_linkedin)
        print(f"📊 Found {total_linkedin} contacts with LinkedIn URLs")

        if MAX_LINKEDIN_PROFILES > 0 and total_linkedin > MAX_LINKEDIN_PROFILES:
            print(f"⚠️  LIMITING to {MAX_LINKEDIN_PROFILES} LinkedIn profiles (for testing)")
            contacts_with_linkedin = contacts_with_linkedin[:MAX_LINKEDIN_PROFILES]
        elif MAX_LINKEDIN_PROFILES == 0:
            print(f"🚀 Processing ALL {total_linkedin} LinkedIn profiles")

        contacts_to_process = contacts_with_linkedin + contacts_without_linkedin
        print(f"📊 Processing {len(contacts_to_process)} total contacts...")

        deep_enricher = DeepEnricher()
        deep_enriched = deep_enricher.enrich(contacts_to_process)

        print(f"\n✅ Deep enriched {len(deep_enriched)} contacts")

    # =========================================================================
    # AGENT 02: STEP 6 - EXPORT CONTACTS TO GOOGLE SHEETS
    # =========================================================================
    print("\n" + "=" * 70)
    print("📊 AGENT 02 - STEP 6: Export Contacts to Google Sheets")
    print("=" * 70)

    contacts_sheet_url = None
    if deep_enriched:
        company_slug = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0]
        sheet_name = f"Leads_{company_slug}_{datetime.now():%Y%m%d_%H%M}"

        contacts_exporter = SheetsExporterOAuth()
        contacts_sheet_url = contacts_exporter.export(deep_enriched, sheet_name)

        print(f"\n✅ Contacts exported to: {contacts_sheet_url}")

    # =========================================================================
    # AGENT 03: STEP 7 - CONFIGURE EMAIL SETTINGS
    # =========================================================================
    print("\n" + "=" * 70)
    print("⚙️  AGENT 03 - STEP 7: Email Configuration")
    print("=" * 70)

    # Tone selection
    print("\n📝 Select email TONE:")
    print("   1. Professional (formal, business-appropriate)")
    print("   2. Casual (friendly, conversational)")
    print("   3. Direct (concise, to-the-point)")

    tone_choice = input("\nEnter choice [1/2/3] (default: 1): ").strip()
    tone_map = {"1": "professional", "2": "casual", "3": "direct", "": "professional"}
    tone = tone_map.get(tone_choice, "professional")

    # CTA selection
    print("\n🎯 Select CALL TO ACTION:")
    print("   1. Call (ask for a 15-minute call)")
    print("   2. Demo (offer a personalized demo)")
    print("   3. PDF (offer to send a case study)")
    print("   4. Reply (ask them to reply)")
    print("   5. Meeting (suggest scheduling a meeting)")

    cta_choice = input("\nEnter choice [1-5] (default: 1): ").strip()
    cta_map = {"1": "call", "2": "demo", "3": "pdf", "4": "reply", "5": "meeting", "": "call"}
    cta = cta_map.get(cta_choice, "call")

    # Sender info
    print("\n👤 SENDER INFORMATION:")
    sender_name = input("   Your name: ").strip() or "Sales Representative"
    sender_company = input("   Your company name: ").strip() or "Our Company"

    # Value proposition
    print("\n💡 VALUE PROPOSITION:")
    print("   (What problem do you solve? How do you help customers?)")
    value_proposition = input("\n   Your value proposition: ").strip()
    if not value_proposition:
        value_proposition = "We help companies improve their operations and efficiency"

    # =========================================================================
    # AGENT 03: STEP 8 - GENERATE PERSONALIZED EMAILS
    # =========================================================================
    print("\n" + "=" * 70)
    print("📧 AGENT 03 - STEP 8: Generating Personalized Emails")
    print("=" * 70)

    if not deep_enriched:
        print("⚠️ No contacts to generate emails for")
        emails = []
    else:
        generator = EmailGenerator()
        generator.configure(
            tone=tone,
            cta=cta,
            sender_name=sender_name,
            sender_company=sender_company,
            value_proposition=value_proposition
        )

        print(f"\n⏳ Generating {len(deep_enriched)} personalized emails...")
        emails = generator.generate_batch(deep_enriched)

        success_count = sum(1 for e in emails if e["generation_status"] == "success")
        print(f"\n✅ Generated {success_count}/{len(emails)} emails successfully")

        # Show preview
        print("\n📬 EMAIL PREVIEW (First 2):")
        print("-" * 50)
        for i, email in enumerate(emails[:2], 1):
            print(f"\n--- Email {i} ---")
            print(f"To: {email['recipient_name']} <{email['recipient_email']}>")
            print(f"Subject: {email['subject_line']}")
            print(f"\n{email['body']}")
            print("-" * 50)

    # =========================================================================
    # AGENT 03: STEP 9 - EXPORT EMAILS TO GOOGLE SHEETS
    # =========================================================================
    print("\n" + "=" * 70)
    print("📊 AGENT 03 - STEP 9: Export Emails to Google Sheets")
    print("=" * 70)

    emails_sheet_url = None
    if emails:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        email_sheet_name = f"Outreach_Emails_{sender_company.replace(' ', '_')}_{timestamp}"

        email_exporter = EmailSheetsExporter()
        emails_sheet_url = email_exporter.export(emails, email_sheet_name)

        print(f"\n✅ Emails exported to: {emails_sheet_url}")

    # =========================================================================
    # SAVE LOCAL OUTPUT
    # =========================================================================
    full_output = {
        "generated_at": datetime.now().isoformat(),
        "source_url": url,
        "pipeline_version": "Agent01 + Agent02 + Agent03",
        "icp": icp,
        "prospects_found": len(prospects),
        "prospects": prospects,
        "apollo_enriched": apollo_enriched,
        "deep_enriched": deep_enriched,
        "contacts_sheet_url": contacts_sheet_url,
        "email_config": {
            "tone": tone,
            "cta": cta,
            "sender_name": sender_name,
            "sender_company": sender_company,
            "value_proposition": value_proposition
        },
        "emails_generated": len(emails),
        "emails": emails,
        "emails_sheet_url": emails_sheet_url
    }

    save_full_output(full_output, os.path.join(PROJECT_ROOT, "output"))

    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ FULL PIPELINE COMPLETE!")
    print("=" * 70)

    print(f"\n📊 SUMMARY:")
    print(f"   • Source URL: {url}")
    print(f"   • Prospects found: {len(prospects)}")
    print(f"   • Contacts enriched: {len(deep_enriched)}")
    print(f"   • Emails generated: {len(emails)}")

    print(f"\n📄 GOOGLE SHEETS:")
    if contacts_sheet_url:
        print(f"   • Contacts: {contacts_sheet_url}")
    if emails_sheet_url:
        print(f"   • Email Drafts: {emails_sheet_url}")

    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Open the Email Drafts Google Sheet")
    print(f"   2. Review each email")
    print(f"   3. Make any edits needed")
    print(f"   4. Copy-paste to Gmail and send!")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
