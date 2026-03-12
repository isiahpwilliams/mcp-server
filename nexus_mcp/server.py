from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .logic.aggregator import get_book_context


app = FastMCP("nexus-mcp")


@app.tool()
async def get_book_context_tool(
    title: str | None = None,
    isbn: str | None = None,
) -> dict[str, Any]:
    """
    Fetches book context by querying both the local node and remote node.

    At least one of title or isbn must be provided.
    """
    if not title and not isbn:
        raise ValueError("At least one of 'title' or 'isbn' must be provided.")

    context = await get_book_context(title=title, isbn=isbn)
    return context


def create_app() -> FastMCP:
    """
    Factory to create and return the FastMCP application instance.
    """
    return app

