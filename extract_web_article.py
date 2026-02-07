"""Extract article text from a web URL and produce JSON compatible with ingest_to_pinecone.py"""

import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def extract_article_text(url: str) -> tuple[str, str]:
    """Fetch a web page and extract the article title and body text.

    Returns (title, body_text).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Extract title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    elif soup.title:
        title = soup.title.string or ""

    # Try to find the main article content
    article = soup.find("article")
    if not article:
        # Fallback: look for common content containers
        for selector in ["main", "[role='main']", ".entry-content", ".post-content", ".article-content", ".content"]:
            article = soup.select_one(selector)
            if article:
                break

    if not article:
        article = soup.body

    # Extract text from paragraphs, headings, and list items
    text_parts = []
    if article:
        for element in article.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote"]):
            text = element.get_text(strip=True)
            if text and len(text) > 20:
                text_parts.append(text)

    body_text = "\n\n".join(text_parts)
    return title.strip(), body_text


def build_output_json(title: str, full_text: str, url: str) -> dict:
    """Build JSON structure matching ingest_to_pinecone.py expected format."""
    word_count = len(full_text.split())

    return {
        "extraction_metadata": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extractor_version": "1.0.0",
            "source_type": "web_article",
            "source_url": url,
            "total_videos_processed": 1,
            "successful_extractions": 1,
            "failed_extractions": 0
        },
        "videos": [
            {
                "id": hashlib.md5(url.encode()).hexdigest()[:12],
                "title": title,
                "transcript": {
                    "available": True,
                    "language": "en",
                    "is_auto_generated": False,
                    "segments": [],
                    "full_text": full_text,
                    "word_count": word_count,
                    "character_count": len(full_text)
                }
            }
        ],
        "errors": []
    }


def main():
    parser = argparse.ArgumentParser(description="Extract article from URL and produce ingestion-compatible JSON")
    parser.add_argument("url", help="URL of the web article")
    parser.add_argument("--source-name", "-s", help="Source name for the output file")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    args = parser.parse_args()

    source_name = args.source_name or "web_article"
    output_path = args.output or f"output/{source_name}.json"

    print(f"Fetching: {args.url}")
    title, body_text = extract_article_text(args.url)

    if not body_text or len(body_text) < 100:
        print(f"Error: Extracted text is too short ({len(body_text)} chars)")
        return

    print(f"Title: {title}")
    print(f"Extracted {len(body_text):,} characters ({len(body_text.split()):,} words)")

    output = build_output_json(title, body_text, args.url)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
