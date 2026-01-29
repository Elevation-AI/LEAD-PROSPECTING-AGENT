import sys
import os
import json
from datetime import datetime

# ---------------------------------------------------
# PATH SETUP (UNCHANGED)
# ---------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ---------------------------------------------------
# IMPORTS
# ---------------------------------------------------
from src.scraper.website_scraper import WebsiteScraper
from src.icp.icp_generator import ICPGenerator
from src.search.company_finder import ProspectFinder
from src.enrichment.apollo_enricher import ApolloEnricher
from src.utils.helpers import validate_url

#  NEW IMPORTS (INPUT LAYER)
from src.input.pdf_extractor import PDFExtractor
from src.input.raw_text_handler import RawTextHandler
from src.input.content_aggregator import ContentAggregator


# ---------------------------------------------------
# SAVE OUTPUT (UNCHANGED)
# ---------------------------------------------------
def save_full_output(url: str, icp: dict, competitors: list, enriched: list, output_dir: str = "output"):
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_slug = (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
        .split(".")[0]
        if url else "custom_input"
    )

    full_output = {
        "generated_at": datetime.now().isoformat(),
        "source": url if url else "multi-input",
        "icp": icp,
        "prospects_found": len(competitors),
        "prospects": competitors,
        "enriched_contacts": enriched,
        "total_contacts": sum(len(c.get("contacts", [])) for c in enriched)
    }

    filename = f"{company_slug}_output_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=4, ensure_ascii=False)

    print(f"\n All output saved to: {filepath}")
    return filepath


# ---------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------
def main():
    print("\n LEAD PROSPECTING — MULTI-INPUT PIPELINE")
    print("=============================================\n")

    contexts = []

    # ---------------------------------------------------
    # 1️⃣ WEBSITE INPUT (OPTIONAL)
    # ---------------------------------------------------
    url = input("Enter company website URL (or press Enter to skip): ").strip()
    if url:
        if not validate_url(url):
            print(" Invalid URL format. Example: https://asana.com")
            return

        print("\n Scraping website content...")
        scraper = WebsiteScraper()
        scraped = scraper.scrape_website(url)

        if scraped and len(scraped.get("combined_text", "")) > 200:
            contexts.append({
                "source": "website",
                "content": scraped["combined_text"]
            })
            print(" Website content added.")
        else:
            print(" Website content could not be used.")

    # ---------------------------------------------------
    # 2️⃣ PDF INPUT (OPTIONAL)
    # ---------------------------------------------------
    pdf_path = input("Enter PDF file path (or press Enter to skip): ").strip()
    if pdf_path:
        try:
            pdf_extractor = PDFExtractor()
            pdf_context = pdf_extractor.extract_text(pdf_path)
            contexts.append(pdf_context)
            print(" PDF content added.")
        except Exception as e:
            print(" PDF skipped:", e)

    # ---------------------------------------------------
    # 3️⃣ RAW TEXT INPUT (OPTIONAL)
    # ---------------------------------------------------
    raw_text = input("Paste raw text (or press Enter to skip): ").strip()
    if raw_text:
        try:
            raw_handler = RawTextHandler()
            raw_context = raw_handler.process(raw_text)
            contexts.append(raw_context)
            print(" Raw text added.")
        except Exception as e:
            print(" Raw text skipped:", e)

    if not contexts:
        print("\n No valid input provided. Exiting.")
        return

    # ---------------------------------------------------
    # 4️⃣ AGGREGATE CONTEXT (NEW CORE STEP)
    # ---------------------------------------------------
    aggregator = ContentAggregator()
    final_context_text = aggregator.aggregate(contexts)

    print(f"\n Unified company context length: {len(final_context_text)} characters")

    # ---------------------------------------------------
    # 5️⃣ GENERATE ICP
    # ---------------------------------------------------
    print("\n Generating ICP using LLM...")
    icp_gen = ICPGenerator()

    try:
        icp = icp_gen.generate_icp(final_context_text)

        print("\n ICP Generated Successfully:\n")
        print(json.dumps(icp, indent=4))

        # Optional user overrides (existing feature)
        icp = icp_gen.get_user_overrides(icp)

        print("\n FINAL ICP (After User Customization):\n")
        print(json.dumps(icp, indent=4))

    except Exception as e:
        print(f" ICP generation failed: {e}")
        return

    # ---------------------------------------------------
    # 6️⃣ FIND PROSPECT COMPANIES
    # ---------------------------------------------------
    print("\n Discovering PROSPECT companies...")
    finder = ProspectFinder()
    competitors = finder.find_prospects(icp)

    if not competitors:
        print(" No prospect companies found.")
        return

    print("\n PROSPECTS Found:")
    for c in competitors:
        print(f"- {c['name']} ({c['domain']}) — Confidence: {c['confidence']:.2f}")

    # ---------------------------------------------------
    # 7️⃣ ENRICH CONTACTS (OPTIONAL)
    # ---------------------------------------------------
    print("\n Enriching PROSPECTS using Apollo API...")
    unlock = input("Unlock emails? (costs credits) [yes/no]: ").lower() == "yes"

    enricher = ApolloEnricher(unlock_emails=unlock)
    enriched = enricher.enrich(competitors, icp)

    print("\n Apollo Enrichment Results:\n")
    print(json.dumps(enriched, indent=4))

    # ---------------------------------------------------
    # 8️⃣ SAVE OUTPUT
    # ---------------------------------------------------
    save_full_output(
        url,
        icp,
        competitors,
        enriched,
        os.path.join(project_root, "output")
    )

    print("\n FULL PIPELINE COMPLETE!\n")


# ---------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------
if __name__ == "__main__":
    main()
