"""Extract structured key takeaways from episode transcripts using Claude.

Phase 7.2: Episode Key Takeaways Extraction
Processes transcripts and extracts:
- Key takeaways (3-5 bullet points)
- Subject area/category
- Topics covered (tags)
- Unique insights
- Potential action items for the firm
"""

import json
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

# Configure stdout for Unicode
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Configuration
CLAUDE_MODEL = "claude-sonnet-4-20250514"
TAKEAWAYS_FILE = Path(__file__).parent / "takeaways_index.json"
OUTPUT_DIR = Path(__file__).parent / "output"

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Extraction prompt template
EXTRACTION_PROMPT = """You are analyzing a transcript from a podcast or video about personal injury law firm marketing and business.

Extract the following structured information:

1. **Key Takeaways** (3-5 bullet points): The most important, actionable insights from this content. Focus on specific tactics, strategies, or principles that a PI law firm could implement.

2. **Subject Area**: The primary category this content falls into. Choose ONE from:
   - Intake Optimization
   - Digital Marketing (SEO, PPC, Social)
   - TV/Radio Advertising
   - Referral Marketing
   - Client Experience
   - Hiring & Team Building
   - Firm Operations
   - Mass Torts
   - Trial Strategy
   - Case Management
   - Branding & Positioning
   - Technology & AI
   - Leadership & Mindset
   - Financial Management
   - Other (specify)

3. **Topics** (3-7 tags): Specific topics covered. Be precise (e.g., "Google LSAs" not just "marketing").

4. **Unique Insights**: Any novel ideas, contrarian takes, or tactics mentioned that aren't commonly discussed. If none, say "None identified."

5. **Action Items**: 1-3 specific things a small/mid-size PI firm could implement based on this content.

6. **Notable Quotes**: 1-2 memorable or impactful quotes (exact or paraphrased) if any stand out.

Respond in this exact JSON format:
```json
{
  "key_takeaways": ["takeaway 1", "takeaway 2", "takeaway 3"],
  "subject_area": "Category Name",
  "topics": ["topic1", "topic2", "topic3"],
  "unique_insights": "Description or 'None identified'",
  "action_items": ["action 1", "action 2"],
  "notable_quotes": ["quote 1"]
}
```

TRANSCRIPT:
"""


def generate_episode_id(source: str, title: str) -> str:
    """Generate a unique ID for an episode."""
    content = f"{source}:{title}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def load_takeaways_index() -> dict:
    """Load the existing takeaways index."""
    if TAKEAWAYS_FILE.exists():
        with open(TAKEAWAYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "updated_at": None,
        "total_episodes": 0,
        "episodes": {}
    }


def save_takeaways_index(index: dict):
    """Save the takeaways index."""
    index["updated_at"] = datetime.now(timezone.utc).isoformat()
    index["total_episodes"] = len(index["episodes"])
    with open(TAKEAWAYS_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def extract_takeaways_from_text(transcript_text: str, max_chars: int = 15000) -> Optional[dict]:
    """Use Claude to extract takeaways from transcript text."""
    # Truncate very long transcripts
    if len(transcript_text) > max_chars:
        transcript_text = transcript_text[:max_chars] + "\n\n[TRANSCRIPT TRUNCATED]"

    try:
        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT + transcript_text
            }]
        )

        # Parse the JSON from the response
        response_text = response.content[0].text

        # Find JSON block
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "{" in response_text:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
        else:
            print(f"  Warning: Could not find JSON in response")
            return None

        takeaways = json.loads(json_str)
        return takeaways

    except json.JSONDecodeError as e:
        print(f"  Error parsing JSON: {e}")
        return None
    except Exception as e:
        print(f"  Error calling Claude: {e}")
        return None


def process_json_file(file_path: Path, index: dict, force: bool = False) -> int:
    """Process a single JSON file and extract takeaways for all episodes."""
    print(f"\nProcessing: {file_path.name}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Determine the source name
    source_name = file_path.stem

    # Handle different JSON structures
    episodes = []
    if "videos" in data:
        episodes = data["videos"]
        content_type = "video"
    elif "episodes" in data:
        episodes = data["episodes"]
        content_type = "episode"
    elif "episode" in data:
        episodes = [data["episode"]]
        content_type = "episode"
    elif "chunks" in data:
        # Single document with chunks (like PDFs)
        full_text = "\n\n".join(c.get("text", "") for c in data["chunks"])
        episodes = [{
            "title": data.get("title", source_name),
            "transcript": {"full_text": full_text}
        }]
        content_type = "document"
    else:
        print(f"  Unknown structure, skipping")
        return 0

    processed = 0
    for ep in episodes:
        title = ep.get("title", ep.get("episode_title", "Unknown"))
        episode_id = generate_episode_id(source_name, title)

        # Skip if already processed (unless force)
        if episode_id in index["episodes"] and not force:
            continue

        # Get transcript text
        transcript = ep.get("transcript", {})
        if isinstance(transcript, dict):
            full_text = transcript.get("full_text", "")
            if not full_text and transcript.get("segments"):
                full_text = " ".join(s.get("text", "") for s in transcript["segments"])
        elif isinstance(transcript, str):
            full_text = transcript
        else:
            full_text = ""

        if not full_text or len(full_text) < 500:
            print(f"  Skipping '{title[:50]}...' - insufficient transcript")
            continue

        print(f"  Extracting: {title[:60]}...")

        takeaways = extract_takeaways_from_text(full_text)

        if takeaways:
            index["episodes"][episode_id] = {
                "source": source_name,
                "title": title,
                "content_type": content_type,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                **takeaways
            }
            processed += 1
            print(f"    Done - {len(takeaways.get('key_takeaways', []))} takeaways")

            # Save after each episode to preserve progress
            save_takeaways_index(index)

    return processed


def process_all_sources(force: bool = False, limit: Optional[int] = None):
    """Process all JSON files in the output directory."""
    index = load_takeaways_index()

    json_files = list(OUTPUT_DIR.glob("*.json"))
    print(f"Found {len(json_files)} JSON files in output/")

    total_processed = 0

    for file_path in sorted(json_files):
        # Skip certain files
        if file_path.name in ["test_questions.json", "eval_results.json", "playlist_transcripts.json"]:
            continue

        processed = process_json_file(file_path, index, force=force)
        total_processed += processed

        if limit and total_processed >= limit:
            print(f"\nReached limit of {limit} episodes")
            break

    save_takeaways_index(index)
    print(f"\n{'='*60}")
    print(f"Extraction Complete!")
    print(f"{'='*60}")
    print(f"Total episodes processed this run: {total_processed}")
    print(f"Total episodes in index: {len(index['episodes'])}")
    print(f"Takeaways saved to: {TAKEAWAYS_FILE}")


def search_takeaways(query: str, limit: int = 10) -> list[dict]:
    """Search takeaways by keyword in titles, topics, or takeaways."""
    index = load_takeaways_index()
    query_lower = query.lower()
    results = []

    for episode_id, ep in index["episodes"].items():
        score = 0

        # Search in title
        if query_lower in ep.get("title", "").lower():
            score += 3

        # Search in subject area
        if query_lower in ep.get("subject_area", "").lower():
            score += 2

        # Search in topics
        for topic in ep.get("topics", []):
            if query_lower in topic.lower():
                score += 2

        # Search in takeaways
        for takeaway in ep.get("key_takeaways", []):
            if query_lower in takeaway.lower():
                score += 1

        # Search in action items
        for action in ep.get("action_items", []):
            if query_lower in action.lower():
                score += 1

        if score > 0:
            results.append({"episode_id": episode_id, "score": score, **ep})

    # Sort by score and return top results
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def get_takeaways_by_category(category: str) -> list[dict]:
    """Get all takeaways for a specific subject area."""
    index = load_takeaways_index()
    category_lower = category.lower()

    results = []
    for episode_id, ep in index["episodes"].items():
        if category_lower in ep.get("subject_area", "").lower():
            results.append({"episode_id": episode_id, **ep})

    return results


def print_summary():
    """Print a summary of the takeaways index."""
    index = load_takeaways_index()

    print(f"\nTakeaways Index Summary")
    print(f"{'='*60}")
    print(f"Total episodes: {len(index['episodes'])}")
    print(f"Last updated: {index.get('updated_at', 'Never')}")

    # Count by subject area
    categories = {}
    all_topics = {}

    for ep in index["episodes"].values():
        cat = ep.get("subject_area", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1

        for topic in ep.get("topics", []):
            all_topics[topic] = all_topics.get(topic, 0) + 1

    print(f"\nBy Subject Area:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print(f"\nTop 15 Topics:")
    for topic, count in sorted(all_topics.items(), key=lambda x: -x[1])[:15]:
        print(f"  {topic}: {count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract key takeaways from episode transcripts")
    parser.add_argument("--force", action="store_true", help="Re-extract even if already processed")
    parser.add_argument("--limit", type=int, help="Limit number of episodes to process")
    parser.add_argument("--summary", action="store_true", help="Print summary of existing takeaways")
    parser.add_argument("--search", type=str, help="Search takeaways by keyword")
    parser.add_argument("--category", type=str, help="List takeaways by category")

    args = parser.parse_args()

    if args.summary:
        print_summary()
    elif args.search:
        results = search_takeaways(args.search)
        print(f"\nSearch results for '{args.search}':")
        for r in results:
            print(f"\n[{r['source']}] {r['title']}")
            print(f"  Category: {r.get('subject_area', 'N/A')}")
            print(f"  Topics: {', '.join(r.get('topics', []))}")
            for t in r.get("key_takeaways", [])[:2]:
                print(f"  - {t}")
    elif args.category:
        results = get_takeaways_by_category(args.category)
        print(f"\nEpisodes in category '{args.category}': {len(results)}")
        for r in results:
            print(f"\n[{r['source']}] {r['title']}")
            for t in r.get("key_takeaways", [])[:2]:
                print(f"  - {t}")
    else:
        process_all_sources(force=args.force, limit=args.limit)
