from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeError(BaseModel):
    node: str
    error_type: str
    message: str


class LocalBookData(BaseModel):
    id: Optional[int] = None
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None


class RemoteBookData(BaseModel):
    raw_source: Dict[str, Any] = Field(default_factory=dict)
    title: Optional[str] = None
    author: Optional[str] = None
    publish_year: Optional[int] = None


class BookContext(BaseModel):
    """
    Unified, LLM-friendly context object for a book.
    """

    id: Optional[int] = None
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None

    local_data: Optional[LocalBookData] = None
    remote_data: Optional[RemoteBookData] = None

    combined_view: Dict[str, Any] = Field(default_factory=dict)

    node_errors: List[NodeError] = Field(default_factory=list)

    last_updated: datetime = Field(default_factory=datetime.utcnow)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def to_response(self) -> Dict[str, Any]:
        """
        Convert to plain dict suitable for MCP tool output.
        """
        return self.model_dump()

