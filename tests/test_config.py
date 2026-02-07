"""Tests for src/config.py."""

import os
from unittest.mock import patch

import pytest


class TestConfigParsing:
    """Test the Config class helper methods and init logic."""

    def _make_config(self, env_overrides=None):
        """Create a Config instance with mocked environment."""
        base = {
            "YOUTUBE_API_KEY": "test-key-123",
        }
        if env_overrides:
            base.update(env_overrides)

        with patch.dict(os.environ, base, clear=False):
            # Re-import to bypass module-level singleton
            from importlib import reload
            import src.config as cfg_mod
            reload(cfg_mod)
            return cfg_mod.Config()

    def test_default_values(self):
        c = self._make_config({"ENABLE_AUDIO_FALLBACK": "false"})
        assert c.youtube_api_key == "test-key-123"
        assert c.max_concurrent_videos == 5
        assert c.preferred_languages == ["en", "en-US", "en-GB"]
        assert c.fallback_to_auto_generated is True
        assert c.retry_attempts == 3
        assert c.enable_audio_fallback is False

    def test_missing_api_key_raises(self):
        # The module-level `config = Config()` fires during reload,
        # so the ValueError is raised at import/reload time.
        with patch("dotenv.load_dotenv"):
            with patch.dict(os.environ, {}, clear=True):
                from importlib import reload
                import src.config as cfg_mod
                with pytest.raises(ValueError, match="YOUTUBE_API_KEY"):
                    reload(cfg_mod)

    def test_custom_languages(self):
        c = self._make_config({"PREFERRED_LANGUAGES": "es,fr"})
        assert c.preferred_languages == ["es", "fr"]

    def test_parse_bool_variants(self):
        c = self._make_config()
        assert c._parse_bool("true") is True
        assert c._parse_bool("1") is True
        assert c._parse_bool("yes") is True
        assert c._parse_bool("on") is True
        assert c._parse_bool("false") is False
        assert c._parse_bool("0") is False
        assert c._parse_bool("no") is False

    def test_parse_languages_strips_whitespace(self):
        c = self._make_config()
        assert c._parse_languages("  en , es , fr  ") == ["en", "es", "fr"]

    def test_validate_max_concurrent(self):
        c = self._make_config({"MAX_CONCURRENT_VIDEOS": "0"})
        with pytest.raises(ValueError, match="MAX_CONCURRENT_VIDEOS"):
            c.validate()

    def test_validate_empty_languages(self):
        c = self._make_config()
        c.preferred_languages = []
        with pytest.raises(ValueError, match="language"):
            c.validate()
