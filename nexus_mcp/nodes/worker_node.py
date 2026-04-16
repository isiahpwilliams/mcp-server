from __future__ import annotations

import ast
from pathlib import Path

from nexus_mcp.config import SETTINGS
from nexus_mcp.models import Implementation


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


def get_implementation(
    symbol_name: str,
    file_path: str | None = None,
) -> Implementation | None:
    """
    Return the source code for a function or class.

    If file_path is provided, only that file is searched.
    Otherwise, all Python files in the repo are scanned until the symbol is found.
    """
    repo_root = SETTINGS.repo_path

    if file_path is not None:
        candidate_files = [repo_root / file_path]
    else:
        candidate_files = _iter_python_files(repo_root)

    for path in candidate_files:
        if not path.exists() or not path.is_file():
            continue

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    start_line = node.lineno
                    end_line = getattr(node, "end_lineno", node.lineno)

                    code = "\n".join(lines[start_line - 1:end_line])

                    return Implementation(
                        file_path=str(path.relative_to(repo_root)),
                        symbol_name=symbol_name,
                        code=code,
                        line_start=start_line,
                        line_end=end_line,
                    )

    return None