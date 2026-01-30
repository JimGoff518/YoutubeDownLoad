"""Retry failed transcriptions with verbose logging and better chunking"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from openai import OpenAI

# Configuration
MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024  # 24MB (OpenAI limit is 25MB)
CHUNK_DURATION_SECONDS = 600  # 10 minutes chunks for more reliable uploads


def get_audio_duration(audio_path: Path) -> Optional[float]:
    """Get duration of audio file in seconds using ffprobe"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        print(f"  Error getting duration: {e}")
    return None


def split_audio_to_chunks(audio_path: Path, temp_dir: Path) -> List[Path]:
    """Split audio file into chunks"""
    duration = get_audio_duration(audio_path)
    if not duration:
        print(f"  Could not determine audio duration")
        return []

    chunks = []
    chunk_num = 0
    start_time = 0

    num_chunks = int(duration // CHUNK_DURATION_SECONDS) + (1 if duration % CHUNK_DURATION_SECONDS > 0 else 0)
    print(f"  Splitting {duration/60:.1f} min audio into {num_chunks} chunks...")

    while start_time < duration:
        chunk_path = temp_dir / f"chunk_{chunk_num}.mp3"

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-ss", str(start_time),
                "-t", str(CHUNK_DURATION_SECONDS),
                "-ac", "1",  # Mono
                "-ab", "64k",  # 64kbps
                "-ar", "16000",  # 16kHz (Whisper's native rate)
                str(chunk_path)
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and chunk_path.exists():
            size_mb = chunk_path.stat().st_size / (1024 * 1024)
            print(f"    Chunk {chunk_num}: {size_mb:.1f}MB")
            chunks.append(chunk_path)
        else:
            print(f"    Failed to create chunk {chunk_num}: {result.stderr[:200]}")
            break

        start_time += CHUNK_DURATION_SECONDS
        chunk_num += 1

    return chunks


def transcribe_chunk(client: OpenAI, chunk_path: Path, language: Optional[str] = None) -> dict:
    """Transcribe a single audio chunk"""
    with open(chunk_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    segments = []
    for seg in response.segments or []:
        segments.append({
            "text": seg.text.strip(),
            "start": seg.start,
            "duration": seg.end - seg.start,
            "end": seg.end
        })

    return {
        "segments": segments,
        "language": response.language or language or "en"
    }


def transcribe_audio_file(audio_path: Path, temp_dir: Path) -> dict:
    """Transcribe a single audio file with chunking support"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)

    file_size = audio_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    print(f"  File size: {file_size_mb:.1f}MB")

    # For files under the limit, try direct upload first
    if file_size <= MAX_FILE_SIZE_BYTES:
        print(f"  Attempting direct transcription...")
        try:
            result = transcribe_chunk(client, audio_path)
            if result["segments"]:
                return {
                    "available": True,
                    "language": result["language"],
                    "is_auto_generated": True,
                    "segments": result["segments"]
                }
        except Exception as e:
            print(f"  Direct upload failed: {e}")

    # Need to compress or split
    print(f"  File too large or direct upload failed, splitting into chunks...")

    # Create chunks
    chunks = split_audio_to_chunks(audio_path, temp_dir)

    if not chunks:
        print(f"  Failed to create chunks")
        return {"available": False}

    # Transcribe each chunk
    all_segments = []
    detected_language = "en"
    time_offset = 0.0

    for i, chunk_path in enumerate(chunks):
        print(f"  Transcribing chunk {i+1}/{len(chunks)}...")
        try:
            result = transcribe_chunk(client, chunk_path)
            detected_language = result["language"]

            # Adjust timestamps for this chunk
            for seg in result["segments"]:
                all_segments.append({
                    "text": seg["text"],
                    "start": seg["start"] + time_offset,
                    "duration": seg["duration"],
                    "end": seg["end"] + time_offset
                })

            print(f"    Got {len(result['segments'])} segments")

        except Exception as e:
            print(f"    Error transcribing chunk {i+1}: {e}")

        # Update offset for next chunk
        time_offset += CHUNK_DURATION_SECONDS

        # Cleanup chunk file
        try:
            chunk_path.unlink()
        except Exception:
            pass

    if all_segments:
        print(f"  Total segments: {len(all_segments)}")
        return {
            "available": True,
            "language": detected_language,
            "is_auto_generated": True,
            "segments": all_segments
        }
    else:
        return {"available": False}


def main():
    # Paths
    source_dir = Path(r"C:\Users\jim\Videos\4K Video Downloader+\Personal Injury Mastermind (PIM) Podcast (Season 1)")
    output_file = Path(r"C:\Users\jim\OneDrive\Documents\Delisi\pim_podcast_transcripts.json")
    temp_dir = Path(r"C:\Users\jim\AppData\Local\Temp\transcription_chunks")

    # Create temp directory
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Load existing data
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Find failed episodes
    failed_filenames = {e['filename'] for e in data.get('errors', [])}
    print(f"\nFound {len(failed_filenames)} failed episodes to retry\n")

    # Track progress
    retried = 0
    newly_successful = 0
    still_failed = []

    for filename in sorted(failed_filenames):
        audio_path = source_dir / filename
        if not audio_path.exists():
            print(f"File not found: {filename}")
            still_failed.append({"filename": filename, "error": "File not found"})
            continue

        retried += 1
        print(f"\n[{retried}/{len(failed_filenames)}] Retrying: {filename}")

        try:
            transcript = transcribe_audio_file(audio_path, temp_dir)

            if transcript["available"]:
                newly_successful += 1
                print(f"  SUCCESS! {len(transcript['segments'])} segments")

                # Calculate computed fields
                full_text = " ".join(seg["text"] for seg in transcript["segments"])
                transcript["full_text"] = full_text
                transcript["word_count"] = len(full_text.split())
                transcript["character_count"] = len(full_text)

                # Find and update the episode in the data
                for ep in data['episodes']:
                    if ep['filename'] == filename:
                        ep['transcript'] = transcript
                        break
                else:
                    # Add new episode entry
                    import re
                    ep_match = re.search(r'Ep\.?\s*(\d+)', filename, re.IGNORECASE)
                    episode_number = int(ep_match.group(1)) if ep_match else None
                    data['episodes'].append({
                        'filename': filename,
                        'title': audio_path.stem,
                        'episode_number': episode_number,
                        'transcript': transcript
                    })

                # Remove from errors list
                data['errors'] = [e for e in data['errors'] if e['filename'] != filename]

            else:
                print(f"  FAILED: No transcript generated")
                still_failed.append({"filename": filename, "error": "No transcript generated"})

        except Exception as e:
            print(f"  ERROR: {e}")
            still_failed.append({"filename": filename, "error": str(e)})

        # Save progress after each episode
        data['extraction_metadata']['successful_extractions'] = sum(
            1 for ep in data['episodes'] if ep.get('transcript', {}).get('available', False)
        )
        data['extraction_metadata']['failed_extractions'] = len(data['errors']) + len(still_failed)
        data['extraction_metadata']['extracted_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Sort episodes by episode number
        data['episodes'].sort(key=lambda x: x.get('episode_number') or 999)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Final summary
    print(f"\n{'='*60}")
    print("Retry Complete!")
    print(f"{'='*60}")
    print(f"Total retried: {retried}")
    print(f"Newly successful: {newly_successful}")
    print(f"Still failed: {len(still_failed)}")
    print(f"{'='*60}")

    # Clean up temp directory
    try:
        for f in temp_dir.iterdir():
            f.unlink()
        temp_dir.rmdir()
    except Exception:
        pass


if __name__ == '__main__':
    main()
