# src/input/content_aggregator.py

from typing import List, Dict


class ContentAggregator:
    def aggregate(self, contexts: List[Dict]) -> str:
        unique_blocks = []

        for ctx in contexts:
            content = ctx.get("content", "").strip()
            if content and content not in unique_blocks:
                unique_blocks.append(content)

        return "\n\n".join(unique_blocks)


# 🔹 DRIVER CODE
if __name__ == "__main__":
    print("\n Testing Content Aggregator")
    print("=" * 50)

    sample_contexts = [
        {"source": "website", "content": "We sell CRM software for healthcare."},
        {"source": "pdf", "content": "Healthcare CRM focused on dental clinics."},
        {"source": "raw_text", "content": "Our product is built for healthcare providers."}
    ]

    aggregator = ContentAggregator()
    final_context = aggregator.aggregate(sample_contexts)

    print("\n Unified Company Context:\n")
    print(final_context)
