"""Tests for Pydantic data models (transcript, video, podcast)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models.transcript import Transcript, TranscriptSegment
from src.models.video import (
    Video,
    Channel,
    ExtractionMetadata,
    ExtractionResult,
    ErrorEntry,
    MLFeatures,
)
from src.models.podcast import (
    Episode,
    Podcast,
    PodcastExtractionMetadata,
    PodcastErrorEntry,
    PodcastExtractionResult,
)


# ── TranscriptSegment ──────────────────────────────────────────────


class TestTranscriptSegment:
    def test_basic_creation(self):
        seg = TranscriptSegment(text="Hello", start=0.0, duration=2.5)
        assert seg.text == "Hello"
        assert seg.start == 0.0
        assert seg.duration == 2.5

    def test_end_computed(self):
        seg = TranscriptSegment(text="Hi", start=1.0, duration=3.0)
        assert seg.end == 4.0

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            TranscriptSegment(text="Hi", start=0.0)  # missing duration


# ── Transcript ─────────────────────────────────────────────────────


class TestTranscript:
    def test_available_false(self):
        t = Transcript(available=False)
        assert t.segments == []
        assert t.full_text == ""
        assert t.word_count == 0
        assert t.character_count == 0

    def test_full_text_join(self, sample_segments):
        segs = [TranscriptSegment(**s) for s in sample_segments]
        t = Transcript(available=True, language="en", segments=segs)
        assert t.full_text == "Hello world. This is a test. Goodbye."
        assert t.word_count == 7
        assert t.character_count == len(t.full_text)

    def test_empty_segments(self):
        t = Transcript(available=True, segments=[])
        assert t.full_text == ""
        assert t.word_count == 0

    def test_serialization_roundtrip(self, sample_segments):
        segs = [TranscriptSegment(**s) for s in sample_segments]
        t = Transcript(available=True, language="en", segments=segs)
        data = t.model_dump(mode="json")
        t2 = Transcript(**data)
        assert t2.full_text == t.full_text
        assert t2.word_count == t.word_count


# ── MLFeatures ─────────────────────────────────────────────────────


class TestMLFeatures:
    def test_creation(self):
        ml = MLFeatures(
            title_token_count=5,
            description_token_count=20,
            transcript_token_count=100,
            total_engagement=550,
            engagement_rate=0.055,
            views_per_day=25.0,
        )
        assert ml.total_engagement == 550
        assert ml.engagement_rate == 0.055


# ── Video ──────────────────────────────────────────────────────────


class TestVideo:
    def test_creation(self, sample_video_data):
        transcript = Transcript(available=False)
        ml = MLFeatures(
            title_token_count=4,
            description_token_count=8,
            transcript_token_count=0,
            total_engagement=550,
            engagement_rate=0.055,
            views_per_day=25.0,
        )
        v = Video(**sample_video_data, transcript=transcript, ml_features=ml)
        assert v.id == "dQw4w9WgXcQ"
        assert v.title == "Test Video Title"
        assert v.view_count == 10000

    def test_defaults(self, sample_video_data):
        transcript = Transcript(available=False)
        ml = MLFeatures(
            title_token_count=1,
            description_token_count=1,
            total_engagement=0,
            engagement_rate=0.0,
            views_per_day=0.0,
        )
        v = Video(**sample_video_data, transcript=transcript, ml_features=ml)
        assert v.tags == ["test", "video"]
        assert v.made_for_kids is False


# ── Channel ────────────────────────────────────────────────────────


class TestChannel:
    def test_creation(self, sample_channel_data):
        c = Channel(**sample_channel_data)
        assert c.title == "Test Channel"
        assert c.subscriber_count == 1000

    def test_defaults(self):
        c = Channel(
            id="UCtest",
            title="T",
            description="",
            published_at=datetime.now(timezone.utc),
            thumbnail_url="https://example.com/t.jpg",
        )
        assert c.subscriber_count == 0
        assert c.topics == []


# ── ExtractionMetadata & ExtractionResult ──────────────────────────


class TestExtractionResult:
    def test_metadata(self):
        meta = ExtractionMetadata(
            channel_id="UCtest",
            total_videos_processed=10,
            successful_extractions=8,
            failed_extractions=2,
        )
        assert meta.extractor_version == "1.0.0"

    def test_error_entry(self):
        e = ErrorEntry(
            video_id="abc",
            error_type="TranscriptNotAvailable",
            error_message="No transcript",
        )
        assert e.video_title is None


# ── Podcast models ─────────────────────────────────────────────────


class TestPodcastModels:
    def test_episode_word_count_no_transcript(self):
        ep = Episode(
            guid="ep1",
            title="Episode 1",
            audio_url="https://example.com/ep1.mp3",
        )
        assert ep.word_count == 0
        assert ep.transcript.available is False

    def test_episode_word_count_with_transcript(self, sample_segments):
        segs = [TranscriptSegment(**s) for s in sample_segments]
        transcript = Transcript(available=True, language="en", segments=segs)
        ep = Episode(
            guid="ep1",
            title="Episode 1",
            audio_url="https://example.com/ep1.mp3",
            transcript=transcript,
        )
        assert ep.word_count == 7

    def test_podcast_creation(self):
        p = Podcast(
            title="Test Podcast",
            feed_url="https://example.com/feed.xml",
        )
        assert p.categories == []
        assert p.author is None

    def test_podcast_extraction_metadata(self):
        meta = PodcastExtractionMetadata(
            feed_url="https://example.com/feed.xml",
        )
        assert meta.total_episodes_processed == 0

    def test_podcast_error_entry(self):
        e = PodcastErrorEntry(
            episode_guid="ep1",
            error_type="DownloadFailed",
            error_message="Connection timeout",
        )
        assert e.episode_title is None

    def test_podcast_extraction_result(self):
        result = PodcastExtractionResult(
            extraction_metadata=PodcastExtractionMetadata(
                feed_url="https://example.com/feed.xml",
            ),
            podcast=Podcast(
                title="Test",
                feed_url="https://example.com/feed.xml",
            ),
        )
        assert result.episodes == []
        assert result.errors == []
