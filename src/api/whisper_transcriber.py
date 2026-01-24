"""Whisper-based audio transcription"""

import os
from pathlib import Path
from typing import Optional, List
import whisper

from ..models.transcript import Transcript, TranscriptSegment


# Add FFmpeg to PATH if not already available (Whisper needs it to load audio)
def _ensure_ffmpeg_in_path():
    """Ensure FFmpeg is accessible in PATH"""
    import shutil
    if not shutil.which('ffmpeg'):
        # Try default Windows installation location
        ffmpeg_bin = Path(r"C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin")
        if ffmpeg_bin.exists():
            # Add to PATH for this process
            os.environ['PATH'] = str(ffmpeg_bin) + os.pathsep + os.environ.get('PATH', '')
            print(f"Added FFmpeg to PATH: {ffmpeg_bin}")


# Ensure FFmpeg is available when module loads
_ensure_ffmpeg_in_path()


class WhisperTranscriber:
    """Transcribe audio using OpenAI Whisper"""

    def __init__(self, model_name: str = "base"):
        """Initialize Whisper transcriber

        Args:
            model_name: Whisper model to use (tiny, base, small, medium, large)
                       - tiny: Fastest, least accurate (~1GB RAM)
                       - base: Good balance (~1GB RAM) - RECOMMENDED
                       - small: Better accuracy (~2GB RAM)
                       - medium: High accuracy (~5GB RAM)
                       - large: Best accuracy (~10GB RAM)
        """
        self.model_name = model_name
        self.model = None

    def load_model(self):
        """Load Whisper model (lazy loading)"""
        if self.model is None:
            print(f"Loading Whisper model '{self.model_name}'...")
            self.model = whisper.load_model(self.model_name)
            print("Model loaded successfully")

    def transcribe_audio(
        self, audio_path: Path, language: Optional[str] = None
    ) -> Transcript:
        """Transcribe audio file

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'es') or None for auto-detect

        Returns:
            Transcript object with segments
        """
        try:
            # Load model if not already loaded
            self.load_model()

            # Transcribe
            print(f"Transcribing audio: {audio_path.name}")
            result = self.model.transcribe(
                str(audio_path),
                language=language,
                verbose=False,
            )

            # Convert to our format
            segments = []
            for seg in result.get("segments", []):
                segments.append(
                    TranscriptSegment(
                        text=seg["text"].strip(),
                        start=seg["start"],
                        duration=seg["end"] - seg["start"],
                    )
                )

            detected_language = result.get("language", language or "unknown")

            return Transcript(
                available=True,
                language=detected_language,
                is_auto_generated=True,  # Whisper-generated
                segments=segments,
            )

        except Exception as e:
            print(f"Error transcribing audio: {str(e)}")
            return Transcript(available=False)
