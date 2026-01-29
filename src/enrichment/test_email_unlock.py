import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.enrichment.apollo_enricher import ApolloEnricher

# Enable email unlocking (will use credits!)
enricher = ApolloEnricher(unlock_emails=True)

# Check credit balance first
print("\n💳 Checking Apollo Credits...")
enricher.check_credit_balance()

# Ask for confirmation
response = input("\n⚠️  This will use ~5 Apollo credits. Continue? (yes/no): ")

if response.lower() != 'yes':
    print("❌ Cancelled")
    exit()

# Test with one company
test_icp = {
    "industry": "SaaS",
    "target_buyers": ["VP Engineering", "CTO"]
}

test_companies = [
    {"name": "Shopify", "domain": "shopify.com"}
]

print("\n🔓 Unlocking emails...")
result = enricher.enrich(test_companies, test_icp)

# Print results
print("\n" + "="*60)
print("📊 RESULTS WITH REAL EMAILS:")
print("="*60)

for company in result:
    print(f"\n🏢 Company: {company['company']}")
    print(f"🌐 Domain: {company['domain']}")
    print(f"👥 Contacts Found: {len(company['contacts'])}")
    
    for i, contact in enumerate(company['contacts'], 1):
        print(f"\n  #{i} Contact:")
        print(f"     Name: {contact['name']}")
        print(f"     Title: {contact['title']}")
        print(f"     📧 Email: {contact['email']}")
        print(f"     ✅ Verified: {contact['email_verified']}")
        print(f"     📞 Phone: {contact['phone'] or 'N/A'}")
        print(f"     🔗 LinkedIn: {contact['linkedin_url']}")
        print(f"     📍 Location: {contact['location']}")

print(f"\n💰 Total Credits Used: {enricher.credits_used}")