import sqlite3
from contextlib import contextmanager

from app.config import settings


@contextmanager
def get_connection():
    """Context manager for SQLite database connections."""
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
