from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Symbol(BaseModel):
    """
    Metadata for a code symbol (function, class, etc.) in the index.
    Used by search_symbols to return lightweight results without full source.
    """

    file_path: str
    symbol_type: Literal["function", "class"]
    symbol_name: str
    docstring: str | None = None
    line_start: int
    line_end: int

class Implementation(BaseModel):
    file_path: str
    symbol_name: str
    code: str
    line_start: int
    line_end: int

class RefactorResult(BaseModel):
    success: bool
    file_path: str
    diff_applied: str
    error: str | None = None


class NodeError(BaseModel):
    node: str
    error_type: str
    message: str

