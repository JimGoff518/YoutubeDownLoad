"""Configuration management"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration"""

    def __init__(self):
        # Debug: Print all environment variables that start with relevant prefixes
        print("=== Environment Variables Debug ===")
        for key in sorted(os.environ.keys()):
            if any(prefix in key.upper() for prefix in ['YOUTUBE', 'WHISPER', 'ENABLE', 'CLEANUP', 'OUTPUT', 'PLAYLIST', 'PREFERRED']):
                print(f"{key} = {os.environ[key][:50]}..." if len(os.environ[key]) > 50 else f"{key} = {os.environ[key]}")
        print("===================================")

        # API Configuration
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY", "")
        if not self.youtube_api_key:
            raise ValueError(
                "YOUTUBE_API_KEY not found in environment variables. "
                "Please set it in your .env file or environment."
            )

        # Processing Configuration
        self.max_concurrent_videos = int(os.getenv("MAX_CONCURRENT_VIDEOS", "5"))

        # Output Configuration
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))

        # Transcript Configuration
        self.preferred_languages = self._parse_languages(
            os.getenv("PREFERRED_LANGUAGES", "en,en-US,en-GB")
        )
        self.fallback_to_auto_generated = self._parse_bool(
            os.getenv("FALLBACK_TO_AUTO_GENERATED", "true")
        )

        # API Retry Configuration
        self.retry_attempts = int(os.getenv("RETRY_ATTEMPTS", "3"))
        self.retry_delay_seconds = int(os.getenv("RETRY_DELAY_SECONDS", "2"))
        self.timeout_seconds = int(os.getenv("TIMEOUT_SECONDS", "30"))

        # Audio Transcription Fallback
        self.enable_audio_fallback = self._parse_bool(
            os.getenv("ENABLE_AUDIO_FALLBACK", "false")
        )
        self.whisper_model = os.getenv("WHISPER_MODEL", "base")
        self.cleanup_audio = self._parse_bool(
            os.getenv("CLEANUP_AUDIO", "true")
        )

    def _parse_languages(self, lang_str: str) -> List[str]:
        """Parse comma-separated language codes"""
        return [lang.strip() for lang in lang_str.split(",") if lang.strip()]

    def _parse_bool(self, value: str) -> bool:
        """Parse boolean from string"""
        return value.lower() in ("true", "1", "yes", "on")

    def validate(self) -> None:
        """Validate configuration"""
        if not self.youtube_api_key:
            raise ValueError("YouTube API key is required")

        if self.max_concurrent_videos < 1:
            raise ValueError("MAX_CONCURRENT_VIDEOS must be at least 1")

        if not self.preferred_languages:
            raise ValueError("At least one preferred language must be specified")


# Global configuration instance
config = Config()
