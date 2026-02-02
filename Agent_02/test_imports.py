"""
Test Imports for Pipeline
==========================
Verifies all modules can be imported correctly.
Run this first to check your setup.
"""

import sys
import os

# Setup path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_imports():
    """Test all required imports"""
    print("\n" + "=" * 60)
    print("🔍 TESTING IMPORTS")
    print("=" * 60)

    results = []

    # Agent 01 imports
    print("\n📦 Agent 01 Modules (src/):")

    try:
        from src.scraper.website_scraper import WebsiteScraper
        print("   ✅ WebsiteScraper")
        results.append(("WebsiteScraper", True))
    except Exception as e:
        print(f"   ❌ WebsiteScraper: {e}")
        results.append(("WebsiteScraper", False))

    try:
        from src.icp.icp_generator import ICPGenerator
        print("   ✅ ICPGenerator")
        results.append(("ICPGenerator", True))
    except Exception as e:
        print(f"   ❌ ICPGenerator: {e}")
        results.append(("ICPGenerator", False))

    try:
        from src.search.company_finder import ProspectFinder
        print("   ✅ ProspectFinder")
        results.append(("ProspectFinder", True))
    except Exception as e:
        print(f"   ❌ ProspectFinder: {e}")
        results.append(("ProspectFinder", False))

    try:
        from src.enrichment.apollo_enricher import ApolloEnricher
        print("   ✅ ApolloEnricher")
        results.append(("ApolloEnricher", True))
    except Exception as e:
        print(f"   ❌ ApolloEnricher: {e}")
        results.append(("ApolloEnricher", False))

    try:
        from src.utils.helpers import validate_url, setup_logger
        print("   ✅ helpers (validate_url, setup_logger)")
        results.append(("helpers", True))
    except Exception as e:
        print(f"   ❌ helpers: {e}")
        results.append(("helpers", False))

    # Agent 01 Input Modules
    print("\n📦 Agent 01 Input Modules (src/input/):")

    try:
        from src.input.pdf_extractor import PDFExtractor
        print("   ✅ PDFExtractor")
        results.append(("PDFExtractor", True))
    except Exception as e:
        print(f"   ❌ PDFExtractor: {e}")
        results.append(("PDFExtractor", False))

    try:
        from src.input.raw_text_handler import RawTextHandler
        print("   ✅ RawTextHandler")
        results.append(("RawTextHandler", True))
    except Exception as e:
        print(f"   ❌ RawTextHandler: {e}")
        results.append(("RawTextHandler", False))

    try:
        from src.input.content_aggregator import ContentAggregator
        print("   ✅ ContentAggregator")
        results.append(("ContentAggregator", True))
    except Exception as e:
        print(f"   ❌ ContentAggregator: {e}")
        results.append(("ContentAggregator", False))

    # Agent 02 imports
    print("\n📦 Agent 02 Modules (Agent_02/):")

    try:
        from deep_enricher import DeepEnricher
        print("   ✅ DeepEnricher")
        results.append(("DeepEnricher", True))
    except Exception as e:
        print(f"   ❌ DeepEnricher: {e}")
        results.append(("DeepEnricher", False))

    try:
        from sheets_exporter import SheetsExporterOAuth
        print("   ✅ SheetsExporterOAuth")
        results.append(("SheetsExporterOAuth", True))
    except Exception as e:
        print(f"   ❌ SheetsExporterOAuth: {e}")
        results.append(("SheetsExporterOAuth", False))

    try:
        from linkedin_scraper import LinkedInScraper
        print("   ✅ LinkedInScraper")
        results.append(("LinkedInScraper", True))
    except Exception as e:
        print(f"   ❌ LinkedInScraper: {e}")
        results.append(("LinkedInScraper", False))

    try:
        from tech_stack_detector import TechStackDetector
        print("   ✅ TechStackDetector")
        results.append(("TechStackDetector", True))
    except Exception as e:
        print(f"   ❌ TechStackDetector: {e}")
        results.append(("TechStackDetector", False))

    # Config imports
    print("\n📦 Config:")

    try:
        from config.settings import settings
        print("   ✅ settings")
        results.append(("settings", True))
    except Exception as e:
        print(f"   ❌ settings: {e}")
        results.append(("settings", False))

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    if passed == total:
        print(f"✅ ALL IMPORTS PASSED ({passed}/{total})")
        print("\n🚀 Ready to run pipeline.py!")
    else:
        print(f"⚠️  SOME IMPORTS FAILED ({passed}/{total})")
        print("\nFailed modules:")
        for name, ok in results:
            if not ok:
                print(f"   - {name}")

    print("=" * 60 + "\n")

    return passed == total


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
