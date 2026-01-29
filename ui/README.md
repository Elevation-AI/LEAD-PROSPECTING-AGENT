# Agent01 Interactive UI

**Real-time lead prospecting pipeline with integrated ICP customization**

## Overview

This is a fully integrated web UI that runs the complete Agent01 pipeline in real-time. Unlike the previous version that only displayed JSON files, this version:

✅ **Takes company URL as input**
✅ **Runs the full pipeline interactively**
✅ **Includes ICP customization interface** (replaces get_user_overrides from command line)
✅ **Step-by-step workflow with "click to proceed"**
✅ **Clean, simple, and attractive design**

## Features

### 🎯 Step 1: Enter URL
- Input company website URL
- Real-time scraping

### 🤖 Step 2: Generate ICP
- AI-powered ICP generation using Groq
- Auto-display of generated ICP

### ✏️ Step 3: Customize ICP
**This replaces the `get_user_overrides()` function!**

Edit these fields:
- **Countries** - Add/remove countries with tags (e.g., USA, India, Canada)
- **Regions/States** - Add/remove regions (e.g., CA, TX, Delhi)
- **Customer Industries** - Edit industry text
- **Target Buyers** - Add/remove buyer personas

### 🔍 Step 4: Find Prospects
- Automatically finds matching companies
- Shows: name, domain, why_good_fit
- Displays count of prospects found

### 📧 Step 5: Enrich Contacts
- Apollo API integration
- Option to unlock emails (costs credits)
- Shows: name, title, email, LinkedIn, location, headline
- Auto-saves to output folder

## Installation

```bash
cd ui
pip install flask
```

## Usage

1. **Start the server:**
   ```bash
   python app.py
   ```

2. **Open browser:**
   ```
   http://localhost:5000
   ```

3. **Enter a company URL and follow the steps!**

## Design Philosophy

- **Simple & Clean** - No overwhelming colors, just professional blue/gray
- **Step-by-step** - Clear progress indicator
- **Click to proceed** - You control when to move forward
- **Integrated** - No need to run main.py separately
- **Real-time** - Watch the pipeline execute live

## Data Filtering

The UI automatically filters output to show only relevant fields:

### ICP Section
✅ Shows: what_they_sell, customer_industry, company_size, target_buyers, characteristics, geography
❌ Hides: pain_points_solved, avoid_company_types

### Prospects Section
✅ Shows: name, domain, why_good_fit
❌ Hides: source, confidence_score

### Enrichment Section
✅ Shows: company_name, domain, contacts (name, title, email, linkedin_url, location, headline)
❌ Hides: Other Apollo metadata

## Output

Results are automatically saved to `output/` folder in JSON format, just like running main.py.

## Comparison to CLI Version

| Feature | CLI (main.py) | Web UI |
|---------|--------------|--------|
| Enter URL | ✅ Command line input | ✅ Web form |
| ICP Customization | ✅ Terminal prompts | ✅ Web interface with tags |
| Step-by-step | ✅ Sequential | ✅ Visual progress |
| Output Format | JSON file | JSON file + Beautiful display |
| User Experience | Terminal | Modern web interface |

## Technical Details

- **Backend**: Flask
- **Frontend**: Vanilla JavaScript (no frameworks needed)
- **Styling**: Custom CSS (no external CSS libraries)
- **API**: RESTful endpoints for each pipeline step
- **Session Management**: Server-side session storage

## Troubleshooting

**Issue: "Invalid session"**
- Solution: Start over from Step 1

**Issue: Port 5000 already in use**
- Solution: Change port in app.py line 312

**Issue: Scraping fails**
- Solution: Check if URL is accessible and has enough content

**Issue: Apollo enrichment fails**
- Solution: Verify Apollo API key in config/settings.py

## File Structure

```
ui/
├── app.py                  # Flask backend with full pipeline integration
├── templates/
│   └── index.html         # Interactive UI with step-by-step workflow
├── requirements.txt
├── start_ui.bat
└── README.md
```

## Dependencies

- Flask (web framework)
- All Agent01 dependencies (from parent project)

---

**Happy Prospecting! 🎯**
