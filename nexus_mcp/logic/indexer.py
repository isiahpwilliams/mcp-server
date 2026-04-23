from __future__ import annotations

import re
import sqlite3

from nexus_mcp.config import SETTINGS
from nexus_mcp.models import Symbol


def search_symbols(query: str) -> list[Symbol]:
    """
    Search indexed symbols by name, docstring, or file path.
    """
    raw_query = query.strip()
    if not raw_query:
        return []

    # Tokenize and build an FTS prefix query so searches like "refactor agent"
    # can match tokens inside symbol names/docstrings.
    tokens = re.findall(r"[A-Za-z0-9_]+", raw_query)
    if not tokens:
        return []
    fts_query = " ".join(f"{tok}*" for tok in tokens)

    db_path = SETTINGS.index_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT
                s.file_path,
                s.symbol_type,
                s.symbol_name,
                s.docstring,
                s.line_start,
                s.line_end
            FROM symbols_fts AS fts
            JOIN symbols AS s ON s.id = fts.rowid
            WHERE symbols_fts MATCH ?
            ORDER BY bm25(symbols_fts)
            LIMIT 25
            """,
            (fts_query,),
        ).fetchall()

        return [Symbol(**dict(row)) for row in rows]
    except sqlite3.OperationalError:
        # Migration safety: if FTS5 isn't available yet for some reason, fall back
        # to the previous LIKE-based search so the tool keeps working.
        search_term = f"%{raw_query}%"
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

