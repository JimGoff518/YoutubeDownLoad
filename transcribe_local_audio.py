"""Batch transcribe local audio files using OpenAI Whisper API"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.whisper_transcriber import WhisperTranscriber
from src.models.transcript import Transcript


def get_episode_number(filename: str) -> tuple:
    """Extract episode number from filename for sorting"""
    # Try to match "Ep. XX" or "Ep  XX" or "Ep XX"
    match = re.search(r'Ep\.?\s*(\d+)', filename, re.IGNORECASE)
    if match:
        return (int(match.group(1)), filename)
    return (999, filename)  # Put unmatched at end


def transcribe_audio_files(
    source_dir: str,
    output_file: str,
    skip_existing: bool = True
):
    """Transcribe all audio files in a directory

    Args:
        source_dir: Directory containing audio files
        output_file: Path to output JSON file
        skip_existing: Skip episodes already in output file
    """
    source_path = Path(source_dir)
    output_path = Path(output_file)

    # Get all audio files (m4a, mp3, wav, etc)
    audio_extensions = {'.m4a', '.mp3', '.wav', '.ogg', '.flac', '.aac'}
    all_files = []
    for ext in audio_extensions:
        all_files.extend(source_path.glob(f'*{ext}'))

    # Filter out duplicates and partial files
    audio_files = []
    seen_episodes = set()

    for f in all_files:
        # Skip partial download files
        if '.part' in f.name:
            continue
        # Skip files with (1) suffix if we already have the original
        if '(1)' in f.name:
            original_name = f.name.replace(' (1)', '')
            if (source_path / original_name).exists():
                continue

        # Extract episode identifier
        ep_match = re.search(r'Ep\.?\s*(\d+)', f.name, re.IGNORECASE)
        if ep_match:
            ep_num = int(ep_match.group(1))
            if ep_num in seen_episodes:
                continue
            seen_episodes.add(ep_num)

        audio_files.append(f)

    # Sort by episode number
    audio_files.sort(key=lambda f: get_episode_number(f.name))

    print(f"\nFound {len(audio_files)} unique audio files to process")

    # Load existing data if available
    existing_episodes = {}
    if skip_existing and output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                for ep in existing_data.get('episodes', []):
                    if ep.get('transcript', {}).get('available', False):
                        existing_episodes[ep['filename']] = ep
                print(f"Found {len(existing_episodes)} existing transcribed episodes")
        except Exception as e:
            print(f"Could not load existing data: {e}")

    # Initialize transcriber
    transcriber = WhisperTranscriber()

    # Process each file
    episodes = list(existing_episodes.values())
    errors = []

    for i, audio_file in enumerate(audio_files, 1):
        filename = audio_file.name

        # Handle filenames with emojis/special chars in print
        safe_filename = filename.encode('ascii', 'replace').decode('ascii')

        # Skip if already transcribed
        if filename in existing_episodes:
            print(f"[{i}/{len(audio_files)}] Skipping (already done): {safe_filename}")
            continue

        print(f"\n[{i}/{len(audio_files)}] Processing: {safe_filename}")

        try:
            # Extract episode info from filename
            title = audio_file.stem
            ep_match = re.search(r'Ep\.?\s*(\d+)', filename, re.IGNORECASE)
            episode_number = int(ep_match.group(1)) if ep_match else None

            # Transcribe
            transcript = transcriber.transcribe_audio(audio_file)

            # Create episode entry
            episode_data = {
                'filename': filename,
                'title': title,
                'episode_number': episode_number,
                'transcript': transcript.model_dump(mode='json'),
            }

            episodes.append(episode_data)

            if transcript.available:
                print(f"  Transcribed: {transcript.word_count} words, {len(transcript.segments)} segments")
            else:
                print(f"  Transcript not available")
                errors.append({
                    'filename': filename,
                    'error_type': 'TranscriptionFailed',
                    'error_message': 'No transcript was generated'
                })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            errors.append({
                'filename': filename,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })

        # Save progress after each episode
        output_data = {
            'schema_version': '1.0.0',
            'extraction_metadata': {
                'extracted_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source_directory': str(source_path.absolute()),
                'total_files_found': len(audio_files),
                'total_episodes_processed': len(episodes),
                'successful_extractions': sum(1 for ep in episodes if ep.get('transcript', {}).get('available', False)),
                'failed_extractions': len(errors),
            },
            'podcast': {
                'title': source_path.name,
                'season': 1,
            },
            'episodes': sorted(episodes, key=lambda x: x.get('episode_number') or 999),
            'errors': errors,
        }

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Final summary
    successful = sum(1 for ep in episodes if ep.get('transcript', {}).get('available', False))
    print(f"\n{'='*60}")
    print("Transcription Complete!")
    print(f"{'='*60}")
    print(f"Total episodes: {len(episodes)}")
    print(f"Successful transcriptions: {successful}")
    print(f"Failed: {len(errors)}")
    print(f"Output saved to: {output_path.absolute()}")
    print(f"{'='*60}")


if __name__ == '__main__':
    source_dir = r"C:\Users\jim\Downloads\PIM_extracted\Season 1\Personal Injury Mastermind (PIM) Podcast (Season 1)"
    output_file = r"C:\Users\jim\OneDrive\Documents\Bill AI Machine\output\PIM_Podcast_Season1.json"

    transcribe_audio_files(source_dir, output_file)
