"""OpenAI Whisper API-based audio transcription"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from openai import OpenAI

from ..models.transcript import Transcript, TranscriptSegment

# OpenAI Whisper API limit is 25MB, use 24MB to be safe
MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024


class WhisperTranscriber:
    """Transcribe audio using OpenAI Whisper API"""

    def __init__(self, model_name: str = "whisper-1"):
        """Initialize Whisper transcriber

        Args:
            model_name: OpenAI Whisper model (currently only "whisper-1" available)
        """
        self.model_name = model_name
        self.client = None

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client"""
        if self.client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.client = OpenAI(api_key=api_key)
        return self.client

    def _compress_audio(self, audio_path: Path) -> Optional[Path]:
        """Compress audio file to fit within OpenAI's 25MB limit

        Uses ffmpeg to convert to mono MP3 at 64kbps (sufficient for speech).

        Args:
            audio_path: Path to original audio file

        Returns:
            Path to compressed file, or None if compression failed
        """
        compressed_path = audio_path.parent / f"{audio_path.stem}_compressed.mp3"

        try:
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            print(f"Compressing audio ({file_size_mb:.1f}MB) for API upload...")

            # Convert to mono MP3 at 64kbps - good enough for speech recognition
            result = subprocess.run(
                [
                    "ffmpeg", "-y",  # Overwrite output
                    "-i", str(audio_path),
                    "-ac", "1",  # Mono
                    "-ab", "64k",  # 64kbps bitrate
                    "-ar", "16000",  # 16kHz sample rate (Whisper's native rate)
                    str(compressed_path)
                ],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"FFmpeg compression failed: {result.stderr[:200]}")
                return None

            compressed_size_mb = compressed_path.stat().st_size / (1024 * 1024)
            print(f"Compressed to {compressed_size_mb:.1f}MB")

            return compressed_path

        except Exception as e:
            print(f"Error compressing audio: {str(e)}")
            return None

    def transcribe_audio(
        self, audio_path: Path, language: Optional[str] = None
    ) -> Transcript:
        """Transcribe audio file using OpenAI Whisper API

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'es') or None for auto-detect

        Returns:
            Transcript object with segments
        """
        compressed_path = None
        try:
            client = self._get_client()

            # Check file size and compress if needed
            file_size = audio_path.stat().st_size
            upload_path = audio_path

            if file_size > MAX_FILE_SIZE_BYTES:
                compressed_path = self._compress_audio(audio_path)
                if compressed_path and compressed_path.exists():
                    # Verify compressed file is under limit
                    if compressed_path.stat().st_size <= MAX_FILE_SIZE_BYTES:
                        upload_path = compressed_path
                    else:
                        print(f"Compressed file still too large, skipping...")
                        if compressed_path.exists():
                            compressed_path.unlink()
                        return Transcript(available=False)
                else:
                    print(f"Compression failed, skipping...")
                    return Transcript(available=False)

            print(f"Transcribing audio via OpenAI API: {upload_path.name}")

            # Open audio file and send to OpenAI
            with open(upload_path, "rb") as audio_file:
                # Use verbose_json to get timestamps
                response = client.audio.transcriptions.create(
                    model=self.model_name,
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            # Convert to our format
            segments = []
            for seg in response.segments or []:
                segments.append(
                    TranscriptSegment(
                        text=seg.text.strip(),
                        start=seg.start,
                        duration=seg.end - seg.start,
                    )
                )

            detected_language = response.language or language or "en"

            print(f"Transcription complete: {len(segments)} segments")

            return Transcript(
                available=True,
                language=detected_language,
                is_auto_generated=True,  # API-generated
                segments=segments,
            )

        except Exception as e:
            print(f"Error transcribing audio via OpenAI API: {str(e)}")
            return Transcript(available=False)

        finally:
            # Clean up compressed file if we created one
            if compressed_path and compressed_path.exists():
                try:
                    compressed_path.unlink()
                except Exception:
                    pass
