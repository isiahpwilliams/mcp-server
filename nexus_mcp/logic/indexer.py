from __future__ import annotations

import sqlite3

from nexus_mcp.config import SETTINGS
from nexus_mcp.models import Symbol


def search_symbols(query: str) -> list[Symbol]:
    """
    Search indexed symbols by name, docstring, or file path.
    """
    db_path = SETTINGS.index_path
    search_term = f"%{query.strip()}%"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT file_path, symbol_type, symbol_name, docstring, line_start, line_end
            FROM symbols
            WHERE symbol_name LIKE ?
               OR COALESCE(docstring, '') LIKE ?
               OR file_path LIKE ?
            ORDER BY symbol_name ASC, file_path ASC
            LIMIT 25
            """,
            (search_term, search_term, search_term),
        ).fetchall()

        return [Symbol(**dict(row)) for row in rows]
    finally:
        conn.close()