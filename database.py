"""Database for storing conversation history.
Uses PostgreSQL when DATABASE_URL is set (Railway), otherwise falls back to SQLite."""

import os
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Check if we have a PostgreSQL URL (Railway sets this)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    logger.info("Using PostgreSQL database")
else:
    import sqlite3
    logger.info("Using SQLite database (local)")

# SQLite database file location (only used locally)
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./conversations.db"))


def get_connection():
    """Get a database connection."""
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def _placeholder():
    """Return the correct placeholder for the current database."""
    return "%s" if DATABASE_URL else "?"


def init_database():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        # PostgreSQL syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
    else:
        # SQLite syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)

    conn.commit()
    conn.close()


def _row_to_dict(cursor, row):
    """Convert a row to a dict, works for both PostgreSQL and SQLite."""
    if DATABASE_URL:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    else:
        return dict(row)


def create_conversation(title: str = "New Conversation") -> int:
    """Create a new conversation and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    p = _placeholder()

    if DATABASE_URL:
        cursor.execute(
            f"INSERT INTO conversations (title) VALUES ({p}) RETURNING id",
            (title,)
        )
        conversation_id = cursor.fetchone()[0]
    else:
        cursor.execute(
            f"INSERT INTO conversations (title) VALUES ({p})",
            (title,)
        )
        conversation_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return conversation_id


def update_conversation_title(conversation_id: int, title: str):
    """Update the title of a conversation."""
    conn = get_connection()
    cursor = conn.cursor()
    p = _placeholder()

    cursor.execute(
        f"UPDATE conversations SET title = {p}, updated_at = {p} WHERE id = {p}",
        (title, datetime.now(), conversation_id)
    )

    conn.commit()
    conn.close()


def add_message(conversation_id: int, role: str, content: str):
    """Add a message to a conversation."""
    conn = get_connection()
    cursor = conn.cursor()
    p = _placeholder()

    cursor.execute(
        f"INSERT INTO messages (conversation_id, role, content) VALUES ({p}, {p}, {p})",
        (conversation_id, role, content)
    )

    cursor.execute(
        f"UPDATE conversations SET updated_at = {p} WHERE id = {p}",
        (datetime.now(), conversation_id)
    )

    conn.commit()
    conn.close()


def get_conversation_messages(conversation_id: int) -> list[dict]:
    """Get all messages for a conversation."""
    conn = get_connection()
    cursor = conn.cursor()
    p = _placeholder()

    cursor.execute(
        f"SELECT role, content, timestamp FROM messages WHERE conversation_id = {p} ORDER BY timestamp",
        (conversation_id,)
    )

    rows = cursor.fetchall()
    messages = [_row_to_dict(cursor, row) for row in rows]

    conn.close()
    return messages


def get_all_conversations() -> list[dict]:
    """Get all conversations, newest first."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id, c.title, c.created_at, c.updated_at,
               COUNT(m.id) as message_count
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        GROUP BY c.id, c.title, c.created_at, c.updated_at
        ORDER BY c.updated_at DESC
    """)

    rows = cursor.fetchall()
    conversations = [_row_to_dict(cursor, row) for row in rows]

    conn.close()
    return conversations


def delete_conversation(conversation_id: int):
    """Delete a conversation and all its messages."""
    conn = get_connection()
    cursor = conn.cursor()
    p = _placeholder()

    cursor.execute(f"DELETE FROM messages WHERE conversation_id = {p}", (conversation_id,))
    cursor.execute(f"DELETE FROM conversations WHERE id = {p}", (conversation_id,))

    conn.commit()
    conn.close()


def get_conversation(conversation_id: int) -> Optional[dict]:
    """Get a single conversation by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    p = _placeholder()

    cursor.execute(
        f"SELECT id, title, created_at, updated_at FROM conversations WHERE id = {p}",
        (conversation_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_dict(cursor, row)
    return None


def generate_title_from_message(message: str) -> str:
    """Generate a short title from the first message."""
    title = message.strip()[:50]
    if len(message) > 50:
        title += "..."
    return title


# Initialize database when this module is imported
init_database()
