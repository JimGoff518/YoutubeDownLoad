"""Tests for PodcastFetcher with mocked HTTP requests."""

import os
from unittest.mock import patch, MagicMock

import pytest


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Test Podcast</title>
    <description>A test podcast</description>
    <link>https://example.com</link>
    <language>en</language>
    <itunes:author>Test Author</itunes:author>
    <itunes:image href="https://example.com/art.jpg"/>
    <itunes:category text="Business"/>
    <itunes:category text="Education"/>
    <item>
      <title>Episode 1</title>
      <description>First episode</description>
      <guid>ep1-guid</guid>
      <pubDate>Mon, 15 Jan 2024 12:00:00 +0000</pubDate>
      <itunes:duration>01:23:45</itunes:duration>
      <enclosure url="https://example.com/ep1.mp3" type="audio/mpeg"/>
      <link>https://example.com/ep1</link>
    </item>
    <item>
      <title>Episode 2</title>
      <description>&lt;p&gt;HTML description&lt;/p&gt;</description>
      <guid>ep2-guid</guid>
      <pubDate>Mon, 22 Jan 2024 12:00:00 +0000</pubDate>
      <itunes:duration>45:30</itunes:duration>
      <enclosure url="https://example.com/ep2.mp3" type="audio/mpeg"/>
    </item>
  </channel>
</rss>
"""


def _make_fetcher():
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key"}):
        from importlib import reload
        import src.config
        reload(src.config)
    from src.api.podcast_fetcher import PodcastFetcher
    return PodcastFetcher("https://example.com/feed.xml")


class TestPodcastFetcher:
    def test_fetch_feed(self):
        fetcher = _make_fetcher()
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_RSS.encode("utf-8")
        mock_resp.raise_for_status = MagicMock()

        with patch("src.api.podcast_fetcher.requests.get", return_value=mock_resp):
            podcast, episodes = fetcher.fetch_feed()

        assert podcast.title == "Test Podcast"
        assert podcast.author == "Test Author"
        assert podcast.language == "en"
        assert "Business" in podcast.categories
        assert len(episodes) == 2

    def test_episode_parsing(self):
        fetcher = _make_fetcher()
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_RSS.encode("utf-8")
        mock_resp.raise_for_status = MagicMock()

        with patch("src.api.podcast_fetcher.requests.get", return_value=mock_resp):
            _, episodes = fetcher.fetch_feed()

        ep1 = episodes[0]
        assert ep1.guid == "ep1-guid"
        assert ep1.title == "Episode 1"
        assert ep1.duration_seconds == 5025  # 1:23:45
        assert ep1.audio_url == "https://example.com/ep1.mp3"
        assert ep1.published_at is not None
        assert ep1.published_at.year == 2024

    def test_html_stripped_from_description(self):
        fetcher = _make_fetcher()
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_RSS.encode("utf-8")
        mock_resp.raise_for_status = MagicMock()

        with patch("src.api.podcast_fetcher.requests.get", return_value=mock_resp):
            _, episodes = fetcher.fetch_feed()

        # Episode 2 has HTML in description
        assert "<p>" not in episodes[1].description

    def test_no_enclosure_skips_episode(self):
        rss = """<?xml version="1.0"?>
        <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
          <channel>
            <title>Test</title>
            <item>
              <title>No Audio</title>
              <guid>no-audio</guid>
            </item>
          </channel>
        </rss>"""
        fetcher = _make_fetcher()
        mock_resp = MagicMock()
        mock_resp.content = rss.encode("utf-8")
        mock_resp.raise_for_status = MagicMock()

        with patch("src.api.podcast_fetcher.requests.get", return_value=mock_resp):
            _, episodes = fetcher.fetch_feed()
        assert len(episodes) == 0

    def test_invalid_rss_raises(self):
        fetcher = _make_fetcher()
        mock_resp = MagicMock()
        mock_resp.content = b"<rss><not-channel/></rss>"
        mock_resp.raise_for_status = MagicMock()

        with patch("src.api.podcast_fetcher.requests.get", return_value=mock_resp):
            with pytest.raises(ValueError, match="no channel"):
                fetcher.fetch_feed()
