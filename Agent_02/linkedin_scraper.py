"""
LinkedIn Scraper using PhantomBuster API (Agent S3 based)
========================================================
Correct for Phantoms that:
- Run successfully
- Store results as result.json in PhantomBuster S3
- Do NOT expose container outputs

This version matches the Phantom behavior you confirmed working.
"""

import requests
import json
import time
import os
from typing import Dict, Optional, List
from datetime import datetime
from dateutil import parser
import sys

import sys
import os

# Get the directory where main.py is located (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (lead-prospecting-agent)
project_root = os.path.dirname(current_dir)

# Add the project root to sys.path so 'src' can be found
if project_root not in sys.path:
    sys.path.insert(0, project_root)



sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logger
from config.settings import settings


class LinkedInScraper:
    """Fetch LinkedIn profile data from PhantomBuster agent S3 output"""

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.api_key = settings.PHANTOMBUSTER_API_KEY
        self.agent_id = settings.PHANTOMBUSTER_PHANTOM_ID
        self.base_url = "https://api.phantombuster.com/api/v2"

        if not self.api_key or not self.agent_id:
            raise ValueError(" PhantomBuster API key or Agent ID missing")

    # ----------------------------------------------------
    # Helpers
    # ----------------------------------------------------
    def _headers(self):
        return {
            "X-Phantombuster-Key": self.api_key,
            "Accept": "application/json",
        }

    # ----------------------------------------------------
    # Phantom Execution
    # ----------------------------------------------------
    def _launch_phantom(self, linkedin_url: str) -> bool:
        """Launch Phantom run"""
        url = f"{self.base_url}/agents/launch"

        payload = {
            "id": self.agent_id,
            "argument": {
                "sessionCookie": settings.LINKEDIN_SESSION_COOKIE,
                "spreadsheetUrl": linkedin_url,
                "numberOfProfiles": 1
            }
        }

        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
            if resp.status_code == 200:
                self.logger.info(" Phantom launched")
                return True
            self.logger.error(f" Launch failed: {resp.text}")
            return False
        except Exception as e:
            self.logger.error(f" Launch error: {e}")
            return False

    def _wait_for_completion(self, max_wait: int = 180) -> bool:
        """Wait until Phantom finishes"""
        url = f"{self.base_url}/agents/fetch?id={self.agent_id}"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=20)
                if resp.status_code == 200:
                    status = resp.json().get("status")
                    if status == "idle":
                        self.logger.info(" Phantom completed")
                        return True
                time.sleep(5)
            except Exception:
                time.sleep(5)

        self.logger.error(" Phantom timeout")
        return False

    # ----------------------------------------------------
    # S3 RESULT FETCH (THIS IS THE KEY FIX)
    # ----------------------------------------------------
    def _download_result_json(self) -> Optional[List[Dict]]:
        """
        Fetch result.json directly from PhantomBuster S3 storage
        """
        url = f"{self.base_url}/agents/fetch?id={self.agent_id}"

        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            if resp.status_code != 200:
                self.logger.error(" Failed to fetch agent metadata")
                return None

            agent = resp.json()
            org_folder = agent.get("orgS3Folder")
            s3_folder = agent.get("s3Folder")

            if not org_folder or not s3_folder:
                self.logger.error(" Missing S3 folder paths")
                return None

            result_url = f"https://phantombuster.s3.amazonaws.com/{org_folder}/{s3_folder}/result.json"
            self.logger.info(f" Downloading {result_url}")

            data_resp = requests.get(result_url, timeout=30)
            if data_resp.status_code != 200:
                self.logger.error(" result.json not found")
                return None

            data = data_resp.json()
            self.logger.info(f" Downloaded {len(data)} profile(s)")
            return data

        except Exception as e:
            self.logger.error(f" S3 download error: {e}")
            return None

    # ----------------------------------------------------
    # Parsing Helpers
    # ----------------------------------------------------
    def _calculate_time_in_role(self, date_range: str) -> str:
        """
        Convert 'Jun 2025 - Present' → 'X yr Y mo'
        """
        try:
            if not date_range or "Present" not in date_range:
                return "Unknown"

            start_str = date_range.split("-")[0].strip()
            start = parser.parse(start_str, fuzzy=True)
            now = datetime.now()

            years = now.year - start.year
            months = now.month - start.month
            if months < 0:
                years -= 1
                months += 12

            return f"{years} yr {months} mo" if years > 0 else f"{months} mo"
        except Exception:
            return "Unknown"

    def _parse_profile(self, raw: Dict) -> Dict:
        return {
            "full_name": f"{raw.get('firstName','')} {raw.get('lastName','')}".strip(),
            "headline": raw.get("linkedinHeadline", "N/A"),
            "bio_snippet": (raw.get("linkedinDescription") or "")[:200],
            "location": raw.get("location") or raw.get("linkedinJobLocation", "Unknown"),
            "current_title": raw.get("linkedinJobTitle", "Unknown"),
            "current_company": raw.get("companyName", "Unknown"),
            "time_in_role": self._calculate_time_in_role(raw.get("linkedinJobDateRange")),
            "linkedin_url": raw.get("profileUrl"),
            "connections": raw.get("linkedinConnectionsCount", 0)
        }

    # ----------------------------------------------------
    # Public API
    # ----------------------------------------------------
    def scrape_profile(self, linkedin_url: str) -> Optional[Dict]:
        if linkedin_url.startswith('http://'):
            linkedin_url = linkedin_url.replace('http://', 'https://')
    
        self.logger.info(f" Scraping: {linkedin_url}")

        if not self._launch_phantom(linkedin_url):
            return None

        # PhantomBuster runs async — wait fixed time
        self.logger.info(" Waiting for Phantom to finish (90s)...")
        time.sleep(90)

        # Try fetching result.json
        results = self._download_result_json()
        if not results:
            self.logger.warning(" No results found, retrying once...")
            time.sleep(30)
            results = self._download_result_json()

        if not results:
            self.logger.error(" Phantom finished but no data produced")
            return None

        parsed = self._parse_profile(results[-1])
        self.logger.info(f" Success: {parsed['full_name']}")
        return parsed



# ----------------------------------------------------
# TEST
# ----------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" LinkedIn Profile Scraper (PhantomBuster S3)")
    print("=" * 60)

    scraper = LinkedInScraper()
    test_url = "http://www.linkedin.com/in/naikkrish/"

    result = scraper.scrape_profile(test_url)

    if result:
        print("\n SUCCESS")
        for k, v in result.items():
            print(f"{k:18}: {v}")
    else:
        print("\n FAILED")

    print("\n" + "=" * 60)
