from __future__ import annotations

import difflib
from pathlib import Path

from tree_sitter import Node

from nexus_mcp.config import SETTINGS
from nexus_mcp.models import RefactorResult
from nexus_mcp.nodes.indexer_node import PARSER, _node_text


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
        for i in range(node.child_count):
            stack.append(node.child(i))
    return False


def _extract_replacement_code(instructions: str) -> str:
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
    return code


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
    replacement_text = _extract_replacement_code(instructions)
    replacement = replacement_text.encode("utf-8")

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

