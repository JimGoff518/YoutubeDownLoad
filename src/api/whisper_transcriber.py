"""OpenAI Whisper API-based audio transcription"""

import os
from pathlib import Path
from typing import Optional
from openai import OpenAI

from ..models.transcript import Transcript, TranscriptSegment


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
        try:
            client = self._get_client()

            print(f"Transcribing audio via OpenAI API: {audio_path.name}")

            # Open audio file and send to OpenAI
            with open(audio_path, "rb") as audio_file:
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
