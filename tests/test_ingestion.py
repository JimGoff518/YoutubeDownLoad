"""Tests for ingest_to_pinecone.py pipeline with mocked APIs."""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest


def _import_module():
    """Import ingest_to_pinecone with mocked API clients."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "PINECONE_API_KEY": "test",
    }):
        mock_openai = MagicMock()
        mock_pc = MagicMock()
        mock_index = MagicMock()
        mock_pc.return_value.Index.return_value = mock_index

        with patch("openai.OpenAI", mock_openai):
            with patch("pinecone.Pinecone", mock_pc):
                if "ingest_to_pinecone" in sys.modules:
                    del sys.modules["ingest_to_pinecone"]
                import ingest_to_pinecone
                return ingest_to_pinecone, mock_openai, mock_index


class TestProcessTranscriptFile:
    def test_video_format(self, tmp_path):
        mod, _, _ = _import_module()

        data = {
            "videos": [{
                "title": "Test Video",
                "transcript": {
                    "available": True,
                    "full_text": "A" * 500,  # Short text
                }
            }]
        }
        f = tmp_path / "test_source.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert len(chunks) > 0
        assert chunks[0]["metadata"]["source"] == "test_source"
        assert chunks[0]["metadata"]["episode_title"] == "Test Video"

    def test_podcast_format(self, tmp_path):
        mod, _, _ = _import_module()

        data = {
            "episodes": [{
                "title": "Episode 1",
                "transcript": {
                    "available": True,
                    "full_text": "B" * 500,
                }
            }]
        }
        f = tmp_path / "podcast_source.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert len(chunks) > 0
        assert chunks[0]["metadata"]["episode_title"] == "Episode 1"

    def test_skips_unavailable_transcript(self, tmp_path):
        mod, _, _ = _import_module()

        data = {
            "videos": [{
                "title": "No Transcript",
                "transcript": {"available": False}
            }]
        }
        f = tmp_path / "skip.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert len(chunks) == 0

    def test_skips_short_text(self, tmp_path):
        mod, _, _ = _import_module()

        data = {
            "videos": [{
                "title": "Short",
                "transcript": {
                    "available": True,
                    "full_text": "Too short",  # < 100 chars
                }
            }]
        }
        f = tmp_path / "short.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert len(chunks) == 0

    def test_builds_text_from_segments(self, tmp_path):
        mod, _, _ = _import_module()

        data = {
            "videos": [{
                "title": "From Segments",
                "transcript": {
                    "available": True,
                    "segments": [{"text": "Word " * 30}]  # > 100 chars
                }
            }]
        }
        f = tmp_path / "segments.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert len(chunks) > 0

    def test_unknown_structure_skips(self, tmp_path):
        mod, _, _ = _import_module()

        data = {"other_key": []}
        f = tmp_path / "unknown.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert len(chunks) == 0

    def test_enriched_text_includes_source(self, tmp_path):
        mod, _, _ = _import_module()

        data = {
            "videos": [{
                "title": "Enriched",
                "transcript": {
                    "available": True,
                    "full_text": "Content " * 50,
                }
            }]
        }
        f = tmp_path / "enriched_source.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        chunks = list(mod.process_transcript_file(f))
        assert "[Source: enriched_source]" in chunks[0]["text"]
        assert "[Episode: Enriched]" in chunks[0]["text"]
