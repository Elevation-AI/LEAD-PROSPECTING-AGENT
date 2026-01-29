"""
Main Company Search Pipeline
=============================
Takes user's company URL → Scrapes → Generates ICP → Finds Prospects
"""

import sys
import os
import json

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.scraper.website_scraper import WebsiteScraper
from src.icp.icp_generator import ICPGenerator
from src.search.company_finder import ProspectFinder
from src.utils.helpers import validate_url

def main():
    print("\n Lead Prospecting — Full Pipeline Test")
    print("=" * 60 + "\n")

    # Step 1: Take URL from user
    url = input("Enter company website URL: ").strip()
    
    if not validate_url(url):
        print(" Invalid URL format. Example: https://junglescout.com")
        return

    print(f"\n Processing: {url}")
    print("-" * 60)

    # Step 2: Website Scraping
    print("\n Scraping website content...")
    scraper = WebsiteScraper()
    
    try:
        scraped = scraper.scrape_website(url)
    except Exception as e:
        print(f" Scraping failed: {e}")
        return

    if not scraped or len(scraped.get("combined_text", "")) < 200:
        print(" Could not extract enough content from website.")
        print(f"   Got {len(scraped.get('combined_text', ''))} characters (need at least 200)")
        return

    print(f" Scraping successful! Extracted {scraped['content_length']:,} characters.")
    print(f"   Method used: {scraped.get('method', 'unknown')}")

    # Step 3: ICP Generation
    print("\n Generating ICP using LLM...")
    icp_gen = ICPGenerator()
    
    try:
        icp = icp_gen.generate_icp(scraped["combined_text"])
        
        if not icp:
            print(" ICP generation returned empty result")
            return
            
        print("\n ICP Generated Successfully:\n")
        print(json.dumps(icp, indent=4))

        #  CHANGE 2: Ask user for overrides (NEW!)
        icp = icp_gen.get_user_overrides(icp)
        
        print("\n FINAL ICP (After User Customization):\n")
        print(json.dumps(icp, indent=4))
        
    except Exception as e:
        print(f" ICP generation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Prospect Finding (NOT competitor finding)
    print("\n Discovering Prospect Companies (potential customers)...")
    print("   Note: Finding companies that would BUY this product, not competitors")
    
    finder = ProspectFinder()

    try:
        prospects = finder.find_prospects(icp)
    except Exception as e:
        print(f" Prospect finding failed: {e}")
        import traceback
        traceback.print_exc()
        return

    if not prospects:
        print("  No prospect companies found.")
        print("   This could mean:")
        print("   - The ICP is too specific")
        print("   - Google API rate limit reached")
        print("   - LLM returned unexpected format")
        return

    print(f"\n Found {len(prospects)} Prospects:\n")
    
    for i, prospect in enumerate(prospects, 1):
        print(f"{i}. {prospect['name']} ({prospect['domain']})")
        print(f"   Confidence: {prospect['confidence']:.0%}")
        print(f"   Why good fit: {prospect['why_good_fit']}")
        print()

    # Summary
    print("=" * 60)
    print(" Pipeline Complete!")
    print(f"   • Scraped: {scraped['content_length']:,} characters")
    print(f"   • Generated ICP for: {icp.get('customer_industry', 'N/A')}")
    print(f"   • Found: {len(prospects)} prospect companies")
    print("=" * 60 + "\n")

    """# Optional: Save results
    save = input(" Save results to file? (yes/no): ").strip().lower()
    
    if save == 'yes':
        output = {
            "company_url": url,
            "icp": icp,
            "prospects": prospects,
            "scrape_stats": {
                "characters": scraped['content_length'],
                "method": scraped.get('method', 'unknown')
            }
        }
        
        filename = f"prospects_{url.split('//')[1].split('/')[0].replace('www.', '')}.json"
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f" Results saved to: {filename}")"""

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrupted by user")
    except Exception as e:
        print(f"\n Unexpected error: {e}")
        import traceback
        traceback.print_exc()