"""Tests for src/api/transcript_fetcher.py with mocked APIs."""

import os
from unittest.mock import patch, MagicMock

import pytest


def _make_fetcher():
    """Create a TranscriptFetcher with mocked config and API."""
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key"}):
        from importlib import reload
        import src.config
        reload(src.config)

    with patch("src.api.transcript_fetcher.YouTubeTranscriptApi") as MockApi:
        from src.api.transcript_fetcher import TranscriptFetcher
        fetcher = TranscriptFetcher(preferred_languages=["en"])
        return fetcher, MockApi


class TestFetchTranscript:
    def test_success(self):
        fetcher, MockApi = _make_fetcher()

        # Mock transcript snippet objects
        snippet1 = MagicMock()
        snippet1.text = "Hello world."
        snippet1.start = 0.0
        snippet1.duration = 2.0

        snippet2 = MagicMock()
        snippet2.text = "Goodbye."
        snippet2.start = 2.0
        snippet2.duration = 1.5

        fetcher.api.fetch.return_value = [snippet1, snippet2]

        result = fetcher.fetch_transcript("vid123")
        assert result.available is True
        assert result.language == "en"
        assert len(result.segments) == 2
        assert result.full_text == "Hello world. Goodbye."

    def test_no_transcript_returns_unavailable(self):
        fetcher, MockApi = _make_fetcher()
        fetcher.api.fetch.side_effect = Exception("No transcript")

        with patch.object(type(fetcher), '_TranscriptFetcher__class__', create=True):
            # Ensure audio fallback is disabled
            with patch("src.api.transcript_fetcher.config") as mock_config:
                mock_config.enable_audio_fallback = False
                mock_config.preferred_languages = ["en"]
                fetcher_fresh, _ = _make_fetcher()
                fetcher_fresh.api.fetch.side_effect = Exception("No transcript available")
                result = fetcher_fresh.fetch_transcript("vid123")
                assert result.available is False

    def test_tries_preferred_languages_in_order(self):
        fetcher, MockApi = _make_fetcher()
        fetcher.preferred_languages = ["es", "en"]

        call_count = 0

        def side_effect(video_id, languages=None):
            nonlocal call_count
            call_count += 1
            if languages == ["es"]:
                raise Exception("Not found")
            snippet = MagicMock()
            snippet.text = "Hello"
            snippet.start = 0.0
            snippet.duration = 1.0
            return [snippet]

        fetcher.api.fetch.side_effect = side_effect
        result = fetcher.fetch_transcript("vid123")
        assert result.available is True
        assert call_count == 2  # es failed, en succeeded


class TestFetchTranscriptWithRetry:
    def test_retry_on_failure(self):
        """fetch_transcript_with_retry retries when fetch_transcript raises."""
        fetcher, MockApi = _make_fetcher()

        call_count = 0
        from src.models.transcript import Transcript, TranscriptSegment

        original_fetch = fetcher.fetch_transcript

        def mock_fetch(video_id):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return Transcript(
                available=True,
                language="en",
                segments=[TranscriptSegment(text="Success", start=0.0, duration=1.0)],
            )

        fetcher.fetch_transcript = mock_fetch

        with patch("time.sleep"):
            result = fetcher.fetch_transcript_with_retry("vid123", max_retries=3)
        assert result.available is True

    def test_exhausts_retries(self):
        fetcher, MockApi = _make_fetcher()

        def always_fail(video_id):
            raise Exception("Permanent error")

        fetcher.fetch_transcript = always_fail

        with patch("time.sleep"):
            result = fetcher.fetch_transcript_with_retry("vid123", max_retries=2)
        assert result.available is False
