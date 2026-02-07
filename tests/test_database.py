"""Tests for database.py using in-memory SQLite."""

import os
import sqlite3
from unittest.mock import patch

import pytest


# We need to patch DATABASE_URL to None and DATABASE_PATH before importing
@pytest.fixture(autouse=True)
def _patch_db(tmp_path):
    """Force SQLite mode with a temp file for each test."""
    db_path = tmp_path / "test.db"
    with patch.dict(os.environ, {"DATABASE_PATH": str(db_path)}, clear=False):
        with patch("database.DATABASE_URL", None):
            with patch("database.DATABASE_PATH", db_path):
                import database
                database.init_database()
                yield database


class TestDatabase:
    def test_create_conversation(self, _patch_db):
        db = _patch_db
        cid = db.create_conversation("Test Conv")
        assert isinstance(cid, int)
        assert cid > 0

    def test_get_conversation(self, _patch_db):
        db = _patch_db
        cid = db.create_conversation("My Conv")
        conv = db.get_conversation(cid)
        assert conv is not None
        assert conv["title"] == "My Conv"

    def test_get_conversation_not_found(self, _patch_db):
        db = _patch_db
        assert db.get_conversation(99999) is None

    def test_add_and_get_messages(self, _patch_db):
        db = _patch_db
        cid = db.create_conversation("Chat")
        db.add_message(cid, "user", "Hello")
        db.add_message(cid, "assistant", "Hi there")

        msgs = db.get_conversation_messages(cid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert msgs[1]["role"] == "assistant"

    def test_update_title(self, _patch_db):
        db = _patch_db
        cid = db.create_conversation("Old Title")
        db.update_conversation_title(cid, "New Title")
        conv = db.get_conversation(cid)
        assert conv["title"] == "New Title"

    def test_delete_conversation(self, _patch_db):
        db = _patch_db
        cid = db.create_conversation("To Delete")
        db.add_message(cid, "user", "msg")
        db.delete_conversation(cid)
        assert db.get_conversation(cid) is None
        assert db.get_conversation_messages(cid) == []

    def test_get_all_conversations_ordering(self, _patch_db):
        import time
        db = _patch_db
        cid1 = db.create_conversation("First")
        time.sleep(1.1)  # SQLite CURRENT_TIMESTAMP has 1s resolution
        cid2 = db.create_conversation("Second")

        convs = db.get_all_conversations()
        assert len(convs) == 2
        # Second is newer, should be first (ORDER BY updated_at DESC)
        assert convs[0]["id"] == cid2

    def test_get_all_conversations_message_count(self, _patch_db):
        db = _patch_db
        cid = db.create_conversation("Counted")
        db.add_message(cid, "user", "1")
        db.add_message(cid, "assistant", "2")
        db.add_message(cid, "user", "3")

        convs = db.get_all_conversations()
        assert convs[0]["message_count"] == 3

    def test_generate_title_from_message(self, _patch_db):
        db = _patch_db
        short = db.generate_title_from_message("Hello world")
        assert short == "Hello world"

        long_msg = "A" * 100
        title = db.generate_title_from_message(long_msg)
        assert len(title) == 53  # 50 + "..."
        assert title.endswith("...")
