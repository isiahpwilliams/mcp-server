from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from ..config import SETTINGS, DATA_DIR
from ..models import LocalBookData


def _ensure_db(path: Path) -> None:
    """
    Ensure the SQLite database and table exist, with some seed data for demo.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT,
                title TEXT,
                author TEXT,
                description TEXT
            )
            """
        )
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM books")
        count = cur.fetchone()[0]
        if count == 0:
            cur.executemany(
                """
                INSERT INTO books (isbn, title, author, description)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "9780140328721",
                        "Matilda",
                        "Roald Dahl",
                        "A brilliant girl with extraordinary powers.",
                    ),
                    (
                        "9780262033848",
                        "Introduction to Algorithms",
                        "Thomas H. Cormen",
                        "Comprehensive textbook on algorithms.",
                    ),
                ],
            )
            conn.commit()
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    _ensure_db(SETTINGS.sqlite_path)
    return sqlite3.connect(SETTINGS.sqlite_path)


def fetch_book_by_isbn(isbn: str) -> Optional[LocalBookData]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, isbn, title, author, description FROM books WHERE isbn = ?",
            (isbn,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return LocalBookData(
            id=row[0], isbn=row[1], title=row[2], author=row[3], description=row[4]
        )
    finally:
        conn.close()


def fetch_book_by_title(title: str) -> Optional[LocalBookData]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, isbn, title, author, description FROM books WHERE title LIKE ?",
            (f"%{title}%",),
        )
        row = cur.fetchone()
        if not row:
            return None
        return LocalBookData(
            id=row[0], isbn=row[1], title=row[2], author=row[3], description=row[4]
        )
    finally:
        conn.close()

