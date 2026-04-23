from __future__ import annotations

import sqlite3
from pathlib import Path

from tree_sitter import Node

from nexus_mcp.config import SETTINGS
from nexus_mcp.models import Implementation
from nexus_mcp.nodes.indexer_node import PARSER, _node_text


def _resolve_file_path(symbol_name: str, file_path: str | None, line_start: int | None) -> Path:
    if file_path is not None:
        return (SETTINGS.repo_path / file_path).resolve()

    conn = sqlite3.connect(SETTINGS.index_path)
    try:
        if line_start is None:
            rows = conn.execute(
                "SELECT file_path, line_start, line_end FROM symbols WHERE symbol_name = ?",
                (symbol_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT file_path, line_start, line_end FROM symbols WHERE symbol_name = ? AND line_start = ?",
                (symbol_name, line_start),
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise ValueError(
            f"No indexed symbol named {symbol_name!r}. "
            "Run indexing or pass file_path explicitly."
        )
    if len(rows) > 1:
        paths = sorted({f"{r[0]}:{r[1]}-{r[2]}" for r in rows})
        raise ValueError(
            f"Multiple matches for {symbol_name!r}: {paths}. "
            "Pass file_path, or pass line_start from search_symbols to disambiguate."
        )
    return (SETTINGS.repo_path / rows[0][0]).resolve()


def _find_definition_node(
    root: Node, source_bytes: bytes, symbol_name: str, line_start: int | None
) -> Node | None:
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        if node.type in ("function_definition", "class_definition"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _node_text(source_bytes, name_node).strip()
                if name == symbol_name and (line_start is None or (node.start_point[0] + 1) == line_start):
                    return node
        for i in range(node.child_count - 1, -1, -1):
            stack.append(node.child(i))
    return None


def get_implementation(
    symbol_name: str, file_path: str | None = None, line_start: int | None = None
) -> Implementation:
    """
    Read the file, locate the symbol with Tree-sitter, return its source slice.
    """
    abs_path = _resolve_file_path(symbol_name, file_path, line_start)
    if not abs_path.is_file():
        raise FileNotFoundError(f"File not found: {abs_path}")

    source_bytes = abs_path.read_bytes()
    tree = PARSER.parse(source_bytes)
    node = _find_definition_node(tree.root_node, source_bytes, symbol_name, line_start)
    if node is None:
        raise ValueError(f"Symbol {symbol_name!r} not found in {abs_path}")

    code = _node_text(source_bytes, node)
    rel = str(abs_path.relative_to(SETTINGS.repo_path.resolve()))
    line_start = node.start_point[0] + 1
    line_end = node.end_point[0] + 1

    return Implementation(
        file_path=rel,
        symbol_name=symbol_name,
        code=code,
        line_start=line_start,
        line_end=line_end,
    )