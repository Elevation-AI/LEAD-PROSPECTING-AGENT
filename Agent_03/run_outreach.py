"""
Agent 03: Outreach Orchestration - Main Runner
===============================================
Takes enriched contacts from Agent 02 (Google Sheet or JSON) and generates
personalized outreach emails, exporting them to Google Sheets for review.

Usage:
    python run_outreach.py

Flow:
    1. User provides input (Google Sheet URL from Agent 02 OR local JSON file)
    2. User configures email settings (tone, CTA, sender info, value prop)
    3. Agent generates personalized emails for each contact
    4. Exports to Google Sheet for user to review and send

Part of Agent 03: Outreach Orchestration (V1 - "The Ghostwriter")
"""

import sys
import os
import json
from datetime import datetime
from typing import List, Dict

# =============================================================================
# PATH SETUP
# =============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# =============================================================================
# IMPORTS
# =============================================================================
from email_generator import EmailGenerator
from sheets_output import EmailSheetsExporter

import gspread
from google.oauth2.credentials import Credentials

from src.utils.helpers import setup_logger

logger = setup_logger(__name__)


def load_contacts_from_sheet(sheet_url: str) -> List[Dict]:
    """
    Load contacts from Agent 02's Google Sheet output.

    Args:
        sheet_url: URL of the Google Sheet from Agent 02

    Returns:
        List of contact dictionaries
    """
    logger.info(f"Loading contacts from Google Sheet...")

    # Authenticate
    token_path = os.path.join(PROJECT_ROOT, "config", "token.json")

    if not os.path.exists(token_path):
        raise FileNotFoundError("Please run Agent 02 first to authenticate with Google")

    credentials = Credentials.from_authorized_user_file(token_path)
    client = gspread.authorize(credentials)

    # Extract spreadsheet ID from URL
    spreadsheet_id = sheet_url.split('/d/')[1].split('/')[0]
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.sheet1

    # Get all records
    records = worksheet.get_all_records()

    # Map Google Sheet columns to contact format
    contacts = []
    for record in records:
        contact = {
            "name": record.get("Full Name") or f"{record.get('First Name', '')} {record.get('Last Name', '')}".strip(),
            "first_name": record.get("First Name"),
            "last_name": record.get("Last Name"),
            "title": record.get("Job Title"),
            "email": record.get("Email"),
            "email_verified": record.get("Email Verified", "").lower() == "yes",
            "linkedin_url": record.get("LinkedIn URL"),
            "time_in_role": record.get("Time in Role"),
            "location": record.get("Location"),
            "bio_snippet": record.get("Bio Snippet"),
            "company": record.get("Company"),
            "domain": record.get("Company Domain"),
            "company_tech_stack": record.get("Company Tech Stack", "").split(", ") if record.get("Company Tech Stack") else [],
        }
        contacts.append(contact)

    logger.info(f"✅ Loaded {len(contacts)} contacts from Google Sheet")
    return contacts


def load_contacts_from_json(file_path: str) -> List[Dict]:
    """
    Load contacts from a local JSON file (Agent 02 output).

    Args:
        file_path: Path to the JSON file

    Returns:
        List of contact dictionaries
    """
    logger.info(f"Loading contacts from JSON file: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle different JSON structures
    if isinstance(data, list):
        contacts = data
    elif "deep_enriched" in data:
        contacts = data["deep_enriched"]
    elif "contacts" in data:
        contacts = data["contacts"]
    else:
        contacts = data

    logger.info(f"✅ Loaded {len(contacts)} contacts from JSON file")
    return contacts


def get_user_config() -> Dict:
    """
    Get email configuration from user.

    Returns:
        Dictionary with tone, cta, sender_name, sender_company, value_proposition
    """
    print("\n" + "=" * 60)
    print("⚙️  EMAIL CONFIGURATION")
    print("=" * 60)

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
    sender_name = input("   Your name: ").strip()
    if not sender_name:
        sender_name = "Sales Representative"

    sender_company = input("   Your company name: ").strip()
    if not sender_company:
        sender_company = "Our Company"

    # Value proposition
    print("\n💡 VALUE PROPOSITION:")
    print("   (What problem do you solve? How do you help customers?)")
    print("   Example: We help operations teams automate repetitive tasks and reduce manual work by 40%")

    value_proposition = input("\n   Your value proposition: ").strip()
    if not value_proposition:
        value_proposition = "We help companies improve their operations and efficiency"

    config = {
        "tone": tone,
        "cta": cta,
        "sender_name": sender_name,
        "sender_company": sender_company,
        "value_proposition": value_proposition
    }

    # Confirm
    print("\n" + "-" * 60)
    print("📋 CONFIGURATION SUMMARY:")
    print(f"   • Tone: {tone}")
    print(f"   • CTA: {cta}")
    print(f"   • Sender: {sender_name} @ {sender_company}")
    print(f"   • Value Prop: {value_proposition[:50]}...")
    print("-" * 60)

    confirm = input("\nProceed with this configuration? [Y/n]: ").strip().lower()
    if confirm == 'n':
        print("Restarting configuration...")
        return get_user_config()

    return config


def main():
    print("\n" + "=" * 60)
    print("🚀 AGENT 03: Outreach Orchestration")
    print("   The Ghostwriter - V1")
    print("=" * 60)

    # =========================================================================
    # STEP 1: GET INPUT SOURCE
    # =========================================================================
    print("\n📥 STEP 1: Select Input Source")
    print("-" * 60)
    print("   1. Google Sheet URL (from Agent 02)")
    print("   2. Local JSON file (from Agent 02 output)")

    source_choice = input("\nEnter choice [1/2]: ").strip()

    contacts = []

    if source_choice == "1":
        sheet_url = input("\nEnter Google Sheet URL from Agent 02: ").strip()
        if not sheet_url:
            print("❌ No URL provided")
            return
        contacts = load_contacts_from_sheet(sheet_url)

    elif source_choice == "2":
        # Look for JSON files in output folder
        output_dir = os.path.join(PROJECT_ROOT, "output")
        if os.path.exists(output_dir):
            json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
            if json_files:
                print(f"\n📁 Found JSON files in output/:")
                for i, f in enumerate(json_files[-5:], 1):  # Show last 5
                    print(f"   {i}. {f}")

        file_path = input("\nEnter JSON file path (or filename from output/): ").strip()

        if not file_path:
            print("❌ No file provided")
            return

        # Handle relative path
        if not os.path.isabs(file_path) and not os.path.exists(file_path):
            file_path = os.path.join(output_dir, file_path)

        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return

        contacts = load_contacts_from_json(file_path)
    else:
        print("❌ Invalid choice")
        return

    if not contacts:
        print("❌ No contacts found in input source")
        return

    # Show contacts summary
    print(f"\n✅ Loaded {len(contacts)} contacts:")
    for i, c in enumerate(contacts[:5], 1):
        print(f"   {i}. {c.get('name', 'Unknown')} - {c.get('title', 'N/A')} @ {c.get('company', 'N/A')}")
    if len(contacts) > 5:
        print(f"   ... and {len(contacts) - 5} more")

    # =========================================================================
    # STEP 2: CONFIGURE EMAIL SETTINGS
    # =========================================================================
    config = get_user_config()

    # =========================================================================
    # STEP 3: GENERATE EMAILS
    # =========================================================================
    print("\n" + "=" * 60)
    print("📧 STEP 3: Generating Personalized Emails")
    print("=" * 60)

    # Initialize generator
    generator = EmailGenerator()
    generator.configure(
        tone=config["tone"],
        cta=config["cta"],
        sender_name=config["sender_name"],
        sender_company=config["sender_company"],
        value_proposition=config["value_proposition"]
    )

    # Generate emails
    print(f"\n⏳ Generating {len(contacts)} emails...")
    emails = generator.generate_batch(contacts)

    # Show preview
    print("\n" + "-" * 60)
    print("📬 EMAIL PREVIEW (First 2):")
    print("-" * 60)

    for i, email in enumerate(emails[:2], 1):
        print(f"\n{'='*50}")
        print(f"📧 Email {i}")
        print(f"{'='*50}")
        print(f"To: {email['recipient_name']} <{email['recipient_email']}>")
        print(f"Subject: {email['subject_line']}")
        print(f"\n--- Body ---")
        print(email['body'])  # Show FULL email body
        print(f"\n[Status: {email['generation_status']}]")
        print(f"[Personalization: {', '.join(email.get('personalization_used', []))}]")

    # =========================================================================
    # STEP 4: EXPORT TO GOOGLE SHEETS
    # =========================================================================
    print("\n" + "=" * 60)
    print("📊 STEP 4: Export to Google Sheets")
    print("=" * 60)

    export_choice = input("\nExport emails to Google Sheet? [Y/n]: ").strip().lower()

    sheet_url = None
    if export_choice != 'n':
        # Generate sheet name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        sheet_name = f"Outreach_Emails_{config['sender_company'].replace(' ', '_')}_{timestamp}"

        print(f"\n📤 Exporting to Google Sheets...")

        exporter = EmailSheetsExporter()
        sheet_url = exporter.export(emails, sheet_name)

        print(f"\n✅ Exported to: {sheet_url}")

    # =========================================================================
    # STEP 5: SAVE LOCAL COPY
    # =========================================================================
    save_local = input("\nSave local JSON copy? [Y/n]: ").strip().lower()

    if save_local != 'n':
        output_dir = os.path.join(PROJECT_ROOT, "output")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"outreach_emails_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        output_data = {
            "generated_at": datetime.now().isoformat(),
            "config": config,
            "total_emails": len(emails),
            "emails": emails,
            "google_sheet_url": sheet_url
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        print(f"✅ Saved to: {filepath}")

    # =========================================================================
    # DONE!
    # =========================================================================
    print("\n" + "=" * 60)
    print("✅ AGENT 03 COMPLETE!")
    print("=" * 60)

    success_count = sum(1 for e in emails if e["generation_status"] == "success")

    print(f"\n📊 Summary:")
    print(f"   • Emails generated: {success_count}/{len(emails)}")
    print(f"   • Tone: {config['tone']}")
    print(f"   • CTA: {config['cta']}")

    if sheet_url:
        print(f"\n📄 Google Sheet (Review & Send):")
        print(f"   {sheet_url}")

    print("\n💡 Next Steps:")
    print("   1. Open the Google Sheet")
    print("   2. Review each email draft")
    print("   3. Make any edits needed")
    print("   4. Copy-paste to Gmail and send!")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
