# Agent 01 + Agent 02 Combined Pipeline

## Overview

This is a professional, modular integration of Agent 01 and Agent 02 that:
- **Imports existing modules** - No code duplication
- **Clean architecture** - Separate steps, easy to customize
- **Multiple interfaces** - CLI, programmatic API, quick runner

## Files

| File | Purpose |
|------|---------|
| `pipeline.py` | Main pipeline class with all steps |
| `run_pipeline.py` | Quick CLI runner with arguments |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        pipeline.py                              │
│                    LeadProspectingPipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   AGENT 01 (imported from src/)                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐        │
│   │WebsiteScraper│→│ICPGenerator │→│ ProspectFinder  │        │
│   │(src/scraper) │  │(src/icp)    │  │ (src/search)    │        │
│   └─────────────┘  └─────────────┘  └────────┬────────┘        │
│                                               ↓                 │
│                                    ┌─────────────────┐          │
│                                    │ ApolloEnricher  │          │
│                                    │(src/enrichment) │          │
│                                    └────────┬────────┘          │
│                                              ↓                  │
│   AGENT 02 (imported from Agent_02/)                            │
│   ┌─────────────┐  ┌─────────────────────┐                     │
│   │DeepEnricher │→│ SheetsExporterOAuth │                     │
│   │(Agent_02)   │  │ (Agent_02)          │                     │
│   └─────────────┘  └─────────────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Usage

### Option 1: Interactive CLI

```bash
cd Agent_02
python pipeline.py
```

This will prompt you for:
- Company URL
- Whether to unlock emails (Apollo credits)
- Whether to customize ICP
- Whether to export to Google Sheets

### Option 2: Quick Runner (with arguments)

```bash
# Basic usage
python run_pipeline.py https://stripe.com

# With email unlocking
python run_pipeline.py https://stripe.com --unlock-emails

# Skip ICP customization (automated)
python run_pipeline.py https://stripe.com --skip-icp-customization

# Skip Google Sheets export
python run_pipeline.py https://stripe.com --no-sheets

# Combine options
python run_pipeline.py https://stripe.com --unlock-emails --skip-icp-customization
```

### Option 3: Programmatic API

```python
from pipeline import LeadProspectingPipeline

# Initialize pipeline
pipeline = LeadProspectingPipeline()

# Run full pipeline
result = pipeline.run(
    url="https://stripe.com",
    unlock_emails=True,
    allow_icp_customization=False,  # Automated
    export_to_sheets=True,
    save_local=True
)

# Check result
if result["success"]:
    print(f"Found {result['prospects_count']} prospects")
    print(f"Enriched {result['contacts_count']} contacts")
    print(f"Google Sheet: {result['google_sheet_url']}")
else:
    print(f"Error: {result['error']}")
```

### Option 4: Step-by-Step Control

```python
from pipeline import LeadProspectingPipeline

pipeline = LeadProspectingPipeline()

# Run steps individually
pipeline.scrape_website("https://stripe.com")
pipeline.generate_icp(allow_customization=True)
pipeline.find_prospects()
pipeline.enrich_with_apollo(unlock_emails=False)

# Agent 02 steps
pipeline.deep_enrich()
pipeline.export_to_sheets()

# Access data at any step
print(pipeline.icp)
print(pipeline.prospects)
print(pipeline.deep_enriched)
print(pipeline.sheet_url)
```

## Pipeline Steps

| Step | Agent | Method | Description |
|------|-------|--------|-------------|
| 1 | 01 | `scrape_website()` | Scrape company website content |
| 2 | 01 | `generate_icp()` | Generate ICP using LLM |
| 3 | 01 | `find_prospects()` | Find matching prospect companies |
| 4 | 01 | `enrich_with_apollo()` | Get emails/contacts via Apollo |
| 5 | 02 | `deep_enrich()` | Add LinkedIn + Tech Stack data |
| 6 | 02 | `export_to_sheets()` | Export to Google Sheets |

## Output

### Google Sheets (Columns)
- First Name, Last Name, Full Name
- Job Title, Email, Email Verified
- LinkedIn URL, Time in Role, Location
- Bio Snippet, Company, Domain
- Tech Stack, Framework, Hosting, Analytics
- Enrichment Date

### Local JSON (`output/` folder)
```json
{
    "generated_at": "2025-01-21T...",
    "source_url": "https://stripe.com",
    "pipeline_version": "Agent01 + Agent02",
    "icp": {...},
    "prospects": [...],
    "apollo_enriched": [...],
    "deep_enriched": [...],
    "google_sheet_url": "https://docs.google.com/..."
}
```

## Modules Used (No Code Duplication!)

### From `src/` (Agent 01)
- `src.scraper.website_scraper.WebsiteScraper`
- `src.icp.icp_generator.ICPGenerator`
- `src.search.company_finder.ProspectFinder`
- `src.enrichment.apollo_enricher.ApolloEnricher`
- `src.utils.helpers`

### From `Agent_02/`
- `deep_enricher.DeepEnricher`
- `sheets_exporter.SheetsExporterOAuth`

## Requirements

Ensure these environment variables are set (`.env` file):
```
# Agent 01
GROQ_API_KEY=...
GOOGLE_SEARCH_API_KEY=...
GOOGLE_SEARCH_ENGINE_ID=...
APOLLO_API_KEY=...

# Agent 02
PHANTOMBUSTER_API_KEY=...
PHANTOMBUSTER_PHANTOM_ID=...
LINKEDIN_SESSION_COOKIE=...
FIRECRAWL_API_KEY=...
```

## Comparison with Previous Approach

| Aspect | Old (main_combined.py) | New (pipeline.py) |
|--------|------------------------|-------------------|
| Code | Copy-pasted classes | Clean imports |
| Modularity | Single file, all logic | Separate steps |
| API | CLI only | CLI + Programmatic |
| Maintenance | Hard to update | Update src/ modules |
| Testing | Difficult | Easy step-by-step |
| Customization | Edit file | Pass parameters |

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the Agent_02 directory
cd Agent_02
python pipeline.py
```

### Module Not Found
```bash
# Install dependencies
pip install gspread google-auth-oauthlib firecrawl groq
```

### API Errors
- Check `.env` file for correct API keys
- Ensure OAuth credentials are in `config/oauth-credentials.json`
- Run `python sheets_exporter.py` first to authorize Google
