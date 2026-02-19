"""SQLite connection helper."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "draft.db"


def get_connection() -> sqlite3.Connection:
    """Return a connection to the draft database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def db_exists() -> bool:
    """Check if the database file exists."""
    return DB_PATH.exists()
