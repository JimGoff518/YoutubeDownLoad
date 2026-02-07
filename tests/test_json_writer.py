"""Tests for src/storage/json_writer.py."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.transcript import Transcript
from src.models.video import (
    Video,
    Channel,
    ExtractionMetadata,
    ExtractionResult,
    MLFeatures,
)
from src.storage.json_writer import JSONWriter


def _make_result(n_videos=0):
    """Build a minimal ExtractionResult."""
    channel = Channel(
        id="UCtest",
        title="Test Channel",
        description="desc",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        thumbnail_url="https://example.com/t.jpg",
    )
    meta = ExtractionMetadata(
        channel_id="UCtest",
        total_videos_processed=n_videos,
        successful_extractions=n_videos,
        failed_extractions=0,
    )
    videos = []
    for i in range(n_videos):
        videos.append(
            Video(
                id=f"vid{i}",
                title=f"Video {i}",
                description="desc",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                duration_seconds=100,
                duration_iso="PT1M40S",
                thumbnail_url="https://example.com/v.jpg",
                category_id="22",
                transcript=Transcript(available=False),
                ml_features=MLFeatures(
                    title_token_count=3,
                    description_token_count=1,
                    total_engagement=0,
                    engagement_rate=0.0,
                    views_per_day=0.0,
                ),
            )
        )
    return ExtractionResult(
        extraction_metadata=meta, channel=channel, videos=videos
    )


class TestJSONWriter:
    def test_write_and_validate(self, tmp_path):
        result = _make_result(2)
        out = tmp_path / "test_output.json"
        JSONWriter.write_output(result, out)

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["channel"]["title"] == "Test Channel"
        assert len(data["videos"]) == 2

        assert JSONWriter.validate_output(out) is True

    def test_write_compact(self, tmp_path):
        result = _make_result(0)
        out = tmp_path / "compact.json"
        JSONWriter.write_output(result, out, pretty=False)
        text = out.read_text(encoding="utf-8")
        assert "\n" not in text.strip()

    def test_write_creates_directories(self, tmp_path):
        result = _make_result(0)
        out = tmp_path / "sub" / "dir" / "out.json"
        JSONWriter.write_output(result, out)
        assert out.exists()

    def test_validate_missing_file(self, tmp_path):
        assert JSONWriter.validate_output(tmp_path / "nope.json") is False

    def test_validate_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        assert JSONWriter.validate_output(bad) is False

    def test_get_summary(self):
        result = _make_result(1)
        summary = JSONWriter.get_summary(result)
        assert "Test Channel" in summary
        assert "Extraction Summary" in summary
