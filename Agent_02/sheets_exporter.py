"""
Google Sheets Exporter using Service Account
=============================================
Creates sheets via GCP Service Account (no browser needed, never expires)
Works on local dev AND GCP Cloud Run / GCE
"""

import os
import sys
from typing import List, Dict
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

# ------------------------------------------------------------------
#  PROJECT ROOT (CRITICAL FIX)
# ------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

# Ensure imports work everywhere
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.helpers import setup_logger


class SheetsExporterOAuth:
    """
    Export enriched contact data to Google Sheets using Service Account.
    Set SHEET_OWNER_EMAIL env var to auto-share sheets to your personal Drive.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.client = None
        self._authenticate()

    # ------------------------------------------------------------------
    #  AUTHENTICATION (Service Account - works on GCP, never expires)
    # ------------------------------------------------------------------
    def _authenticate(self):
        credentials_path = os.path.join(PROJECT_ROOT, "config", "service-account.json")

        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"Service account credentials not found at:\n{credentials_path}\n"
                f"Download from GCP Console → IAM → Service Accounts → Keys → JSON"
            )

        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=self.SCOPES
        )

        self.client = gspread.authorize(creds)
        self.logger.info(" Authenticated with service account")

    # ------------------------------------------------------------------
    #  DATA PREPARATION
    # ------------------------------------------------------------------
    def _headers(self) -> List[str]:
        return [
            "First Name", "Last Name", "Full Name", "Job Title",
            "Email", "Email Verified", "LinkedIn URL", "Time in Role",
            "Location", "Bio Snippet", "Company", "Company Domain",
            "About the Company", "Company Tech Stack", "Primary Framework",
            "Hosting Provider", "Analytics Tools", "Enrichment Date"
        ]

    def _row(self, contact: Dict) -> List[str]:
        full_name = str(contact.get("name", contact.get("full_name", "")) or "")
        parts = full_name.split(" ", 1)
        first = parts[0] if parts else ""
        last = parts[1] if len(parts) > 1 else ""

        tech_stack = contact.get("company_tech_stack", [])
        if isinstance(tech_stack, list):
            tech_stack_str = ", ".join(str(t) for t in tech_stack) if tech_stack else "Not detected"
        else:
            tech_stack_str = str(tech_stack) if tech_stack else "Not detected"

        categories = contact.get("company_description", {})
        if not isinstance(categories, dict):
            categories = {}
        primary_framework = str(categories.get("frontend", "N/A") or "N/A")
        hosting = str(categories.get("hosting", "N/A") or "N/A")
        analytics_list = categories.get("analytics", [])
        if isinstance(analytics_list, list):
            analytics = ", ".join(str(a) for a in analytics_list) or "N/A"
        else:
            analytics = str(analytics_list) if analytics_list else "N/A"

        bio = contact.get("bio_snippet") or contact.get("headline") or ""

        return [
            first,
            last,
            full_name,
            str(contact.get("title", contact.get("current_title", "N/A")) or "N/A"),
            str(contact.get("email", "N/A") or "N/A"),
            "Yes" if contact.get("email_verified") else "No",
            str(contact.get("linkedin_url", "N/A") or "N/A"),
            str(contact.get("time_in_role", "N/A") or "N/A"),
            str(contact.get("location", "N/A") or "N/A"),
            str(bio)[:100],
            str(contact.get("company", contact.get("current_company", "N/A")) or "N/A"),
            str(contact.get("domain", "N/A") or "N/A"),
            str(contact.get("about_company", "N/A") or "N/A"),
            tech_stack_str,
            primary_framework,
            hosting,
            analytics,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]

    # ------------------------------------------------------------------
    # 📤 EXPORT
    # ------------------------------------------------------------------
    def export(self, contacts: List[Dict], sheet_name: str = None) -> str:
        if not contacts:
            raise ValueError(" No contacts to export")

        if not sheet_name:
            sheet_name = f"Agent02_Enriched_{datetime.now():%Y-%m-%d_%H-%M}"

        self.logger.info(f" Creating Google Sheet: {sheet_name}")

        spreadsheet = self.client.create(
            sheet_name,
            folder_id="0AIaLj4bNYk2CUk9PVA"
        )

        worksheet = spreadsheet.sheet1

        worksheet.append_row(self._headers())
        for contact in contacts:
            worksheet.append_row(self._row(contact))

        worksheet.freeze(rows=1)

        spreadsheet.share("", perm_type="anyone", role="reader")

        owner_email = os.environ.get("SHEET_OWNER_EMAIL")
        if owner_email:
            spreadsheet.share(owner_email, perm_type="user", role="writer", notify=False)

        self.logger.info(" Google Sheet created successfully")
        return spreadsheet.url



# ------------------------------------------------------------------
# 🧪 STANDALONE TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("🔧 OAuth Google Sheets Exporter Test")
    print("=" * 70)

    sample_contacts = [
        {
            "name": "Amit Singh",
            "title": "Director of Engineering",
            "email": "amit.singh@fintechco.com",
            "email_verified": True,
            "linkedin_url": "https://www.linkedin.com/in/amit-singh-engineering",
            "bio_snippet": "Engineering leader with 12+ years experience.",
            "time_in_role": "2 yr 3 mo",
            "location": "Bangalore, India",
            "company": "FinTechCo",
            "domain": "fintechco.com",
            "company_tech_stack": ["React", "Node.js", "AWS", "PostgreSQL"],
            "company_description": {
                "frontend": "React",
                "hosting": "AWS",
                "analytics": ["Segment"]
            }
        }
    ]

    exporter = SheetsExporterOAuth()
    url = exporter.export(sample_contacts)
    print(f"\n Sheet created:\n{url}\n")
