"""Transcribe specific video files to JSON"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.whisper_transcriber import WhisperTranscriber


def transcribe_videos(video_files: list[str], output_file: str):
    """Transcribe video files and save to JSON

    Args:
        video_files: List of paths to video files
        output_file: Path to output JSON file
    """
    output_path = Path(output_file)

    # Initialize transcriber
    transcriber = WhisperTranscriber()

    episodes = []
    errors = []

    for i, video_path in enumerate(video_files, 1):
        video_file = Path(video_path)

        if not video_file.exists():
            print(f"[{i}/{len(video_files)}] File not found: {video_path}")
            errors.append({
                'filename': video_file.name,
                'error_type': 'FileNotFound',
                'error_message': f'File does not exist: {video_path}'
            })
            continue

        # Safe filename for printing
        safe_filename = video_file.name.encode('ascii', 'replace').decode('ascii')
        print(f"\n[{i}/{len(video_files)}] Processing: {safe_filename}")

        try:
            # Transcribe
            transcript = transcriber.transcribe_audio(video_file)

            # Create episode entry
            episode_data = {
                'filename': video_file.name,
                'title': video_file.stem,
                'transcript': transcript.model_dump(mode='json'),
            }

            episodes.append(episode_data)

            if transcript.available:
                print(f"  Transcribed: {transcript.word_count} words, {len(transcript.segments)} segments")
            else:
                print(f"  Transcript not available")
                errors.append({
                    'filename': video_file.name,
                    'error_type': 'TranscriptionFailed',
                    'error_message': 'No transcript was generated'
                })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            errors.append({
                'filename': video_file.name,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })

    # Build output data
    output_data = {
        'schema_version': '1.0.0',
        'extraction_metadata': {
            'extracted_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'total_files_found': len(video_files),
            'total_episodes_processed': len(episodes),
            'successful_extractions': sum(1 for ep in episodes if ep.get('transcript', {}).get('available', False)),
            'failed_extractions': len(errors),
        },
        'episodes': episodes,
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
    print(f"Total videos: {len(video_files)}")
    print(f"Successful transcriptions: {successful}")
    print(f"Failed: {len(errors)}")
    print(f"Output saved to: {output_path.absolute()}")
    print(f"{'='*60}")


if __name__ == '__main__':
    video_files = [
        r"C:\Users\jim\Box\Downloads\PreLit Guru Session 3 Recording .mp4",
        r"C:\Users\jim\Box\Downloads\Session 1.mp4",
        r"C:\Users\jim\Box\Downloads\Session 2.mp4",
    ]

    output_file = r"C:\Users\jim\OneDrive\Documents\Bill AI Machine\output\PreLitGuru_Sessions.json"

    transcribe_videos(video_files, output_file)
