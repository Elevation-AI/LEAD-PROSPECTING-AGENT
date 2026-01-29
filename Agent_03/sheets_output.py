"""
Sheets Output - Export Generated Emails to Google Sheets
=========================================================
Exports the generated emails to a Google Sheet for user review.
User can then copy-paste to send, or use as reference.

Part of Agent 03: Outreach Orchestration
"""

import sys
import os
from datetime import datetime
from typing import Dict, List

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
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.utils.helpers import setup_logger


class EmailSheetsExporter:
    """
    Exports generated emails to Google Sheets.

    Creates a formatted sheet with columns:
    - Recipient Name
    - Email Address
    - Company
    - Subject Line
    - Email Body
    - Personalization Used
    - Status (Draft/Sent)
    - Notes
    """

    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
    ]

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.credentials = None
        self.client = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google using OAuth"""
        token_path = os.path.join(PROJECT_ROOT, "config", "token.json")
        creds_path = os.path.join(PROJECT_ROOT, "config", "oauth-credentials.json")

        # Load existing token
        if os.path.exists(token_path):
            self.credentials = Credentials.from_authorized_user_file(token_path, self.SCOPES)

        # Refresh or get new token
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.logger.info("Refreshing expired credentials...")
                self.credentials.refresh(Request())
            else:
                if not os.path.exists(creds_path):
                    raise FileNotFoundError(
                        f"OAuth credentials not found at {creds_path}. "
                        "Please download from Google Cloud Console."
                    )
                self.logger.info("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, self.SCOPES)
                self.credentials = flow.run_local_server(port=0)

            # Save token
            with open(token_path, 'w') as f:
                f.write(self.credentials.to_json())
            self.logger.info("Credentials saved")

        self.client = gspread.authorize(self.credentials)
        self.logger.info("✅ Google Sheets authenticated")

    def export(self, emails: List[Dict], sheet_name: str = None) -> str:
        """
        Export generated emails to a new Google Sheet.

        Args:
            emails: List of email dictionaries from EmailGenerator
            sheet_name: Custom sheet name (optional)

        Returns:
            URL of the created Google Sheet
        """
        if not sheet_name:
            sheet_name = f"Outreach_Emails_{datetime.now():%Y%m%d_%H%M}"

        self.logger.info(f"Creating sheet: {sheet_name}")

        # Create new spreadsheet
        spreadsheet = self.client.create(sheet_name)
        worksheet = spreadsheet.sheet1
        worksheet.update_title("Email Drafts")

        # Define headers
        headers = [
            "Recipient Name",
            "Email Address",
            "Company",
            "Subject Line",
            "Email Body",
            "Personalization Used",
            "Tone",
            "CTA Type",
            "Generation Status",
            "Send Status",
            "Notes",
            "Generated At"
        ]

        # Prepare rows
        rows = [headers]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for email in emails:
            # Format personalization list
            personalization = email.get("personalization_used", [])
            if isinstance(personalization, list):
                personalization = ", ".join(personalization)

            row = [
                email.get("recipient_name", ""),
                email.get("recipient_email", ""),
                email.get("recipient_company", ""),
                email.get("subject_line", ""),
                email.get("body", ""),
                personalization,
                email.get("tone", "professional"),
                email.get("cta", "call"),
                email.get("generation_status", "unknown"),
                "Draft",  # Default status
                "",  # Notes - empty for user to fill
                timestamp
            ]
            rows.append(row)

        # Write all data
        worksheet.update(f'A1:L{len(rows)}', rows)

        # Format header row
        worksheet.format('A1:L1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
        })

        # Set column widths for readability
        self._set_column_widths(worksheet)

        # Freeze header row
        worksheet.freeze(rows=1)

        # Make sheet public (view only)
        spreadsheet.share('', perm_type='anyone', role='reader')

        sheet_url = spreadsheet.url
        self.logger.info(f"✅ Exported {len(emails)} emails to: {sheet_url}")

        return sheet_url

    def _set_column_widths(self, worksheet):
        """Set appropriate column widths for readability"""
        try:
            # Column widths in pixels
            widths = {
                'A': 150,  # Recipient Name
                'B': 200,  # Email Address
                'C': 150,  # Company
                'D': 250,  # Subject Line
                'E': 500,  # Email Body (wide)
                'F': 200,  # Personalization Used
                'G': 100,  # Tone
                'H': 100,  # CTA Type
                'I': 120,  # Generation Status
                'J': 100,  # Send Status
                'K': 150,  # Notes
                'L': 150   # Generated At
            }

            requests = []
            for i, (col, width) in enumerate(widths.items()):
                requests.append({
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': worksheet.id,
                            'dimension': 'COLUMNS',
                            'startIndex': i,
                            'endIndex': i + 1
                        },
                        'properties': {'pixelSize': width},
                        'fields': 'pixelSize'
                    }
                })

            worksheet.spreadsheet.batch_update({'requests': requests})
        except Exception as e:
            self.logger.warning(f"Could not set column widths: {e}")

    def append_emails(self, spreadsheet_url: str, emails: List[Dict]) -> int:
        """
        Append more emails to an existing sheet.

        Args:
            spreadsheet_url: URL of existing spreadsheet
            emails: List of new email dictionaries

        Returns:
            Number of emails appended
        """
        # Extract spreadsheet ID from URL
        spreadsheet_id = spreadsheet_url.split('/d/')[1].split('/')[0]

        spreadsheet = self.client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.sheet1

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows = []
        for email in emails:
            personalization = email.get("personalization_used", [])
            if isinstance(personalization, list):
                personalization = ", ".join(personalization)

            row = [
                email.get("recipient_name", ""),
                email.get("recipient_email", ""),
                email.get("recipient_company", ""),
                email.get("subject_line", ""),
                email.get("body", ""),
                personalization,
                email.get("tone", "professional"),
                email.get("cta", "call"),
                email.get("generation_status", "unknown"),
                "Draft",
                "",
                timestamp
            ]
            rows.append(row)

        # Append rows
        worksheet.append_rows(rows)

        self.logger.info(f"✅ Appended {len(emails)} emails to existing sheet")
        return len(emails)


# =============================================================================
# DRIVER CODE - TEST
# =============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📊 Email Sheets Exporter Test")
    print("=" * 60)

    # Sample generated emails (simulating EmailGenerator output)
    test_emails = [
        {
            "recipient_name": "Harold Dawson",
            "recipient_email": "harold@industrialelectricalco.com",
            "recipient_company": "Industrial Electrical Company",
            "subject_line": "Optimizing Operations at Industrial Electrical Company",
            "body": "As an operations manager with nearly a decade of experience at Industrial Electrical Company, Harold, you've likely identified areas where automation could significantly reduce manual work. Our team at TechSolutions Inc has helped similar operations teams reduce manual work by 40%. Would you be available for a quick 15-minute call to explore further?",
            "personalization_used": ["Name", "Job Title", "Company", "Years of experience"],
            "tone": "professional",
            "cta": "call",
            "generation_status": "success"
        },
        {
            "recipient_name": "Derek Sammataro",
            "recipient_email": "dereks@westportproperties.net",
            "recipient_company": "Westport Properties",
            "subject_line": "Streamlining Operations at Westport Properties",
            "body": "As a seasoned Director of Facilities Services with over 20 years of experience in self storage operations and commercial real estate, I'd love to discuss how TechSolutions Inc can help Westport Properties automate repetitive tasks. Would you be available for a quick 15-minute call?",
            "personalization_used": ["Name", "Job Title", "Company", "LinkedIn bio"],
            "tone": "professional",
            "cta": "call",
            "generation_status": "success"
        }
    ]

    # Export to Google Sheets
    print("\n📤 Exporting emails to Google Sheets...")

    exporter = EmailSheetsExporter()
    sheet_url = exporter.export(test_emails, "Test_Outreach_Emails")

    print("\n" + "=" * 60)
    print("✅ EXPORT COMPLETE!")
    print("=" * 60)
    print(f"\n📄 Google Sheet URL:")
    print(f"   {sheet_url}")
    print("\nColumns in the sheet:")
    print("   • Recipient Name, Email Address, Company")
    print("   • Subject Line, Email Body")
    print("   • Personalization Used, Tone, CTA Type")
    print("   • Generation Status, Send Status, Notes")
    print("   • Generated At")
    print("\n" + "=" * 60)
