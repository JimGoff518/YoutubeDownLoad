"""Tests for src/api/youtube_client.py with mocked Google API."""

import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest


def _make_client():
    """Create a YouTubeClient with a mocked Google API build."""
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key"}):
        from importlib import reload
        import src.config
        reload(src.config)

    with patch("src.api.youtube_client.build") as mock_build:
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        from src.api.youtube_client import YouTubeClient
        client = YouTubeClient(api_key="test-key")
        return client, mock_youtube


class TestGetChannelInfo:
    def test_success(self):
        client, mock_yt = _make_client()
        mock_yt.channels().list().execute.return_value = {
            "items": [{
                "id": "UCtest123456789012345678",
                "snippet": {
                    "title": "Test Channel",
                    "description": "A channel",
                    "customUrl": "@test",
                    "publishedAt": "2020-01-01T00:00:00Z",
                    "thumbnails": {"high": {"url": "https://example.com/t.jpg"}},
                    "country": "US",
                },
                "statistics": {
                    "subscriberCount": "1000",
                    "videoCount": "50",
                    "viewCount": "100000",
                },
                "topicDetails": {"topicCategories": ["Education"]},
            }]
        }

        info = client.get_channel_info("UCtest123456789012345678")
        assert info["title"] == "Test Channel"
        assert info["subscriber_count"] == 1000

    def test_not_found(self):
        client, mock_yt = _make_client()
        mock_yt.channels().list().execute.return_value = {"items": []}

        with pytest.raises(ValueError, match="Channel not found"):
            client.get_channel_info("UCnotfound")

    def test_http_404(self):
        client, mock_yt = _make_client()
        from googleapiclient.errors import HttpError
        resp = MagicMock()
        resp.status = 404
        mock_yt.channels().list().execute.side_effect = HttpError(resp, b"not found")

        with pytest.raises(ValueError, match="Channel not found"):
            client.get_channel_info("UCnotfound")

    def test_http_403(self):
        client, mock_yt = _make_client()
        from googleapiclient.errors import HttpError
        resp = MagicMock()
        resp.status = 403
        mock_yt.channels().list().execute.side_effect = HttpError(resp, b"quota")

        with pytest.raises(ValueError, match="quota"):
            client.get_channel_info("UCtest")


class TestGetVideoDetails:
    def test_success(self):
        client, mock_yt = _make_client()
        mock_yt.videos().list().execute.return_value = {
            "items": [{
                "id": "vid123",
                "snippet": {
                    "title": "Test Video",
                    "description": "desc",
                    "publishedAt": "2024-01-15T12:00:00Z",
                    "thumbnails": {"high": {"url": "https://example.com/v.jpg"}},
                    "tags": ["test"],
                    "categoryId": "22",
                },
                "contentDetails": {
                    "duration": "PT3M32S",
                    "license": "youtube",
                },
                "statistics": {
                    "viewCount": "10000",
                    "likeCount": "500",
                    "commentCount": "50",
                },
                "status": {"privacyStatus": "public", "madeForKids": False},
            }]
        }

        videos = client.get_video_details(["vid123"])
        assert len(videos) == 1
        assert videos[0]["title"] == "Test Video"
        assert videos[0]["duration_seconds"] == 212

    def test_too_many_ids(self):
        client, _ = _make_client()
        with pytest.raises(ValueError, match="Maximum 50"):
            client.get_video_details(["x"] * 51)

    def test_empty_list(self):
        client, _ = _make_client()
        assert client.get_video_details([]) == []

    def test_skips_live_streams(self):
        """Videos without duration (live streams) should be skipped."""
        client, mock_yt = _make_client()
        mock_yt.videos().list().execute.return_value = {
            "items": [{
                "id": "live1",
                "snippet": {
                    "title": "Live Stream",
                    "description": "",
                    "publishedAt": "2024-01-15T12:00:00Z",
                    "thumbnails": {"high": {"url": "https://example.com/v.jpg"}},
                    "categoryId": "22",
                },
                "contentDetails": {},  # No duration
                "statistics": {},
            }]
        }

        videos = client.get_video_details(["live1"])
        assert len(videos) == 0


class TestGetVideoDetailsBatch:
    def test_batching(self):
        client, mock_yt = _make_client()
        mock_yt.videos().list().execute.return_value = {"items": []}

        with patch("time.sleep"):
            client.get_video_details_batch(["v"] * 75, batch_size=50)

        # Should have been called twice (50 + 25)
        assert mock_yt.videos().list.call_count >= 2
