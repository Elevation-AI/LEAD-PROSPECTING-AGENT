"""
Flask Blueprint for Agent 03 - Outreach Email Generation
=========================================================
Handles:
  Step 8: Configure email settings (tone, CTA, sender info, value prop)
  Step 9: Generate emails + export to Google Sheets
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify

# Add project root and Agent_03 directory to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
agent03_dir = str(PROJECT_ROOT / "Agent_03")
if agent03_dir not in sys.path:
    sys.path.insert(0, agent03_dir)

from email_generator import EmailGenerator
from sheets_output import EmailSheetsExporter

agent03_bp = Blueprint('agent03', __name__)


@agent03_bp.route('/api/agent03/configure', methods=['POST'])
def configure_outreach():
    """
    Save email configuration (tone, CTA, sender, value prop).
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    config = {
        "tone": data.get('tone', 'professional'),
        "cta": data.get('cta', 'call'),
        "sender_name": data.get('sender_name', 'Sales Representative'),
        "sender_company": data.get('sender_company', 'Our Company'),
        "value_proposition": data.get('value_proposition', 'We help companies improve their operations')
    }

    session_data[session_id]['email_config'] = config

    return jsonify({
        "success": True,
        "config": config
    })


@agent03_bp.route('/api/agent03/generate-emails', methods=['POST'])
def generate_emails():
    """
    Generate personalized emails for all deep-enriched contacts.
    Uses the config saved in the previous step.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    sess = session_data[session_id]
    config = sess.get('email_config')

    if not config:
        return jsonify({"error": "Email configuration not set. Complete Step 8 first."}), 400

    # Get contacts - prefer deep enriched, fall back to Agent 01 flat contacts
    contacts = sess.get('deep_enriched_contacts', sess.get('flat_contacts', []))

    if not contacts:
        return jsonify({"error": "No contacts available. Complete previous steps first."}), 400

    try:
        # Initialize and configure generator
        generator = EmailGenerator()
        generator.configure(
            tone=config['tone'],
            cta=config['cta'],
            sender_name=config['sender_name'],
            sender_company=config['sender_company'],
            value_proposition=config['value_proposition']
        )

        # Generate emails
        emails = generator.generate_batch(contacts)

        # Store in session
        sess['generated_emails'] = emails

        # Format for display
        emails_display = []
        for email in emails:
            emails_display.append({
                "recipient_name": email.get('recipient_name', 'Unknown'),
                "recipient_email": email.get('recipient_email', ''),
                "recipient_company": email.get('recipient_company', ''),
                "subject_line": email.get('subject_line', ''),
                "body": email.get('body', ''),
                "personalization_used": email.get('personalization_used', []),
                "tone": email.get('tone', ''),
                "cta": email.get('cta', ''),
                "generation_status": email.get('generation_status', 'unknown')
            })

        success_count = sum(1 for e in emails if e.get('generation_status') == 'success')

        return jsonify({
            "success": True,
            "emails": emails_display,
            "total": len(emails),
            "success_count": success_count
        })

    except Exception as e:
        return jsonify({"error": f"Email generation failed: {str(e)}"}), 500


@agent03_bp.route('/api/agent03/export-sheets', methods=['POST'])
def export_emails_to_sheets():
    """
    Export generated emails to Google Sheets.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    sess = session_data[session_id]
    emails = sess.get('generated_emails', [])

    if not emails:
        return jsonify({"error": "No generated emails to export"}), 400

    try:
        config = sess.get('email_config', {})
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        company = config.get('sender_company', 'Outreach').replace(' ', '_')
        sheet_name = f"Outreach_Emails_{company}_{timestamp}"

        exporter = EmailSheetsExporter()
        sheet_url = exporter.export(emails, sheet_name)

        sess['sheets_url_agent03'] = sheet_url

        return jsonify({
            "success": True,
            "sheet_url": sheet_url
        })

    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


@agent03_bp.route('/api/agent03/save-local', methods=['POST'])
def save_emails_local():
    """
    Save generated emails as a local JSON file.
    """
    from shared import session_data
    data = request.json
    session_id = data.get('session_id')

    if session_id not in session_data:
        return jsonify({"error": "Invalid session"}), 400

    sess = session_data[session_id]
    emails = sess.get('generated_emails', [])
    config = sess.get('email_config', {})

    if not emails:
        return jsonify({"error": "No emails to save"}), 400

    try:
        output_dir = PROJECT_ROOT / "output"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"outreach_emails_{timestamp}.json"
        filepath = output_dir / filename

        output_data = {
            "generated_at": datetime.now().isoformat(),
            "config": config,
            "total_emails": len(emails),
            "emails": emails,
            "google_sheet_url": sess.get('sheets_url_agent03')
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        return jsonify({
            "success": True,
            "filepath": str(filepath),
            "message": f"Saved {len(emails)} emails to {filename}"
        })

    except Exception as e:
        return jsonify({"error": f"Save failed: {str(e)}"}), 500