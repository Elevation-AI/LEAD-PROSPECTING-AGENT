"""
Google Sheets Exporter using OAuth (User Account)
================================================
Creates sheets in YOUR Google Drive (not service account)
Works correctly when run standalone OR inside full pipeline
"""

import os
import sys
import pickle
from typing import List, Dict
from datetime import datetime

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

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
    Export enriched contact data to Google Sheets using OAuth
    Sheets are created in YOUR Google Drive
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
    #  AUTHENTICATION
    # ------------------------------------------------------------------
    def _authenticate(self):
        creds = None

        token_path = os.path.join(PROJECT_ROOT, "config", "token.pickle")
        credentials_path = os.path.join(PROJECT_ROOT, "config", "oauth-credentials.json")

        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f" OAuth credentials not found at:\n{credentials_path}\n"
                        f"Download from Google Cloud Console → OAuth Client ID"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path,
                    self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        self.client = gspread.authorize(creds)
        self.logger.info(" Authenticated with YOUR Google account")

    # ------------------------------------------------------------------
    #  DATA PREPARATION
    # ------------------------------------------------------------------
    def _headers(self) -> List[str]:
        return [
            "First Name", "Last Name", "Full Name", "Job Title",
            "Email", "Email Verified", "LinkedIn URL", "Time in Role",
            "Location", "Bio Snippet", "Company", "Company Domain",
            "Company Tech Stack", "Primary Framework", "Hosting Provider",
            "Analytics Tools", "Enrichment Date"
        ]

    def _row(self, contact: Dict) -> List[str]:
        full_name = contact.get("name", contact.get("full_name", ""))
        parts = full_name.split(" ", 1)
        first = parts[0] if parts else ""
        last = parts[1] if len(parts) > 1 else ""

        tech_stack = contact.get("company_tech_stack", [])
        tech_stack_str = ", ".join(tech_stack) if tech_stack else "Not detected"

        categories = contact.get("company_description", {})
        primary_framework = categories.get("frontend", "N/A")
        hosting = categories.get("hosting", "N/A")
        analytics = ", ".join(categories.get("analytics", [])) or "N/A"

        return [
            first,
            last,
            full_name,
            contact.get("title", contact.get("current_title", "N/A")),
            contact.get("email", "N/A"),
            "Yes" if contact.get("email_verified") else "No",
            contact.get("linkedin_url", "N/A"),
            contact.get("time_in_role", "N/A"),
            contact.get("location", "N/A"),
            (contact.get("bio_snippet") or contact.get("headline", ""))[:100],
            contact.get("company", contact.get("current_company", "N/A")),
            contact.get("domain", "N/A"),
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

        spreadsheet = self.client.create(sheet_name)
        worksheet = spreadsheet.sheet1

        worksheet.append_row(self._headers())
        for contact in contacts:
            worksheet.append_row(self._row(contact))

        worksheet.freeze(rows=1)

        spreadsheet.share("", perm_type="anyone", role="reader")

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
