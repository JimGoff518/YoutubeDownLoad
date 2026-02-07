"""Tests for src/processors/video_processor.py with mocked dependencies."""

import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest


def _make_processor():
    """Create a VideoProcessor with mocked YouTubeClient and TranscriptFetcher."""
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key"}):
        from importlib import reload
        import src.config
        reload(src.config)

    from src.processors.video_processor import VideoProcessor
    from src.models.transcript import Transcript, TranscriptSegment

    mock_yt = MagicMock()
    mock_tf = MagicMock()
    processor = VideoProcessor(youtube_client=mock_yt, transcript_fetcher=mock_tf)
    return processor, mock_yt, mock_tf


class TestCalculateMLFeatures:
    def test_basic_calculation(self, sample_video_data):
        processor, _, _ = _make_processor()
        ml = processor.calculate_ml_features(sample_video_data, transcript_word_count=500)

        assert ml.total_engagement == 550  # 500 likes + 50 comments
        assert ml.engagement_rate == round(550 / 10000, 6)
        assert ml.transcript_token_count > 0
        assert ml.views_per_day > 0

    def test_zero_views(self, sample_video_data):
        processor, _, _ = _make_processor()
        sample_video_data["view_count"] = 0
        ml = processor.calculate_ml_features(sample_video_data, transcript_word_count=0)
        # Should not divide by zero (uses max(1, view_count))
        assert ml.engagement_rate == 550.0  # 550 / 1

    def test_zero_transcript(self, sample_video_data):
        processor, _, _ = _make_processor()
        ml = processor.calculate_ml_features(sample_video_data, transcript_word_count=0)
        assert ml.transcript_token_count == 0


class TestProcessVideo:
    def test_success(self, sample_video_data):
        processor, _, mock_tf = _make_processor()
        from src.models.transcript import Transcript, TranscriptSegment

        mock_tf.fetch_transcript.return_value = Transcript(
            available=True,
            language="en",
            segments=[TranscriptSegment(text="Hello world", start=0.0, duration=2.0)],
        )

        video = processor.process_video(sample_video_data)
        assert video.id == "dQw4w9WgXcQ"
        assert video.transcript.available is True
        assert video.ml_features.total_engagement == 550

    def test_no_transcript(self, sample_video_data):
        processor, _, mock_tf = _make_processor()
        from src.models.transcript import Transcript

        mock_tf.fetch_transcript.return_value = Transcript(available=False)

        video = processor.process_video(sample_video_data)
        assert video.transcript.available is False
        assert video.ml_features.transcript_token_count == 0


class TestProcessChannel:
    def test_success(self, sample_channel_data, sample_video_data):
        processor, mock_yt, mock_tf = _make_processor()
        from src.models.transcript import Transcript

        vid_id = sample_video_data["id"]  # "dQw4w9WgXcQ"
        mock_yt.get_channel_info.return_value = sample_channel_data
        mock_yt.get_channel_videos.return_value = [vid_id]
        mock_yt.get_video_details_batch.return_value = [sample_video_data]
        mock_tf.fetch_transcript.return_value = Transcript(available=False)

        result = processor.process_channel("UCtest")
        assert result.channel.title == "Test Channel"
        assert len(result.videos) == 1
        assert result.extraction_metadata.total_videos_processed == 1

    def test_empty_channel(self, sample_channel_data):
        processor, mock_yt, _ = _make_processor()
        mock_yt.get_channel_info.return_value = sample_channel_data
        mock_yt.get_channel_videos.return_value = []

        result = processor.process_channel("UCtest")
        assert len(result.videos) == 0
        assert result.extraction_metadata.total_videos_processed == 0

    def test_error_handling(self, sample_channel_data, sample_video_data):
        processor, mock_yt, mock_tf = _make_processor()

        vid_id = sample_video_data["id"]
        mock_yt.get_channel_info.return_value = sample_channel_data
        mock_yt.get_channel_videos.return_value = [vid_id, "missing_vid"]
        mock_yt.get_video_details_batch.return_value = [sample_video_data]
        # vid_id has metadata, "missing_vid" does not (private/deleted)

        from src.models.transcript import Transcript
        mock_tf.fetch_transcript.return_value = Transcript(available=False)

        result = processor.process_channel("UCtest")
        # vid_id processed, missing_vid should be in errors (no metadata)
        assert len(result.videos) == 1
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "VideoNotFound"
