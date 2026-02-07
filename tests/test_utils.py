"""Tests for pure utility functions (chunking, parsing, hashing)."""

import hashlib
from datetime import datetime

import pytest

# ── chunk_text (ingest_to_pinecone) ─────────────────────────────────
# We import just the function to avoid module-level API client init.

import importlib
import sys
from unittest.mock import MagicMock, patch


def _import_chunk_utils():
    """Import chunk_text and generate_chunk_id without triggering API clients."""
    # Mock the heavy imports at module level
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "test",
        "PINECONE_API_KEY": "test",
    }):
        with patch("openai.OpenAI"):
            with patch("pinecone.Pinecone") as mock_pc:
                mock_pc.return_value.Index.return_value = MagicMock()
                if "ingest_to_pinecone" in sys.modules:
                    del sys.modules["ingest_to_pinecone"]
                import ingest_to_pinecone
                return ingest_to_pinecone.chunk_text, ingest_to_pinecone.generate_chunk_id


class TestChunkText:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.chunk_text, self.generate_chunk_id = _import_chunk_utils()

    def test_short_text_single_chunk(self):
        chunks = self.chunk_text("Hello world.", chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world."
        assert chunks[0]["chunk_index"] == 0

    def test_multiple_chunks(self):
        text = "Word " * 1000  # ~5000 chars
        chunks = self.chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        # Chunks should have sequential indices
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_overlap_exists(self):
        text = "Sentence one. Sentence two. Sentence three. Sentence four. " * 20
        chunks = self.chunk_text(text, chunk_size=50, overlap=10)
        if len(chunks) >= 2:
            # Second chunk should start before first chunk ends (overlap)
            assert chunks[1]["char_start"] < chunks[0]["char_end"]

    def test_empty_text(self):
        chunks = self.chunk_text("", chunk_size=100, overlap=10)
        assert chunks == []

    def test_whitespace_only(self):
        chunks = self.chunk_text("   ", chunk_size=100, overlap=10)
        assert chunks == []


class TestGenerateChunkId:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _, self.generate_chunk_id = _import_chunk_utils()

    def test_deterministic(self):
        id1 = self.generate_chunk_id("source", "title", 0)
        id2 = self.generate_chunk_id("source", "title", 0)
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = self.generate_chunk_id("source", "title", 0)
        id2 = self.generate_chunk_id("source", "title", 1)
        assert id1 != id2

    def test_is_md5_hex(self):
        cid = self.generate_chunk_id("s", "t", 0)
        assert len(cid) == 32
        int(cid, 16)  # Should not raise


# ── parse_duration (podcast_fetcher) ────────────────────────────────

# Need to mock config import to avoid YOUTUBE_API_KEY requirement
import os


def _import_podcast_utils():
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test"}):
        from importlib import reload
        import src.config
        reload(src.config)
        from src.api.podcast_fetcher import parse_duration, parse_pub_date
        return parse_duration, parse_pub_date


class TestParseDuration:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.parse_duration, _ = _import_podcast_utils()

    def test_hhmmss(self):
        assert self.parse_duration("01:23:45") == 5025

    def test_mmss(self):
        assert self.parse_duration("23:45") == 1425

    def test_seconds_only(self):
        assert self.parse_duration("3600") == 3600

    def test_empty(self):
        assert self.parse_duration("") is None

    def test_none(self):
        assert self.parse_duration(None) is None

    def test_invalid(self):
        assert self.parse_duration("not-a-duration") is None


class TestParsePubDate:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _, self.parse_pub_date = _import_podcast_utils()

    def test_rfc2822(self):
        result = self.parse_pub_date("Mon, 15 Jan 2024 12:00:00 +0000")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_format(self):
        result = self.parse_pub_date("2024-01-15")
        assert result is not None
        assert result.year == 2024

    def test_empty(self):
        assert self.parse_pub_date("") is None

    def test_none(self):
        assert self.parse_pub_date(None) is None

    def test_invalid(self):
        assert self.parse_pub_date("not-a-date") is None


# ── YouTube URL extraction (static methods) ─────────────────────────


def _import_youtube_client():
    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test"}):
        from importlib import reload
        import src.config
        reload(src.config)
        from src.api.youtube_client import YouTubeClient
        return YouTubeClient


class TestExtractChannelId:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.YT = _import_youtube_client()

    def test_raw_channel_id(self):
        cid = "UCxxxxxxxxxxxxxxxxxxxxxx"  # exactly 24 chars starting with UC
        assert self.YT.extract_channel_id(cid) == cid

    def test_channel_url(self):
        url = "https://youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
        assert self.YT.extract_channel_id(url) == "UCxxxxxxxxxxxxxxxxxxxxxx"

    def test_at_username_raises(self):
        with pytest.raises(ValueError, match="@username"):
            self.YT.extract_channel_id("https://youtube.com/@testchannel")

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid channel input"):
            self.YT.extract_channel_id("not-a-channel")


class TestExtractVideoId:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.YT = _import_youtube_client()

    def test_raw_video_id(self):
        assert self.YT.extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_watch_url(self):
        assert self.YT.extract_video_id(
            "https://youtube.com/watch?v=dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert self.YT.extract_video_id(
            "https://youtu.be/dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert self.YT.extract_video_id(
            "https://youtube.com/embed/dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid video input"):
            self.YT.extract_video_id("not_a_valid_video_id_too_long")


class TestExtractPlaylistId:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.YT = _import_youtube_client()

    def test_raw_playlist_id(self):
        pid = "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        assert self.YT.extract_playlist_id(pid) == pid

    def test_playlist_url(self):
        url = "https://youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        assert self.YT.extract_playlist_id(url) == "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid playlist input"):
            self.YT.extract_playlist_id("not-a-playlist")
