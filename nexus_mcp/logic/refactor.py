from __future__ import annotations

import difflib
import sqlite3

from tree_sitter import Node

from nexus_mcp.config import SETTINGS
from nexus_mcp.models import RefactorResult
from nexus_mcp.nodes.worker_node import get_implementation
from nexus_mcp.nodes.indexer_node import PARSER, _node_text, reindex_file
from nexus_mcp.llm.gemini_client import generate_replacement_symbol_code


def _find_definition_node(root: Node, source_bytes: bytes, symbol_name: str) -> Node | None:
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        if node.type in ("function_definition", "class_definition"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _node_text(source_bytes, name_node).strip()
                if name == symbol_name:
                    return node
        for i in range(node.child_count - 1, -1, -1):
            stack.append(node.child(i))
    return None


def _tree_has_error(root: Node) -> bool:
    # py-tree-sitter exposes `.has_error` in some versions, but walking for
    # explicit ERROR nodes is compatible across versions.
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR":
            return True
        # Tree-sitter can represent invalid syntax with "missing" tokens
        # (e.g. (MISSING ")")) without producing ERROR nodes.
        if getattr(node, "is_missing", False):
            return True
        for i in range(node.child_count):
            stack.append(node.child(i))
    return False


def _first_top_level_definition(root: Node) -> Node | None:
    """
    Return the first top-level function/class definition node, if present.

    Tree-sitter-python wraps the file in a `module` node. Top-level statements
    are direct children of that module.
    """
    for i in range(root.child_count):
        child = root.child(i)
        if child.type in ("function_definition", "class_definition"):
            return child
    return None


def _extract_replacement_code(symbol_name: str, instructions: str) -> bytes:
    """
    Symbol-scoped refactor strategy (deterministic):

    `instructions` must contain the full replacement source for the *symbol*
    (a `def ...` or `class ...` block). The caller (LLM) is responsible for
    generating that updated symbol implementation.
    """
    code = instructions.strip()
    if not code:
        raise ValueError("instructions must include replacement symbol code.")
    if not (code.startswith("def ") or code.startswith("async def ") or code.startswith("class ")):
        raise ValueError(
            "For symbol-scoped refactors, instructions must be the full replacement "
            "symbol code starting with 'def', 'async def', or 'class'."
        )

    replacement_bytes = (code + "\n").encode("utf-8")
    replacement_tree = PARSER.parse(replacement_bytes)
    if _tree_has_error(replacement_tree.root_node):
        raise ValueError("Replacement code does not parse cleanly (Tree-sitter ERROR node).")

    top = _first_top_level_definition(replacement_tree.root_node)
    if top is None:
        raise ValueError("Replacement code must contain a top-level def/class.")

    # Hardening 1: ensure the replacement is exactly one *named* top-level symbol.
    # This rejects cases where the replacement contains multiple defs/classes.
    named_toplevel: list[Node] = []
    for i in range(replacement_tree.root_node.child_count):
        child = replacement_tree.root_node.child(i)
        if child.is_named:
            named_toplevel.append(child)

    top_span = (top.start_byte, top.end_byte, top.type)
    if len(named_toplevel) != 1 or (
        (named_toplevel[0].start_byte, named_toplevel[0].end_byte, named_toplevel[0].type) != top_span
    ):
        raise ValueError("Replacement code must contain only a single top-level symbol.")

    # Hardening 2+3: ensure symbol kind + name match.
    if top.type == "function_definition" and not (
        code.startswith("def ") or code.startswith("async def ")
    ):
        raise ValueError("Replacement must be a function definition (def/async def).")
    if top.type == "class_definition" and not code.startswith("class "):
        raise ValueError("Replacement must be a class definition (class).")

    name_node = top.child_by_field_name("name")
    if name_node is None:
        raise ValueError("Replacement symbol has no name node.")
    found_name = _node_text(replacement_bytes, name_node).strip()
    if found_name != symbol_name:
        raise ValueError(
            f"Replacement symbol name {found_name!r} does not match requested {symbol_name!r}."
        )

    return replacement_bytes


def suggest_refactor(file_path: str, symbol_name: str, instructions: str) -> RefactorResult:
    """
    Symbol-scoped refactor.

    - Locates `symbol_name` in `file_path` using Tree-sitter.
    - Replaces only that symbol's source with the replacement code provided
      in `instructions`.
    - Runs a Tree-sitter parse safety gate; if invalid, does not write changes.
    - Returns a unified diff of the full file change.
    """
    abs_path = (SETTINGS.repo_path / file_path).resolve()
    if not abs_path.is_file():
        return RefactorResult(
            success=False,
            file_path=file_path,
            diff_applied="",
            error=f"File not found: {abs_path}",
        )

    original_bytes = abs_path.read_bytes()
    original_text = original_bytes.decode("utf-8", errors="replace")

    tree = PARSER.parse(original_bytes)
    target = _find_definition_node(tree.root_node, original_bytes, symbol_name)
    if target is None:
        return RefactorResult(
            success=False,
            file_path=file_path,
            diff_applied="",
            error=f"Symbol {symbol_name!r} not found in {file_path}",
        )

    original_slice = original_bytes[target.start_byte : target.end_byte]
    try:
        replacement = _extract_replacement_code(symbol_name, instructions)
    except ValueError as exc:
        return RefactorResult(
            success=False,
            file_path=file_path,
            diff_applied="",
            error=str(exc),
        )

    # Preserve the original slice's trailing newline convention so no-op
    # replacements don't introduce a file diff.
    if original_slice.endswith(b"\n") and not replacement.endswith(b"\n"):
        replacement += b"\n"
    elif not original_slice.endswith(b"\n") and replacement.endswith(b"\n"):
        replacement = replacement.rstrip(b"\n")

    if replacement == original_slice:
        return RefactorResult(success=True, file_path=file_path, diff_applied="", error=None)

    new_bytes = original_bytes[: target.start_byte] + replacement + original_bytes[target.end_byte :]

    new_tree = PARSER.parse(new_bytes)
    if _tree_has_error(new_tree.root_node):
        diff = "".join(
            difflib.unified_diff(
                original_text.splitlines(keepends=True),
                new_bytes.decode("utf-8", errors="replace").splitlines(keepends=True),
                fromfile=file_path,
                tofile=file_path,
            )
        )
        return RefactorResult(
            success=False,
            file_path=file_path,
            diff_applied=diff,
            error="Refactor rejected: Tree-sitter parse error after applying change.",
        )

    # Write file only after passing the safety gate.
    abs_path.write_bytes(new_bytes)

    # Keep the index fresh for subsequent search/fetch calls.
    try:
        reindex_file(file_path=file_path)
    except Exception as exc:  # noqa: BLE001
        return RefactorResult(
            success=True,
            file_path=file_path,
            diff_applied="",
            error=f"Refactor applied, but reindex failed: {type(exc).__name__}: {exc}",
        )

    new_text = new_bytes.decode("utf-8", errors="replace")
    diff = "".join(
        difflib.unified_diff(
            original_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path,
        )
    )
    return RefactorResult(success=True, file_path=file_path, diff_applied=diff, error=None)


def _symbol_outline_for_file(file_path: str) -> str:
    conn = sqlite3.connect(SETTINGS.index_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT symbol_type, symbol_name, line_start, line_end, docstring
            FROM symbols
            WHERE file_path = ?
            ORDER BY line_start ASC
            """,
            (file_path,),
        ).fetchall()
    finally:
        conn.close()

    lines: list[str] = []
    for r in rows:
        doc = (r["docstring"] or "").strip().replace("\n", " ")
        if len(doc) > 160:
            doc = doc[:157] + "..."
        lines.append(
            f"- {r['symbol_type']} {r['symbol_name']} ({r['line_start']}-{r['line_end']}): {doc}".rstrip()
        )
    return "\n".join(lines)


def suggest_refactor_llm(file_path: str, symbol_name: str, instructions: str) -> RefactorResult:
    """
    LLM-driven symbol-scoped refactor.

    - Fetch current symbol implementation
    - Provide a small outline of other symbols in the file (from the index)
    - Ask Gemini to return the full replacement symbol code ONLY
    - Apply via `suggest_refactor` (Tree-sitter safety gate)
    """
    impl = get_implementation(symbol_name=symbol_name, file_path=file_path)
    outline = _symbol_outline_for_file(file_path)

    prompt = "\n".join(
        [
            "You are refactoring a Python codebase.",
            "Return ONLY the full replacement code for the specified symbol.",
            "Do not include markdown fences, explanations, or multiple symbols.",
            "",
            f"Target file: {file_path}",
            f"Target symbol: {symbol_name}",
            "",
            "Other symbols in this file:",
            outline or "(none)",
            "",
            "Current implementation:",
            impl.code,
            "",
            "Refactor instructions:",
            instructions.strip(),
            "",
            "Return ONLY the updated symbol code (starting with def/async def/class).",
        ]
    )

    replacement_code = generate_replacement_symbol_code(prompt)
    return suggest_refactor(file_path=file_path, symbol_name=symbol_name, instructions=replacement_code)

