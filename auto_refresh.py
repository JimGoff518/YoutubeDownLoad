"""Auto-refresh pipeline for Bill AI Machine knowledge base.

Checks monitored YouTube channels/playlists for new episodes,
extracts transcripts, ingests into Pinecone, and runs takeaways extraction.

Usage:
    python auto_refresh.py                    # Full refresh (all enabled sources)
    python auto_refresh.py --source "PI Wingman"  # Single source
    python auto_refresh.py --dry-run          # Check only, no ingestion
    python auto_refresh.py --backfill         # Populate known_video_ids from output/ files
"""

import json
import os
import sys
import time
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Reuse existing infrastructure
from src.api.youtube_client import YouTubeClient
from src.api.transcript_fetcher import TranscriptFetcher
from src.processors.video_processor import VideoProcessor
from ingest_to_pinecone import chunk_text, get_embedding, generate_chunk_id
from extract_takeaways import (
    extract_takeaways_from_text,
    load_takeaways_index,
    save_takeaways_index,
    generate_episode_id,
)

# Paths
REGISTRY_PATH = Path(__file__).parent / "sources_registry.json"
REFRESH_LOG_PATH = Path(__file__).parent / "refresh_log.json"
OUTPUT_DIR = Path(__file__).parent / "output"

# Pinecone client (lazy init)
_pinecone_index = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        _pinecone_index = pc.Index("legal-docs")
    return _pinecone_index


def load_registry():
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry):
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


# -- Check for new episodes ---------------------------------------------------

def check_source(youtube_client, source):
    """Check a single source for new video IDs. Returns list of new IDs."""
    known = set(source.get("known_video_ids", []))

    if source["type"] == "youtube_channel":
        all_ids = youtube_client.get_channel_videos(source["channel_id"])
    elif source["type"] == "youtube_playlist":
        all_ids = youtube_client.get_playlist_videos(source["playlist_id"])
    else:
        logger.warning(f"Unknown source type: {source['type']}")
        return []

    new_ids = [vid for vid in all_ids if vid not in known]
    return new_ids


# -- Extract, chunk, embed a single video -------------------------------------

def ingest_video(youtube_client, video_processor, video_id, source):
    """Extract transcript, chunk, embed, and upsert a single video to Pinecone.

    Returns (video_dict, chunk_count) on success, or (None, error_msg) on failure.
    """
    source_name = source["output_source_name"]

    # Get video details from YouTube API
    details_list = youtube_client.get_video_details_batch([video_id])
    if not details_list:
        return None, "video_not_found"

    details = details_list[0]

    # Process video (fetches transcript, calculates ML features)
    video = video_processor.process_video(details)

    if not video.transcript.available:
        return None, "no_transcript"

    full_text = video.transcript.full_text
    if not full_text or len(full_text) < 100:
        return None, "transcript_too_short"

    # Chunk the transcript
    chunks = chunk_text(full_text)
    if not chunks:
        return None, "no_chunks"

    # Embed and upsert to Pinecone
    pinecone_index = get_pinecone_index()
    vectors = []

    for chunk in chunks:
        enriched_text = f"[Source: {source_name}] [Episode: {video.title}]\n\n{chunk['text']}"
        try:
            embedding = get_embedding(enriched_text)
        except Exception as e:
            logger.error(f"  Embedding error for chunk {chunk['chunk_index']}: {e}")
            continue

        chunk_id = generate_chunk_id(source_name, video.title, chunk["chunk_index"])
        vectors.append({
            "id": chunk_id,
            "values": embedding,
            "metadata": {
                "source": source_name,
                "episode_title": video.title,
                "chunk_index": chunk["chunk_index"],
                "total_chunks": len(chunks),
                "text": chunk["text"],
            },
        })

    # Batch upsert
    for i in range(0, len(vectors), 100):
        pinecone_index.upsert(vectors=vectors[i : i + 100])

    # Build video dict for output JSON
    video_dict = {
        "id": video.id,
        "title": video.title,
        "description": video.description or "",
        "published_at": video.published_at.isoformat() if video.published_at else None,
        "duration_seconds": video.duration_seconds,
        "view_count": video.view_count,
        "like_count": video.like_count,
        "comment_count": video.comment_count,
        "tags": video.tags or [],
        "transcript": {
            "available": True,
            "language": video.transcript.language,
            "is_auto_generated": video.transcript.is_auto_generated,
            "segments": [{"text": s.text, "start": s.start, "duration": s.duration}
                         for s in video.transcript.segments],
            "full_text": full_text,
            "word_count": video.transcript.word_count,
        },
    }

    return video_dict, len(vectors)


# -- Append to output JSON ----------------------------------------------------

def append_to_output(source, video_dicts):
    """Append new video entries to the source's output JSON file."""
    source_name = source["output_source_name"]
    output_file = OUTPUT_DIR / f"{source_name}.json"

    if output_file.exists():
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "extraction_metadata": {
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "extractor_version": "1.0.0-autorefresh",
                "source_type": "youtube",
                "total_videos_processed": 0,
                "successful_extractions": 0,
            },
            "videos": [],
            "errors": [],
        }

    data["videos"].extend(video_dicts)
    data["extraction_metadata"]["total_videos_processed"] = len(data["videos"])
    data["extraction_metadata"]["successful_extractions"] = len(data["videos"])

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"  Saved {len(video_dicts)} new episodes to {output_file.name}")


# -- Extract takeaways for new episodes ---------------------------------------

def extract_takeaways_for_videos(source, video_dicts):
    """Run takeaways extraction for a list of new videos."""
    source_name = source["output_source_name"]
    takeaways_index = load_takeaways_index()
    count = 0

    for vd in video_dicts:
        title = vd["title"]
        full_text = vd["transcript"].get("full_text", "")

        if not full_text or len(full_text) < 500:
            continue

        episode_id = generate_episode_id(source_name, title)
        if episode_id in takeaways_index["episodes"]:
            continue

        logger.info(f"  Extracting takeaways: {title[:60]}...")
        takeaways = extract_takeaways_from_text(full_text)

        if takeaways:
            takeaways_index["episodes"][episode_id] = {
                "source": source_name,
                "title": title,
                "content_type": "video",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                **takeaways,
            }
            count += 1
            save_takeaways_index(takeaways_index)

    return count


# -- Backfill known IDs from existing output files ----------------------------

def backfill_known_ids(registry):
    """Populate known_video_ids from existing output JSON files."""
    for source in registry["sources"]:
        source_name = source["output_source_name"]
        output_file = OUTPUT_DIR / f"{source_name}.json"

        if not output_file.exists():
            continue

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        videos = data.get("videos", data.get("episodes", []))
        existing_ids = [v.get("id") for v in videos if v.get("id")]
        source["known_video_ids"] = existing_ids
        logger.info(f"  {source['name']}: backfilled {len(existing_ids)} known IDs")

    save_registry(registry)
    logger.info("Backfill complete.")


# -- Refresh log --------------------------------------------------------------

def save_refresh_log(results):
    """Save/append to refresh_log.json."""
    log = []
    if REFRESH_LOG_PATH.exists():
        with open(REFRESH_LOG_PATH, encoding="utf-8") as f:
            log = json.load(f)

    log.append(results)

    # Keep last 50 runs
    log = log[-50:]

    with open(REFRESH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# -- Main pipeline -------------------------------------------------------------

def run_refresh(source_filter=None, dry_run=False):
    """Main refresh pipeline. Returns results dict."""
    registry = load_registry()

    youtube_client = YouTubeClient(os.getenv("YOUTUBE_API_KEY"))
    transcript_fetcher = TranscriptFetcher()
    video_processor = VideoProcessor(youtube_client, transcript_fetcher)

    results = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sources_checked": 0,
        "new_episodes_found": 0,
        "episodes_ingested": 0,
        "chunks_created": 0,
        "takeaways_extracted": 0,
        "errors": [],
        "source_details": [],
    }

    for source in registry["sources"]:
        if not source.get("enabled", True):
            continue
        if source_filter and source["name"] != source_filter:
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Checking: {source['name']}")
        results["sources_checked"] += 1

        try:
            new_ids = check_source(youtube_client, source)
            logger.info(f"  Found {len(new_ids)} new episodes")
            results["new_episodes_found"] += len(new_ids)

            source_result = {
                "name": source["name"],
                "new_episodes": len(new_ids),
                "ingested": 0,
                "errors": [],
            }

            if dry_run or not new_ids:
                results["source_details"].append(source_result)
                continue

            # Process each new video
            video_dicts = []
            for video_id in new_ids:
                logger.info(f"  Processing: {video_id}")
                try:
                    video_dict, chunk_count_or_error = ingest_video(
                        youtube_client, video_processor, video_id, source
                    )
                    if video_dict:
                        video_dicts.append(video_dict)
                        results["episodes_ingested"] += 1
                        results["chunks_created"] += chunk_count_or_error
                        source_result["ingested"] += 1

                        # Mark as known
                        if "known_video_ids" not in source:
                            source["known_video_ids"] = []
                        source["known_video_ids"].append(video_id)
                    else:
                        logger.warning(f"    Skipped: {chunk_count_or_error}")
                        source_result["errors"].append({
                            "video_id": video_id,
                            "error": chunk_count_or_error,
                        })

                    # Rate limiting between videos
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"    Error processing {video_id}: {e}")
                    source_result["errors"].append({
                        "video_id": video_id,
                        "error": str(e),
                    })
                    results["errors"].append({
                        "source": source["name"],
                        "video_id": video_id,
                        "error": str(e),
                    })

            # Save output JSON
            if video_dicts:
                append_to_output(source, video_dicts)

                # Extract takeaways
                takeaway_count = extract_takeaways_for_videos(source, video_dicts)
                results["takeaways_extracted"] += takeaway_count

            results["source_details"].append(source_result)

        except Exception as e:
            logger.error(f"  Error checking source {source['name']}: {e}")
            results["errors"].append({
                "source": source["name"],
                "error": str(e),
            })

    results["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Save updated registry
    save_registry(registry)

    # Save refresh log
    save_refresh_log(results)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Refresh Complete!")
    logger.info(f"  Sources checked: {results['sources_checked']}")
    logger.info(f"  New episodes found: {results['new_episodes_found']}")
    logger.info(f"  Episodes ingested: {results['episodes_ingested']}")
    logger.info(f"  Chunks created: {results['chunks_created']}")
    logger.info(f"  Takeaways extracted: {results['takeaways_extracted']}")
    logger.info(f"  Errors: {len(results['errors'])}")

    return results


# -- CLI -----------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-refresh knowledge base")
    parser.add_argument("--source", help="Refresh a single source by name")
    parser.add_argument("--dry-run", action="store_true", help="Check only, no ingestion")
    parser.add_argument("--backfill", action="store_true", help="Populate known IDs from output files")
    args = parser.parse_args()

    if args.backfill:
        registry = load_registry()
        backfill_known_ids(registry)
    else:
        run_refresh(source_filter=args.source, dry_run=args.dry_run)
