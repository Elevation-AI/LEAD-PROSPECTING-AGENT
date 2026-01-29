"""
Email Generator - LLM-based Email Writer
=========================================
Uses Groq LLM to generate personalized, unique emails for each contact.
No static templates - each email has unique sentence structure.

Part of Agent 03: Outreach Orchestration
"""

import sys
import os
import json
from typing import Dict, List, Optional

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
from groq import Groq
from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from src.utils.helpers import setup_logger


class EmailGenerator:
    """
    LLM-based email generator for personalized outreach.

    Features:
    - Generates unique email for each contact (no static templates)
    - Uses contact data from Agent 02 (name, title, company, bio, tech stack)
    - Configurable tone (Professional, Casual, Direct)
    - Configurable CTA (Call, Demo, PDF, etc.)
    - Fallback to safer copy when data is missing
    """

    # Available tone options
    TONES = {
        "professional": "formal, business-appropriate, respectful",
        "casual": "friendly, conversational, approachable",
        "direct": "concise, to-the-point, action-oriented"
    }

    # Available CTA options
    CTAS = {
        "call": "ask for a quick 15-minute call",
        "demo": "offer a personalized demo",
        "pdf": "offer to send a relevant case study or PDF",
        "reply": "ask them to reply with their thoughts",
        "meeting": "suggest scheduling a meeting"
    }

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

        # Default settings
        self.tone = "professional"
        self.cta = "call"
        self.sender_name = "Sales Representative"
        self.sender_company = "Our Company"
        self.value_proposition = ""

    def configure(
        self,
        tone: str = "professional",
        cta: str = "call",
        sender_name: str = None,
        sender_company: str = None,
        value_proposition: str = None
    ):
        """
        Configure the email generator settings.

        Args:
            tone: Email tone - "professional", "casual", or "direct"
            cta: Call to action - "call", "demo", "pdf", "reply", "meeting"
            sender_name: Name of the person sending the email
            sender_company: Company name of the sender
            value_proposition: What value/solution you offer
        """
        if tone.lower() in self.TONES:
            self.tone = tone.lower()
        else:
            self.logger.warning(f"Unknown tone '{tone}', using 'professional'")
            self.tone = "professional"

        if cta.lower() in self.CTAS:
            self.cta = cta.lower()
        else:
            self.logger.warning(f"Unknown CTA '{cta}', using 'call'")
            self.cta = "call"

        if sender_name:
            self.sender_name = sender_name
        if sender_company:
            self.sender_company = sender_company
        if value_proposition:
            self.value_proposition = value_proposition

        self.logger.info(f"Configured: tone={self.tone}, cta={self.cta}")

    def _build_context(self, contact: Dict) -> Dict:
        """
        Build context dictionary from contact data.
        Marks what data is available vs missing.
        """
        # Extract first name properly
        first_name = contact.get("first_name")
        if not first_name and contact.get("name"):
            name_parts = contact.get("name", "").split()
            first_name = name_parts[0] if name_parts else None

        # Extract last name
        last_name = contact.get("last_name")
        if not last_name and contact.get("name"):
            name_parts = contact.get("name", "").split()
            last_name = name_parts[-1] if len(name_parts) > 1 else None

        # Full name
        full_name = contact.get("name")
        if not full_name:
            full_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

        # Company name - handle "Unknown" from Agent 02
        company = contact.get("company")
        if company == "Unknown" or not company:
            # Try to extract from domain
            domain = contact.get("domain", "")
            if domain:
                company = domain.split('.')[0].title()

        context = {
            # Contact info
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "title": contact.get("title"),
            "email": contact.get("email"),

            # Company info
            "company": company,
            "domain": contact.get("domain"),

            # Enrichment data from Agent 02
            "time_in_role": contact.get("time_in_role"),
            "location": contact.get("location"),
            "bio_snippet": contact.get("bio_snippet"),
            "tech_stack": contact.get("company_tech_stack") or contact.get("tech_stack"),

            # What's available for personalization
            "has_tenure": bool(contact.get("time_in_role")),
            "has_bio": bool(contact.get("bio_snippet")),
            "has_location": bool(contact.get("location")),
            "has_tech_stack": bool(contact.get("company_tech_stack") or contact.get("tech_stack")),
        }

        return context

    def _create_prompt(self, context: Dict) -> str:
        """
        Create the LLM prompt for generating the email.
        """
        # Build personalization hints based on available data
        personalization_hints = []

        if context["has_tenure"]:
            personalization_hints.append(f"- They have been in their role for {context['time_in_role']}")

        if context["has_bio"]:
            personalization_hints.append(f"- Their LinkedIn bio mentions: {context['bio_snippet'][:150]}")

        if context["has_location"]:
            personalization_hints.append(f"- They are located in {context['location']}")

        if context["has_tech_stack"]:
            tech = context["tech_stack"]
            if isinstance(tech, list):
                tech = ", ".join(tech[:5])
            personalization_hints.append(f"- Their company uses: {tech}")

        personalization_section = "\n".join(personalization_hints) if personalization_hints else "- Limited data available, use a general but professional approach"

        prompt = f"""You are an expert sales copywriter. Write a personalized cold outreach email.

RECIPIENT INFORMATION:
- First Name: {context['first_name'] or context['full_name'].split()[0] if context['full_name'] else 'there'}
- Full Name: {context['full_name'] or 'the recipient'}
- Job Title: {context['title'] or 'Professional'}
- Company: {context['company'] or 'their company'}

PERSONALIZATION DATA AVAILABLE:
{personalization_section}

SENDER INFORMATION:
- Sender Name: {self.sender_name}
- Sender Company: {self.sender_company}
- Value Proposition: {self.value_proposition or 'We help companies improve their operations'}

EMAIL REQUIREMENTS:
1. TONE: {self.TONES[self.tone]}
2. CALL TO ACTION: {self.CTAS[self.cta]}
3. DO NOT use generic phrases like "I hope this finds you well" or "I came across your profile"
4. DO NOT hallucinate or make up facts not provided above
5. If data is missing, write a professional email without making things up
6. Make the opening line unique and specific to this person
7. Each email must have a DIFFERENT sentence structure (no templates)

CRITICAL EMAIL FORMATTING:
The email MUST have proper line breaks (use \\n for new lines). Format EXACTLY like this:

Hi [First Name],

[Opening paragraph - 1-2 sentences with personalized hook]

[Value paragraph - 1-2 sentences about how you can help]

[CTA sentence - ask for call/meeting]

Best regards,
{self.sender_name}
{self.sender_company}

IMPORTANT FORMATTING RULES:
- Use \\n\\n (double newline) between paragraphs
- Use \\n (single newline) between sign-off lines
- The greeting "Hi [Name]," must be on its own line followed by blank line
- The sign-off must be on separate lines (Best regards, then name, then company)
- Do NOT write everything in one paragraph

OUTPUT FORMAT:
Return ONLY a JSON object with this exact structure:
{{
    "subject_line": "The email subject (short, compelling, no spam words)",
    "body": "Hi [Name],\\n\\n[Opening paragraph]\\n\\n[Value paragraph]\\n\\n[CTA]\\n\\nBest regards,\\n{self.sender_name}\\n{self.sender_company}",
    "personalization_used": ["list", "of", "data", "points", "used"]
}}

Generate the properly formatted email now:"""

        return prompt

    def generate_email(self, contact: Dict) -> Dict:
        """
        Generate a personalized email for a single contact.

        Args:
            contact: Contact dictionary from Agent 02

        Returns:
            Dictionary with subject_line, body, email address, and metadata
        """
        self.logger.info(f"Generating email for: {contact.get('name', 'Unknown')}")

        # Build context
        context = self._build_context(contact)

        # Create prompt
        prompt = self._create_prompt(context)

        try:
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a sales copywriter. Return ONLY valid JSON, no other text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # Balanced temperature for quality
                max_tokens=800  # More tokens for complete email with sign-off
            )

            # Parse response
            content = response.choices[0].message.content.strip()

            # Clean up JSON if needed
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            email_data = json.loads(content.strip())

            # Add metadata
            result = {
                "recipient_email": context["email"],
                "recipient_name": context["full_name"],
                "recipient_company": context["company"],
                "subject_line": email_data.get("subject_line", "Quick question"),
                "body": email_data.get("body", ""),
                "personalization_used": email_data.get("personalization_used", []),
                "tone": self.tone,
                "cta": self.cta,
                "generation_status": "success"
            }

            self.logger.info(f"✅ Email generated for {context['full_name']}")
            return result

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return self._fallback_email(context)
        except Exception as e:
            self.logger.error(f"Email generation failed: {e}")
            return self._fallback_email(context)

    def _fallback_email(self, context: Dict) -> Dict:
        """
        Generate a safe fallback email when LLM fails.
        """
        first_name = context["first_name"] or "there"
        company = context["company"] or "your company"

        subject = f"Quick question for {first_name}"
        body = f"""Hi {first_name},

I came across {company} and wanted to reach out briefly.

{self.value_proposition or "We help companies like yours improve their operations and efficiency."}

Would you be open to a quick conversation to see if there's a fit?

Best,
{self.sender_name}
{self.sender_company}"""

        return {
            "recipient_email": context["email"],
            "recipient_name": context["full_name"],
            "recipient_company": context["company"],
            "subject_line": subject,
            "body": body,
            "personalization_used": [],
            "tone": self.tone,
            "cta": self.cta,
            "generation_status": "fallback"
        }

    def generate_batch(self, contacts: List[Dict]) -> List[Dict]:
        """
        Generate emails for a batch of contacts.

        Args:
            contacts: List of contact dictionaries from Agent 02

        Returns:
            List of generated email dictionaries
        """
        self.logger.info(f"Generating emails for {len(contacts)} contacts...")

        emails = []
        for i, contact in enumerate(contacts, 1):
            self.logger.info(f"Processing {i}/{len(contacts)}: {contact.get('name', 'Unknown')}")

            email = self.generate_email(contact)
            emails.append(email)

        success_count = sum(1 for e in emails if e["generation_status"] == "success")
        self.logger.info(f"✅ Generated {success_count}/{len(emails)} emails successfully")

        return emails


# =============================================================================
# DRIVER CODE - TEST
# =============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Email Generator Test")
    print("=" * 60)

    # Sample contacts (simulating Agent 02 output)
    test_contacts = [
        {
            "name": "Harold Dawson",
            "title": "Operations Manager",
            "email": "harold@industrialelectricalco.com",
            "company": "Industrial Electrical Company",
            "domain": "industrialelectricalco.com",
            "time_in_role": "8 yr 3 mo",
            "location": "Modesto, California, United States",
            "bio_snippet": "Operations Manager at Industrial Electrical Company",
            "company_tech_stack": ["WordPress", "PHP", "Google Analytics"]
        },
        {
            "name": "Derek Sammataro",
            "title": "Director of Facilities Services",
            "email": "dereks@westportproperties.net",
            "company": "Westport Properties",
            "domain": "westportproperties.net",
            "time_in_role": "2 yr 11 mo",
            "location": "Windham, New Hampshire",
            "bio_snippet": "20+ years in Self Storage Operations I Commercial Real Estate I Capital Projects",
            "company_tech_stack": ["WordPress", "Stripe", "Google Analytics"]
        }
    ]

    # Initialize generator
    generator = EmailGenerator()

    # Configure settings
    print("\n⚙️ Configuring email generator...")
    generator.configure(
        tone="professional",
        cta="call",
        sender_name="John Smith",
        sender_company="TechSolutions Inc",
        value_proposition="We help operations teams automate repetitive tasks and reduce manual work by 40%"
    )

    # Generate emails
    print("\n📧 Generating emails...")
    print("-" * 60)

    emails = generator.generate_batch(test_contacts)

    # Display results
    print("\n" + "=" * 60)
    print("📬 GENERATED EMAILS")
    print("=" * 60)

    for i, email in enumerate(emails, 1):
        print(f"\n--- Email {i} ---")
        print(f"To: {email['recipient_name']} <{email['recipient_email']}>")
        print(f"Subject: {email['subject_line']}")
        print(f"\n{email['body']}")
        print(f"\n[Status: {email['generation_status']}]")
        print(f"[Personalization: {', '.join(email['personalization_used'])}]")
        print("-" * 40)

    print("\n✅ Test complete!")
    print("=" * 60)
