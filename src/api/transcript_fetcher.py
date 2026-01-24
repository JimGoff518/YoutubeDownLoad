"""Transcript extraction using youtube-transcript-api"""

from typing import List, Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

from ..config import config
from ..models.transcript import Transcript, TranscriptSegment


class TranscriptFetcher:
    """Fetcher for YouTube video transcripts"""

    def __init__(self, preferred_languages: Optional[List[str]] = None):
        """Initialize transcript fetcher

        Args:
            preferred_languages: List of preferred language codes (e.g., ['en', 'es'])
        """
        self.preferred_languages = preferred_languages or config.preferred_languages

        # Lazy load audio tools
        self.audio_downloader = None
        self.whisper_transcriber = None

    def fetch_transcript(self, video_id: str) -> Transcript:
        """Fetch transcript for a video

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript object (available=False if transcript not available)
        """
        try:
            # Try to get transcript in preferred languages
            transcript_data = None
            language_used = None

            # Try each preferred language
            for lang in self.preferred_languages:
                try:
                    transcript_data = YouTubeTranscriptApi.get_transcript(
                        video_id, languages=[lang]
                    )
                    language_used = lang
                    break
                except Exception:
                    continue

            # If no preferred language worked, try without language specification
            if not transcript_data:
                try:
                    transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
                    language_used = "unknown"
                except Exception:
                    pass

            # If we got transcript data, parse it
            if transcript_data:
                segments = [
                    TranscriptSegment(
                        text=item["text"],
                        start=item["start"],
                        duration=item["duration"],
                    )
                    for item in transcript_data
                ]

                return Transcript(
                    available=True,
                    language=language_used,
                    is_auto_generated=True,  # API doesn't distinguish in simple mode
                    segments=segments,
                )

            # No YouTube transcript available - try audio fallback if enabled
            if config.enable_audio_fallback:
                print(f"No YouTube transcript for {video_id}, trying audio transcription...")
                return self._transcribe_from_audio(video_id)

            return Transcript(available=False)

        except TranscriptsDisabled:
            # Transcripts are disabled - try audio fallback if enabled
            if config.enable_audio_fallback:
                print(f"Transcripts disabled for {video_id}, trying audio transcription...")
                return self._transcribe_from_audio(video_id)
            return Transcript(available=False)

        except VideoUnavailable:
            # Video is unavailable (private, deleted, etc.)
            return Transcript(available=False)

        except Exception as e:
            # Any other error - try audio fallback if enabled
            print(f"Warning: Error fetching transcript for {video_id}: {str(e)}")
            if config.enable_audio_fallback:
                print(f"Trying audio transcription fallback...")
                return self._transcribe_from_audio(video_id)
            return Transcript(available=False)

    def _transcribe_from_audio(self, video_id: str) -> Transcript:
        """Transcribe video from downloaded audio using Whisper

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript object
        """
        try:
            # Lazy load audio tools
            if self.audio_downloader is None:
                from .audio_downloader import AudioDownloader
                self.audio_downloader = AudioDownloader()

            if self.whisper_transcriber is None:
                from .whisper_transcriber import WhisperTranscriber
                self.whisper_transcriber = WhisperTranscriber(model_name=config.whisper_model)

            # Download audio
            audio_path = self.audio_downloader.download_audio(video_id)
            if not audio_path:
                return Transcript(available=False)

            # Transcribe
            transcript = self.whisper_transcriber.transcribe_audio(
                audio_path,
                language=self.preferred_languages[0] if self.preferred_languages else None
            )

            # Cleanup if configured
            if config.cleanup_audio and audio_path:
                self.audio_downloader.cleanup(video_id)

            return transcript

        except Exception as e:
            print(f"Error in audio transcription fallback for {video_id}: {str(e)}")
            return Transcript(available=False)

    def fetch_transcript_with_retry(
        self, video_id: str, max_retries: int = 3
    ) -> Transcript:
        """Fetch transcript with retry logic

        Args:
            video_id: YouTube video ID
            max_retries: Maximum number of retry attempts

        Returns:
            Transcript object
        """
        import time

        for attempt in range(max_retries):
            try:
                return self.fetch_transcript(video_id)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    print(
                        f"Retry {attempt + 1}/{max_retries} for {video_id} "
                        f"after {wait_time}s: {str(e)}"
                    )
                    time.sleep(wait_time)
                else:
                    print(f"Failed to fetch transcript for {video_id}: {str(e)}")
                    return Transcript(available=False)

        return Transcript(available=False)
