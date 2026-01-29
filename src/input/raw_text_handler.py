# src/input/raw_text_handler.py

from typing import Dict


class RawTextHandler:
    def process(self, raw_text: str) -> Dict:
        if not raw_text or len(raw_text.strip()) < 50:
            raise ValueError("Raw text too short to generate ICP")

        cleaned_text = " ".join(raw_text.split())

        return {
            "source": "raw_text",
            "content": cleaned_text
        }


# 🔹 DRIVER CODE
if __name__ == "__main__":
    print("\n Testing Raw Text Handler")
    print("=" * 50)

    sample_text = """
    We are a B2B SaaS company building AI-powered lead generation tools
    for startups and enterprise sales teams across North America and Europe.
    """

    handler = RawTextHandler()
    result = handler.process(sample_text)

    print("\n Normalized Raw Text:\n")
    print(result["content"])
