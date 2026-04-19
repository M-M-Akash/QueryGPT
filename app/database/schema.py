import sqlite3
from typing import Any

from app.database.connection import get_connection


def get_database_schema() -> dict[str, Any]:
    """Extract schema information from the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        schema_info: dict[str, Any] = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            column_info = []
            for col in columns:
                column_info.append({
                    "name": col[1],
                    "type": col[2],
                    "primary_key": bool(col[5]),
                })

            schema_info[table_name] = {
                "columns": column_info,
                "description": f"Table containing {table_name} information",
            }

    return schema_info
