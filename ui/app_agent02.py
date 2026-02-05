"""
Flask Blueprint for Agent 02 - Deep Enrichment
================================================
Handles:
  Step 6: Select contacts for LinkedIn scraping + start deep enrichment
  Step 7: View deep enrichment results + Google Sheets export
"""

import sys
import os
import threading
import time
from pathlib import Path
from flask import Blueprint, request, jsonify

# Add project root and Agent_02 directory to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
agent02_dir = str(PROJECT_ROOT / "Agent_02")
if agent02_dir not in sys.path:
    sys.path.insert(0, agent02_dir)

from tech_stack_detector import TechStackDetector
from linkedin_scraper import LinkedInScraper
from sheets_exporter import SheetsExporterOAuth

agent02_bp = Blueprint('agent02', __name__)

# Background task tracking
enrichment_tasks = {}


def _flatten_agent01_contacts(session_data):
    """
    Flatten Agent 01 enriched contacts into a flat list suitable for Agent 02.
    Agent 01 stores contacts grouped by company:
      [{"company": ..., "domain": ..., "contacts": [...]}, ...]
    Agent 02 expects a flat list:
      [{"name": ..., "title": ..., "email": ..., "domain": ..., "company": ...}, ...]
    """
    enriched = session_data.get('enriched', [])
    flat_contacts = []
    for company in enriched:
        company_name = company.get('company', company.get('company_name', ''))
        domain = company.get('domain', '')
        for contact in company.get('contacts', []):
            flat = contact.copy()
            flat['company'] = company_name
            flat['domain'] = domain
            flat_contacts.append(flat)
    return flat_contacts


def _run_deep_enrichment(task_id, contacts, linkedin_indices, skip_linkedin, session_data_ref):
    """
    Background worker for deep enrichment.
    Updates enrichment_tasks[task_id] with progress.
    """
    task = enrichment_tasks[task_id]
    task['status'] = 'running'

    try:
        # --- Phase 1: Tech stack detection for all unique domains ---
        task['phase'] = 'tech_stack'
        tech_detector = TechStackDetector()
        unique_domains = list({c.get('domain') for c in contacts if c.get('domain')})
        task['tech_total'] = len(unique_domains)
        task['tech_completed'] = 0

        tech_cache = {}
        for domain in unique_domains:
            task['tech_current'] = domain
            try:
                tech_data = tech_detector.detect(f"https://{domain}")
                if tech_data:
                    tech_cache[domain] = tech_data
            except Exception as e:
                tech_cache[domain] = {"domain": domain, "tech_stack": [], "categories": {}}
            task['tech_completed'] += 1
            time.sleep(2)

        # --- Phase 2: LinkedIn scraping for selected contacts only ---
        task['phase'] = 'linkedin'
        linkedin_results = {}

        if not skip_linkedin and linkedin_indices:
            linkedin_scraper = LinkedInScraper()
            task['linkedin_total'] = len(linkedin_indices)
            task['linkedin_completed'] = 0

            for idx in linkedin_indices:
                if idx < len(contacts):
                    contact = contacts[idx]
                    task['linkedin_current'] = contact.get('name', 'Unknown')
                    linkedin_url = contact.get('linkedin_url')
                    if linkedin_url:
                        try:
                            profile_data = linkedin_scraper.scrape_profile(linkedin_url)
                            if profile_data:
                                linkedin_results[idx] = profile_data
                        except Exception:
                            pass
                    task['linkedin_completed'] += 1
                    time.sleep(1)
        else:
            task['linkedin_total'] = 0
            task['linkedin_completed'] = 0

        # --- Phase 3: Merge results ---
        task['phase'] = 'merging'
        enriched_contacts = []
        for i, contact in enumerate(contacts):
            enriched = contact.copy()

            # Add LinkedIn data if available
            if i in linkedin_results:
                enriched.update(linkedin_results[i])

            # Add tech stack data
            domain = contact.get('domain')
            if domain and domain in tech_cache:
                tech_data = tech_cache[domain]
                enriched['company_tech_stack'] = tech_data.get('tech_stack', [])
                enriched['company_description'] = tech_data.get('categories', {})
                enriched['about_company'] = tech_data.get('company_summary', 'N/A')

            enriched_contacts.append(enriched)

        # Store in session
        session_data_ref['deep_enriched_contacts'] = enriched_contacts
        task['result'] = enriched_contacts
        task['status'] = 'completed'
        task['phase'] = 'done'

    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)


@agent02_bp.route('/api/agent02/get-contacts', methods=['POST'])
def get_contacts_for_selection():
    """
    Return the flat contact list from Agent 01 for the selection UI.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    flat_contacts = _flatten_agent01_contacts(session_data[session_id])

    if not flat_contacts:
        return jsonify({"error": "No enriched contacts from Agent 01. Complete Step 5 first."}), 400

    contacts_display = []
    for i, c in enumerate(flat_contacts):
        contacts_display.append({
            "index": i,
            "name": c.get('name', 'Unknown'),
            "title": c.get('title', 'N/A'),
            "company": c.get('company', 'N/A'),
            "domain": c.get('domain', ''),
            "linkedin_url": c.get('linkedin_url', ''),
            "has_linkedin": bool(c.get('linkedin_url'))
        })

    # Store flat contacts in session for later use
    session_data[session_id]['flat_contacts'] = flat_contacts

    return jsonify({
        "success": True,
        "contacts": contacts_display,
        "total": len(contacts_display)
    })


@agent02_bp.route('/api/agent02/start-enrichment', methods=['POST'])
def start_deep_enrichment():
    """
    Start deep enrichment in background thread.
    Accepts selected LinkedIn indices and config.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')
    linkedin_indices = data.get('linkedin_indices', [])
    skip_linkedin = data.get('skip_linkedin', False)

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    sess = session_data[session_id]
    flat_contacts = sess.get('flat_contacts')

    if not flat_contacts:
        flat_contacts = _flatten_agent01_contacts(sess)
        sess['flat_contacts'] = flat_contacts

    if not flat_contacts:
        return jsonify({"error": "No contacts available for enrichment"}), 400

    # Create task
    task_id = f"{session_id}_agent02"
    enrichment_tasks[task_id] = {
        'status': 'starting',
        'phase': 'init',
        'tech_total': 0,
        'tech_completed': 0,
        'tech_current': '',
        'linkedin_total': 0,
        'linkedin_completed': 0,
        'linkedin_current': '',
        'result': None,
        'error': None
    }

    # Start background thread
    thread = threading.Thread(
        target=_run_deep_enrichment,
        args=(task_id, flat_contacts, linkedin_indices, skip_linkedin, sess),
        daemon=True
    )
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Deep enrichment started"
    })


@agent02_bp.route('/api/agent02/enrichment-status/<task_id>', methods=['GET'])
def get_enrichment_status(task_id):
    """
    Poll endpoint for enrichment progress.
    """
    if task_id not in enrichment_tasks:
        return jsonify({"error": "Unknown task"}), 404

    task = enrichment_tasks[task_id]

    return jsonify({
        "status": task['status'],
        "phase": task['phase'],
        "tech_stack": {
            "completed": task['tech_completed'],
            "total": task['tech_total'],
            "current": task.get('tech_current', '')
        },
        "linkedin": {
            "completed": task['linkedin_completed'],
            "total": task['linkedin_total'],
            "current": task.get('linkedin_current', '')
        },
        "error": task.get('error')
    })


@agent02_bp.route('/api/agent02/enrichment-results', methods=['POST'])
def get_enrichment_results():
    """
    Get the deep enrichment results after completion.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    sess = session_data[session_id]
    enriched = sess.get('deep_enriched_contacts', [])

    if not enriched:
        return jsonify({"error": "No deep enrichment results available"}), 400

    # Format for display
    results = []
    for c in enriched:
        tech_stack = c.get('company_tech_stack', [])
        categories = c.get('company_description', {})

        results.append({
            "name": c.get('name', 'Unknown'),
            "title": c.get('title', 'N/A'),
            "email": c.get('email', ''),
            "company": c.get('company', 'N/A'),
            "domain": c.get('domain', ''),
            "linkedin_url": c.get('linkedin_url', ''),
            # LinkedIn enrichment fields
            "bio_snippet": c.get('bio_snippet', ''),
            "time_in_role": c.get('time_in_role', ''),
            "location": c.get('location', ''),
            "connections": c.get('connections', ''),
            # Tech stack fields
            "tech_stack": tech_stack if isinstance(tech_stack, list) else [],
            "primary_framework": categories.get('frontend', 'N/A'),
            "hosting": categories.get('hosting', 'N/A'),
            "analytics": categories.get('analytics', []),
            "about_company": c.get('about_company', 'N/A'),
        })

    return jsonify({
        "success": True,
        "contacts": results,
        "total": len(results)
    })


@agent02_bp.route('/api/agent02/export-sheets', methods=['POST'])
def export_to_sheets():
    """
    Export deep enriched contacts to Google Sheets.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    sess = session_data[session_id]
    enriched = sess.get('deep_enriched_contacts', [])

    if not enriched:
        return jsonify({"error": "No enriched contacts to export"}), 400

    try:
        exporter = SheetsExporterOAuth()
        sheet_url = exporter.export(enriched)
        sess['sheets_url_agent02'] = sheet_url

        return jsonify({
            "success": True,
            "sheet_url": sheet_url
        })
    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500