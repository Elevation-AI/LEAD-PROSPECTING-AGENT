"""
Tech Stack Detector using Firecrawl + LLM
==========================================
Zero hardcoded patterns — LLM does ALL detection from raw signals.
"""

import sys
import os
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse
import json
import time
from firecrawl import FirecrawlApp
from google import genai
from google.genai import types

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.helpers import setup_logger
from config.settings import settings


class TechStackDetector:
    """
    Detect technologies used by a website using Firecrawl + LLM analysis.

    Approach (no hardcoded pattern lists):
    1. Firecrawl scrapes the website HTML
    2. Structurally extract script srcs, meta tags, link hrefs (no matching)
    3. LLM receives raw signals and detects ALL technologies itself
    4. Return structured tech stack + company summary
    """

    def __init__(self):
        self.logger = setup_logger(__name__)

        if not settings.FIRECRAWL_API_KEY:
            raise ValueError("FIRECRAWL_API_KEY missing in .env")
        self.firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)

        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY missing in .env")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # ------------------------------------------------------------------
    # STEP 1: Scrape website
    # ------------------------------------------------------------------
    def _scrape_website(self, url: str) -> Optional[Dict]:
        """Scrape website using Firecrawl Python SDK."""
        try:
            self.logger.info(f"Scraping {url} with Firecrawl...")

            doc = self.firecrawl.scrape(
                url=url,
                formats=["html", "markdown"],
                only_main_content=False
            )

            if not doc or not getattr(doc, "html", None):
                self.logger.error(f"Firecrawl returned no HTML for {url}")
                return None

            self.logger.info(f"Scraped {len(doc.html)} chars")

            return {
                "html": doc.html,
                "markdown": getattr(doc, "markdown", ""),
                "metadata": getattr(doc, "metadata", {}),
            }

        except Exception as e:
            self.logger.error(f"Firecrawl error for {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # STEP 2: Structural extraction (NO hardcoded pattern lists)
    # ------------------------------------------------------------------
    def _extract_raw_signals(self, scraped_data: Dict) -> str:
        """
        Extract raw structural signals from HTML for LLM analysis.

        Pulls ALL available signals — HTML elements, metadata from Firecrawl,
        and page content. No hardcoded technology lists. The LLM decides
        what technologies these signals represent.
        """
        html = scraped_data.get('html', '')
        markdown = scraped_data.get('markdown', '')
        metadata = scraped_data.get('metadata', {})
        sections = []

        # 1. Firecrawl metadata (often contains pre-detected info like OG tags, title, etc.)
        if metadata:
            meta_str = json.dumps(metadata, indent=2, default=str)[:2000]
            sections.append("FIRECRAWL METADATA:\n" + meta_str)

        # 2. All <script src="..."> URLs (reveals frameworks, analytics, CDNs, integrations)
        scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
        if scripts:
            seen = set()
            unique_scripts = []
            for s in scripts:
                if s not in seen:
                    seen.add(s)
                    unique_scripts.append(s)
            sections.append("SCRIPT SOURCES:\n" + "\n".join(unique_scripts[:30]))

        # 3. All <link> tags with full attributes (reveals CSS, fonts, CDNs, preconnect hints)
        link_tags = re.findall(r'<link\s+([^>]+)>', html, re.IGNORECASE)
        if link_tags:
            seen = set()
            unique_links = []
            for l in link_tags:
                if l not in seen:
                    seen.add(l)
                    unique_links.append(l)
            sections.append("LINK TAGS:\n" + "\n".join(unique_links[:25]))

        # 4. All <meta> tags (reveals CMS, generator, viewport, OG tags)
        meta_tags = re.findall(r'<meta\s+([^>]+)>', html, re.IGNORECASE)
        if meta_tags:
            sections.append("META TAGS:\n" + "\n".join(meta_tags[:25]))

        # 5. Inline <script> content snippets (first 800 chars of each, max 8)
        #    Reveals global variables like __NEXT_DATA__, __VUE__, dataLayer, gtag, etc.
        inline_scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html)
        inline_snippets = []
        for script in inline_scripts:
            stripped = script.strip()
            if stripped and len(stripped) > 20:
                inline_snippets.append(stripped[:800])
            if len(inline_snippets) >= 8:
                break
        if inline_snippets:
            sections.append("INLINE SCRIPT SNIPPETS:\n" + "\n---\n".join(inline_snippets))

        # 6. HTML <head> section (first 4000 chars)
        head_match = re.search(r'<head[^>]*>([\s\S]*?)</head>', html, re.IGNORECASE)
        if head_match:
            sections.append("HEAD SECTION:\n" + head_match.group(1)[:4000])

        # 7. Markdown content from Firecrawl (reveals mentioned services, integrations,
        #    third-party tools, and content that JS-rendered sites expose after rendering)
        if markdown:
            sections.append("PAGE CONTENT (markdown):\n" + markdown[:3000])

        if not sections:
            sections.append("RAW HTML (first 5000 chars):\n" + html[:5000])

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # STEP 3: LLM analyzes raw signals (does ALL detection)
    # ------------------------------------------------------------------
    def _analyze_with_llm(self, raw_signals: str, domain: str) -> Optional[Dict]:
        """
        LLM receives raw HTML signals and detects technologies.
        No pre-filtering or hardcoded lists — LLM decides everything.
        """
        prompt = f"""You are a senior web technology analyst. Analyze the raw HTML signals below from {domain} and identify every technology, framework, service, and tool this website uses.

RAW SIGNALS FROM {domain}:
{raw_signals}

IMPORTANT CONTEXT:
- The domain is {domain}. If {domain} is itself a technology company (e.g., stripe.com, shopify.com), do NOT list their own product as a technology they "use." Only list third-party tools and the actual tech stack that BUILDS their website.
- For example: stripe.com references "stripe" everywhere — that is their product, NOT a technology they use as a dependency.

YOUR TASK:
Identify ALL technologies based on EVIDENCE in the signals above. Look for:
- Script URLs (e.g., cdn.segment.com → Segment analytics, js.stripe.com → Stripe payments)
- Framework globals (e.g., __NEXT_DATA__ → Next.js, __VUE__ → Vue.js)
- Link tags (e.g., fonts.googleapis.com → Google Fonts)
- Meta tags (e.g., generator=WordPress)
- CDN/hosting URLs (e.g., vercel-scripts → Vercel, cloudflare → Cloudflare)
- Any other technology signals you can identify from the raw data

RULES:
1. ONLY include technologies you have EVIDENCE for in the signals
2. DO NOT guess or hallucinate technologies not visible in the data
3. DO NOT list the company's own product as part of their tech stack
4. Be specific (e.g., "Next.js" not just "React")
5. You may infer closely related tech (e.g., Next.js implies React and Node.js)

RETURN FORMAT (JSON only, no other text):
{{
  "frontend_framework": "string or null",
  "backend_technology": "string or null",
  "programming_languages": ["string"],
  "hosting_provider": "string or null",
  "cdn": "string or null",
  "analytics_tools": ["string"],
  "crm_tools": ["string"],
  "payment_processing": ["string"],
  "other_integrations": ["string"],
  "cms": "string or null",
  "confidence": "high/medium/low",
  "reasoning": "Brief explanation of key evidence for each detection"
}}

Return ONLY the JSON object, no additional text."""

        try:
            self.logger.info("Analyzing with LLM...")

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1500
                )
            )

            llm_output = response.text.strip()

            # Remove markdown code blocks if present
            if '```' in llm_output:
                parts = llm_output.split('```')
                for part in parts:
                    cleaned = part.strip()
                    if cleaned.startswith('json'):
                        cleaned = cleaned[4:].strip()
                    if cleaned.startswith('{'):
                        llm_output = cleaned
                        break

            tech_stack = json.loads(llm_output)

            self.logger.info(f"LLM detected {len([v for v in tech_stack.values() if v])} tech categories")
            return tech_stack

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON: {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM analysis error: {e}")
            return None

    # ------------------------------------------------------------------
    # STEP 4: Format output
    # ------------------------------------------------------------------
    def _format_tech_stack(self, raw_tech_stack: Dict, domain: str) -> Dict:
        """Format LLM output into clean structured dict for Agent 02."""
        tech_list = []

        for key, value in raw_tech_stack.items():
            if key in ['confidence', 'reasoning']:
                continue
            if isinstance(value, list):
                tech_list.extend([v for v in value if v])
            elif value and value != "null":
                tech_list.append(value)

        # Remove duplicates while preserving order
        tech_list = list(dict.fromkeys(tech_list))

        return {
            "domain": domain,
            "tech_stack": tech_list,
            "categories": {
                "frontend": raw_tech_stack.get("frontend_framework"),
                "backend": raw_tech_stack.get("backend_technology"),
                "hosting": raw_tech_stack.get("hosting_provider"),
                "analytics": raw_tech_stack.get("analytics_tools", []),
                "crm": raw_tech_stack.get("crm_tools", []),
                "cms": raw_tech_stack.get("cms")
            },
            "confidence": raw_tech_stack.get("confidence", "medium"),
            "reasoning": raw_tech_stack.get("reasoning", ""),
            "detection_method": "firecrawl_llm",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    # ------------------------------------------------------------------
    # COMPANY SUMMARY (PRD: "About the Company" column)
    # ------------------------------------------------------------------
    def summarize_company(self, url: str, scraped_data: Optional[Dict] = None) -> str:
        """
        Generate a plain-English summary of what the company does.
        PRD requirement: 'About the Company' column.

        Reuses already-scraped data when available to avoid duplicate API calls.
        """
        if not scraped_data:
            scraped_data = self._scrape_website(url)
        if not scraped_data:
            return "Company summary unavailable"

        markdown = scraped_data.get('markdown', '') or scraped_data.get('html', '')[:4000]
        content_snippet = markdown[:4000]

        prompt = f"""Based on this website content, write a concise 2-3 sentence summary of what this company does, who their customers are, and what products/services they offer.

WEBSITE CONTENT:
{content_snippet}

RULES:
1. Be factual — only state what the content shows
2. Focus on: what the company does, who they serve, their main product/service
3. Do NOT mention website technologies or design
4. Keep it under 200 characters
5. Write in third person (e.g., "Stripe provides...")

Return ONLY the summary text, no labels or formatting."""

        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=300
                )
            )
            summary = response.text.strip()
            self.logger.info(f"Company summary generated ({len(summary)} chars)")
            return summary[:300]
        except Exception as e:
            self.logger.error(f"Company summary failed: {e}")
            return "Company summary unavailable"

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def detect(self, url: str) -> Optional[Dict]:
        """
        Main method: Detect tech stack for a website.

        Args:
            url: Full website URL (e.g., "https://greenhouse.io")

        Returns:
            Dictionary with tech stack or None if failed
        """
        domain = urlparse(url).netloc.replace('www.', '')

        self.logger.info(f"Detecting tech stack for {domain}")

        # Step 1: Scrape website
        scraped_data = self._scrape_website(url)
        if not scraped_data:
            return None

        # Step 2: Extract raw structural signals (no pattern matching)
        raw_signals = self._extract_raw_signals(scraped_data)

        # Step 3: LLM analyzes raw signals and detects everything
        raw_tech_stack = self._analyze_with_llm(raw_signals, domain)
        if not raw_tech_stack:
            return None

        # Step 4: Format output
        formatted = self._format_tech_stack(raw_tech_stack, domain)

        # Step 5: Generate company summary (PRD: "About the Company" column)
        formatted["company_summary"] = self.summarize_company(url, scraped_data=scraped_data)

        self.logger.info(f"Detected {len(formatted['tech_stack'])} technologies for {domain}")

        return formatted

    def detect_batch(self, urls: List[str]) -> List[Dict]:
        """Detect tech stack for multiple websites."""
        results = []

        for i, url in enumerate(urls, 1):
            self.logger.info(f"Processing {i}/{len(urls)}: {url}")

            tech_stack = self.detect(url)

            if tech_stack:
                results.append(tech_stack)
            else:
                self.logger.warning(f"Failed to detect tech for {url}")

            if i < len(urls):
                time.sleep(2)

        self.logger.info(f"Detected tech for {len(results)}/{len(urls)} websites")
        return results


# --------------------------------------------------------
# TEST DRIVER
# --------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*70)
    print("Tech Stack Detector (Firecrawl + LLM)")
    print("="*70)

    detector = TechStackDetector()

    test_urls = [
        "https://openai.com"
    ]

    for url in test_urls:
        print(f"\nTesting: {url}")
        print("-" * 70)

        result = detector.detect(url)

        if result:
            print("\nSUCCESS\n")
            print(f"Domain: {result['domain']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Reasoning: {result.get('reasoning', 'N/A')}")
            print(f"\nTech Stack ({len(result['tech_stack'])} technologies):")
            for tech in result['tech_stack']:
                print(f"  - {tech}")

            print(f"\nCategories:")
            for category, value in result['categories'].items():
                if value:
                    print(f"  {category}: {value}")
        else:
            print("\nFAILED")

        print("\n" + "="*70)