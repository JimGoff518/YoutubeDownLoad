"""Extract marketing-relevant articles from Trial Lawyer magazine PDFs.

Steps:
1. Extract full text from each PDF
2. Use Claude to identify article boundaries and score marketing relevance
3. Output only marketing-relevant articles (score >= 3) as separate entries
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import time

import pdfplumber
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

RELEVANCE_PROMPT = """You are analyzing a legal magazine issue to identify individual articles and score their relevance to personal injury (PI) law firm marketing and growth strategy.

RELEVANT topics (score 3-5):
- Marketing, advertising, branding for law firms
- Intake, case acquisition, lead strategy, cost per case
- Mass torts (marketing angle)
- Referrals, referral partners
- Firm growth strategies, acquisition, scaling
- Overhead, staffing for marketing, CMO roles
- Marketing environment/landscape changes
- AI for legal marketing
- Content strategy, social media marketing
- PI firm business operations and growth

IRRELEVANT topics (score 1-2):
- Pure trial technique / courtroom strategy with no business angle
- Non-PI practice areas (family law, criminal, immigration)
- Personal stories with no marketing or growth insight
- Advertisements or sponsor content
- Table of contents, editor's notes with no substance

For each article you identify, output a JSON array of objects:
{
  "title": "Article title",
  "relevance_score": 1-5,
  "reason": "Brief reason for score",
  "start_marker": "First ~20 words of the article text",
  "end_marker": "Last ~20 words of the article text"
}

Only include articles with enough substance (at least a few paragraphs). Skip ads, TOC, mastheads.

Here is the magazine text:
"""


def extract_pdf_text(pdf_path: str) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def identify_articles(full_text: str, client: Anthropic) -> list[dict]:
    """Use Claude to identify articles and score relevance."""
    # Send first ~60K chars (covers most articles, stays under token limits)
    max_chars = 60000
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars]

    # Retry with backoff for rate limits
    for attempt in range(5):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": RELEVANCE_PROMPT + full_text
                }]
            )
            break
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 30 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s (attempt {attempt + 1}/5)...")
                time.sleep(wait)
            else:
                raise
    else:
        print("  Failed after 5 retries")
        return []

    # Parse JSON from response
    text = response.content[0].text
    # Find JSON array in response
    start = text.find('[')
    end = text.rfind(']') + 1
    if start == -1 or end == 0:
        print("  Warning: Could not parse article list from Claude response")
        return []

    try:
        articles = json.loads(text[start:end])
        return articles
    except json.JSONDecodeError as e:
        print(f"  Warning: JSON parse error: {e}")
        return []


def extract_article_text(full_text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between start and end markers."""
    # Find start position
    start_idx = full_text.find(start_marker[:50])
    if start_idx == -1:
        # Try a shorter match
        start_idx = full_text.find(start_marker[:30])
    if start_idx == -1:
        return ""

    # Find end position (search after start)
    end_idx = full_text.find(end_marker[:50], start_idx)
    if end_idx == -1:
        end_idx = full_text.find(end_marker[:30], start_idx)
    if end_idx == -1:
        # Take a reasonable chunk after start
        end_idx = min(start_idx + 15000, len(full_text))
    else:
        end_idx += len(end_marker)

    return full_text[start_idx:end_idx].strip()


def process_magazine(pdf_path: str, source_name: str, client: Anthropic) -> dict:
    """Process a single magazine PDF and return ingestion-ready JSON."""
    print(f"\nProcessing: {Path(pdf_path).name}")

    full_text = extract_pdf_text(pdf_path)
    print(f"  Extracted {len(full_text):,} chars ({len(full_text.split()):,} words)")

    if len(full_text) < 500:
        print("  Skipping - too little text extracted")
        return None

    print("  Identifying articles with Claude...")
    articles = identify_articles(full_text, client)
    print(f"  Found {len(articles)} articles total")

    # Filter to marketing-relevant (score >= 3)
    relevant = [a for a in articles if a.get("relevance_score", 0) >= 3]
    print(f"  {len(relevant)} marketing-relevant articles (score >= 3)")

    for a in articles:
        status = "KEEP" if a.get("relevance_score", 0) >= 3 else "skip"
        print(f"    [{status}] ({a.get('relevance_score', '?')}) {a.get('title', 'Unknown')}")

    # Build video entries for each relevant article
    videos = []
    for article in relevant:
        article_text = extract_article_text(
            full_text,
            article.get("start_marker", ""),
            article.get("end_marker", "")
        )

        if len(article_text) < 200:
            print(f"    Warning: Could not extract text for '{article.get('title', 'Unknown')}', skipping")
            continue

        title = article.get("title", "Unknown Article")
        videos.append({
            "id": hashlib.md5(f"{source_name}:{title}".encode()).hexdigest()[:12],
            "title": title,
            "transcript": {
                "available": True,
                "language": "en",
                "is_auto_generated": False,
                "segments": [],
                "full_text": article_text,
                "word_count": len(article_text.split()),
                "character_count": len(article_text)
            }
        })

    if not videos:
        print("  No articles extracted successfully")
        return None

    return {
        "extraction_metadata": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extractor_version": "1.0.0",
            "source_type": "pdf_magazine",
            "source_file": Path(pdf_path).name,
            "total_videos_processed": len(videos),
            "successful_extractions": len(videos),
            "failed_extractions": 0,
            "total_articles_found": len(articles),
            "marketing_relevant_articles": len(relevant)
        },
        "videos": videos,
        "errors": []
    }


def main():
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    pdfs = [
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Spring 2024.pdf", "TrialLawyer_Spring2024"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Summer 2024.pdf", "TrialLawyer_Summer2024"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Fall 2024.pdf", "TrialLawyer_Fall2024"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Spring 2025.pdf", "TrialLawyer_Spring2025"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Summer 2025.pdf", "TrialLawyer_Summer2025"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Fall 2025.pdf", "TrialLawyer_Fall2025"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer Winter 2025.pdf", "TrialLawyer_Winter2025"),
        ("C:\\Users\\jim\\Box\\Downloads\\The Trial Lawyer - The A-List 2025.pdf", "TrialLawyer_AList2025"),
    ]

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    results_summary = []

    for pdf_path, source_name in pdfs:
        if not Path(pdf_path).exists():
            print(f"  SKIP - File not found: {pdf_path}")
            continue

        output_file = output_dir / f"{source_name}.json"
        if output_file.exists():
            print(f"\n  SKIP - Already extracted: {output_file}")
            continue

        result = process_magazine(pdf_path, source_name, client)
        if result:
            output_path = output_dir / f"{source_name}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"  Saved to: {output_path}")
            results_summary.append({
                "source": source_name,
                "articles_found": result["extraction_metadata"]["total_articles_found"],
                "articles_kept": result["extraction_metadata"]["marketing_relevant_articles"],
                "articles_extracted": len(result["videos"])
            })

    print(f"\n{'='*60}")
    print("Summary:")
    for r in results_summary:
        print(f"  {r['source']}: {r['articles_found']} found, {r['articles_kept']} relevant, {r['articles_extracted']} extracted")
    print(f"{'='*60}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    main()
