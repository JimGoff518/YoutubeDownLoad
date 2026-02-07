"""Extract a single YouTube video transcript, bypassing Rich console Unicode issues on Windows."""

import sys
import os
import json
from pathlib import Path

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from src.api.youtube_client import YouTubeClient
from src.api.transcript_fetcher import TranscriptFetcher
from src.processors.video_processor import VideoProcessor


def extract_video(video_url: str, output_path: str):
    """Extract a single YouTube video and save as JSON."""
    # Parse video ID from URL
    video_id = None
    if "v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0]

    if not video_id:
        print(f"Could not parse video ID from: {video_url}")
        return False

    print(f"Extracting video: {video_id}")

    client = YouTubeClient(api_key=os.getenv("YOUTUBE_API_KEY"))
    processor = VideoProcessor(youtube_client=client)

    try:
        # First get video metadata from YouTube API
        video_metadata_list = client.get_video_details([video_id])
        if not video_metadata_list:
            print(f"No metadata returned for video {video_id}")
            return False
        video_metadata = video_metadata_list[0]
        print(f"Got metadata for: {video_metadata.get('title', 'Unknown')}")

        # Then process (fetches transcript, calculates ML features)
        video = processor.process_video(video_metadata)
    except Exception as e:
        print(f"Error processing video: {e}")
        return False

    if not video:
        print("No video data returned")
        return False

    video_dict = video.model_dump(mode='json')

    output = {
        "extraction_metadata": {
            "extracted_at": str(video_dict.get("published_at", "")),
            "extractor_version": "1.0.0",
            "video_id": video_id
        },
        "videos": [video_dict],
        "errors": []
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    title = video_dict.get("title", "Unknown")
    has_transcript = video_dict.get("transcript", {}).get("available", False)
    word_count = video_dict.get("transcript", {}).get("word_count", 0)
    print(f"Title: {title}")
    print(f"Transcript: {'Yes' if has_transcript else 'No'} ({word_count} words)")
    print(f"Saved to: {output_path}")
    return True


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    if len(sys.argv) < 3:
        print("Usage: python extract_youtube.py <video_url> <output_path>")
        sys.exit(1)

    success = extract_video(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
