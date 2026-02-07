"""Shared fixtures for all tests."""

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Sample data factories ──────────────────────────────────────────


@pytest.fixture
def sample_segments():
    """Raw segment dicts for building Transcript objects."""
    return [
        {"text": "Hello world.", "start": 0.0, "duration": 2.5},
        {"text": "This is a test.", "start": 2.5, "duration": 3.0},
        {"text": "Goodbye.", "start": 5.5, "duration": 1.5},
    ]


@pytest.fixture
def sample_video_data():
    """Minimal video metadata dict (as returned by YouTubeClient)."""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Test Video Title",
        "description": "A test video description for unit testing.",
        "published_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        "duration_seconds": 212,
        "duration_iso": "PT3M32S",
        "view_count": 10000,
        "like_count": 500,
        "comment_count": 50,
        "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        "tags": ["test", "video"],
        "category_id": "22",
        "category_name": "People & Blogs",
        "default_language": "en",
        "default_audio_language": "en",
        "license": "youtube",
        "privacy_status": "public",
        "made_for_kids": False,
    }


@pytest.fixture
def sample_channel_data():
    """Minimal channel metadata dict."""
    return {
        "id": "UCxxxxxxxxxxxxxxxxxxxxxxxx",
        "title": "Test Channel",
        "description": "A test channel.",
        "custom_url": "@testchannel",
        "published_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
        "subscriber_count": 1000,
        "video_count": 50,
        "view_count": 100000,
        "thumbnail_url": "https://example.com/thumb.jpg",
        "country": "US",
        "topics": [],
    }
