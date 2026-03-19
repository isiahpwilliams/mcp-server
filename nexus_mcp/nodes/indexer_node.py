from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from nexus_mcp.config import SETTINGS


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            symbol_type TEXT NOT NULL,
            symbol_name TEXT NOT NULL,
            docstring TEXT,
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL
        )
    """)
    conn.execute("DELETE FROM symbols")
    conn.commit()


def _iter_python_files(repo_path: Path) -> list[Path]:
    excluded_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "node_modules",
        "dist",
        "build",
        "data",
    }

    files: list[Path] = []
    for path in repo_path.rglob("*.py"):
        if any(part in excluded_dirs for part in path.parts):
            continue
        files.append(path)
    return files


def _extract_symbols_from_file(
    file_path: Path,
    repo_path: Path,
) -> list[tuple[str, str, str, str | None, int, int]]:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    relative_path = str(file_path.relative_to(repo_path))
    symbols: list[tuple[str, str, str, str | None, int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            symbols.append((
                relative_path,
                "function",
                node.name,
                ast.get_docstring(node),
                node.lineno,
                getattr(node, "end_lineno", node.lineno),
            ))
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append((
                relative_path,
                "function",
                node.name,
                ast.get_docstring(node),
                node.lineno,
                getattr(node, "end_lineno", node.lineno),
            ))
        elif isinstance(node, ast.ClassDef):
            symbols.append((
                relative_path,
                "class",
                node.name,
                ast.get_docstring(node),
                node.lineno,
                getattr(node, "end_lineno", node.lineno),
            ))

    return symbols


def crawl_and_index(repo_path: Path | None = None) -> int:
    """
    Scan the repository for Python files, extract class/function symbols,
    and rebuild the SQLite index.
    """
    repo_root = repo_path or SETTINGS.repo_path
    db_path = SETTINGS.index_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)

    try:
        _create_tables(conn)
        total = 0

        for py_file in _iter_python_files(repo_root):
            try:
                symbols = _extract_symbols_from_file(py_file, repo_root)
            except (SyntaxError, UnicodeDecodeError):
                continue

            conn.executemany(
                """
                INSERT INTO symbols (
                    file_path,
                    symbol_type,
                    symbol_name,
                    docstring,
                    line_start,
                    line_end
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                symbols,
            )
            total += len(symbols)

        conn.commit()
        return total
    finally:
        conn.close()