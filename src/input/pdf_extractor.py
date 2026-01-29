# src/input/pdf_extractor.py

import os
from typing import Dict

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError("Install PyMuPDF: pip install pymupdf")


class PDFExtractor:
    def extract_text(self, pdf_path: str) -> Dict:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        text_blocks = []

        for page in doc:
            text_blocks.append(page.get_text())

        combined_text = "\n".join(text_blocks).strip()

        return {
            "source": "pdf",
            "content": combined_text
        }


# 🔹 DRIVER CODE
if __name__ == "__main__":
    print("\n Testing PDF Extractor")
    print("=" * 50)

    extractor = PDFExtractor()
    sample_pdf = r"C:\Users\nikhil kumar\Downloads\24-MFI-Global-Company-Brochure-merged-compressed-24-MFI-Global-Company-Brochure-HighRes.pdf"   # put a test PDF here

    try:
        result = extractor.extract_text(sample_pdf)
        print("\n Extracted Content Preview:\n")
        print(result["content"][:1000])  # first 1000 chars
    except Exception as e:
        print(" Error:", e)
