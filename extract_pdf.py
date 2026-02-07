"""Extract text from PDF files and produce JSON compatible with ingest_to_pinecone.py"""

import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber


def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def build_output_json(title: str, full_text: str, source_type: str = "pdf") -> dict:
    """Build JSON structure matching ingest_to_pinecone.py expected format."""
    word_count = len(full_text.split())
    char_count = len(full_text)

    return {
        "extraction_metadata": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extractor_version": "1.0.0",
            "source_type": source_type,
            "total_videos_processed": 1,
            "successful_extractions": 1,
            "failed_extractions": 0
        },
        "videos": [
            {
                "id": hashlib.md5(title.encode()).hexdigest()[:12],
                "title": title,
                "transcript": {
                    "available": True,
                    "language": "en",
                    "is_auto_generated": False,
                    "segments": [],
                    "full_text": full_text,
                    "word_count": word_count,
                    "character_count": char_count
                }
            }
        ],
        "errors": []
    }


def build_multi_article_json(articles: list[dict], source_type: str = "pdf_magazine") -> dict:
    """Build JSON with multiple articles as separate video entries."""
    videos = []
    for article in articles:
        word_count = len(article["text"].split())
        videos.append({
            "id": hashlib.md5(article["title"].encode()).hexdigest()[:12],
            "title": article["title"],
            "transcript": {
                "available": True,
                "language": "en",
                "is_auto_generated": False,
                "segments": [],
                "full_text": article["text"],
                "word_count": word_count,
                "character_count": len(article["text"])
            }
        })

    return {
        "extraction_metadata": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extractor_version": "1.0.0",
            "source_type": source_type,
            "total_videos_processed": len(videos),
            "successful_extractions": len(videos),
            "failed_extractions": 0
        },
        "videos": videos,
        "errors": []
    }


def main():
    parser = argparse.ArgumentParser(description="Extract text from PDF and produce ingestion-compatible JSON")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--source-name", "-s", help="Source name for the output file (default: PDF filename)")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--title", "-t", help="Document title (default: PDF filename)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return

    source_name = args.source_name or pdf_path.stem
    title = args.title or pdf_path.stem
    output_path = args.output or f"output/{source_name}.json"

    print(f"Extracting text from: {pdf_path.name}")
    full_text = extract_pdf_text(str(pdf_path))

    if not full_text or len(full_text) < 100:
        print(f"Error: Extracted text is too short ({len(full_text)} chars)")
        return

    print(f"Extracted {len(full_text):,} characters ({len(full_text.split()):,} words)")

    output = build_output_json(title, full_text)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
