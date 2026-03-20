from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from nexus_mcp.config import SETTINGS


PY_LANGUAGE = Language(tree_sitter_python.language())
PARSER = Parser(PY_LANGUAGE)


def _node_text(source_bytes: bytes, node: Node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _find_first_descendant_of_type(start: Node, wanted_type: str) -> Node | None:
    stack = [start]
    while stack:
        node = stack.pop()
        if node.type == wanted_type:
            return node
        for i in range(node.child_count):
            stack.append(node.child(i))
    return None


def _extract_docstring(container: Node, source_bytes: bytes) -> str | None:
    body = container.child_by_field_name("body")
    if body is None or body.child_count == 0:
        return None

    # In Python, a docstring is the first statement in the body and is represented
    # as an expression_statement holding a string literal.
    first_stmt = body.child(0)
    if first_stmt.type != "expression_statement":
        return None

    string_node = _find_first_descendant_of_type(first_stmt, "string")
    if string_node is None:
        return None

    literal = _node_text(source_bytes, string_node)
    try:
        value = ast.literal_eval(literal)
        return value if isinstance(value, str) else None
    except Exception:
        # Fallback: return raw literal text (still useful for the LLM).
        return literal.strip("\"'")


def _create_tables(conn: sqlite3.Connection) -> None:
    # Build/refresh the symbol index.
    # `symbols` stores structured metadata, and `symbols_fts` is an FTS5 index over
    # `symbol_name` / `docstring` / `file_path`.
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS symbols_ai;
        DROP TRIGGER IF EXISTS symbols_ad;
        DROP TRIGGER IF EXISTS symbols_au;
        DROP TABLE IF EXISTS symbols_fts;

        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            symbol_type TEXT NOT NULL,
            symbol_name TEXT NOT NULL,
            docstring TEXT,
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL
        );

        -- Start clean so we don't rely on delete triggers for the rebuild.
        DELETE FROM symbols;

        CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
            file_path,
            symbol_type,
            symbol_name,
            docstring,
            content='symbols',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
            INSERT INTO symbols_fts(rowid, file_path, symbol_type, symbol_name, docstring)
            VALUES (new.id, new.file_path, new.symbol_type, new.symbol_name, new.docstring);
        END;

        CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
            INSERT INTO symbols_fts(symbols_fts, rowid, file_path, symbol_type, symbol_name, docstring)
            VALUES ('delete', old.id, old.file_path, old.symbol_type, old.symbol_name, old.docstring);
        END;

        CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
            INSERT INTO symbols_fts(symbols_fts, rowid, file_path, symbol_type, symbol_name, docstring)
            VALUES ('delete', old.id, old.file_path, old.symbol_type, old.symbol_name, old.docstring);
            INSERT INTO symbols_fts(rowid, file_path, symbol_type, symbol_name, docstring)
            VALUES (new.id, new.file_path, new.symbol_type, new.symbol_name, new.docstring);
        END;
        """
    )
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
    source_text = file_path.read_text(encoding="utf-8")
    source_bytes = source_text.encode("utf-8")
    tree = PARSER.parse(source_bytes)
    root_node = tree.root_node

    relative_path = str(file_path.relative_to(repo_path))
    symbols: list[tuple[str, str, str, str | None, int, int]] = []

    # Walk the tree and extract function/class symbols.
    #
    # Note: Tree-sitter's line points are 0-based but we store 1-based lines
    while stack:
        node = stack.pop()

        symbol_type: str | None = None
        if node.type == "function_definition":
            symbol_type = "function"
        elif node.type == "class_definition":
            symbol_type = "class"

        if symbol_type:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                symbol_name = _node_text(source_bytes, name_node)
                docstring = _extract_docstring(node, source_bytes)
                line_start = node.start_point[0] + 1
                line_end = node.end_point[0] + 1
                symbols.append(
                    (
                        relative_path,
                        symbol_type,
                        symbol_name,
                        docstring,
                        line_start,
                        line_end,
                    )
                )

        for i in range(node.child_count):
            stack.append(node.child(i))

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
            except UnicodeDecodeError:
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