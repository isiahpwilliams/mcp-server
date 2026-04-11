from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from nexus_mcp.logic.indexer import search_symbols as search_symbols_logic
from nexus_mcp.nodes.indexer_node import crawl_and_index
from nexus_mcp.nodes.worker_node import get_implementation as get_implementation_logic


def create_app() -> FastMCP:
    app = FastMCP("nexus-mcp")

    indexed_count = crawl_and_index()
    print(f"[nexus-mcp] Indexed {indexed_count} symbols.")

    @app.tool()
    def search_symbols(query: str) -> list[dict]:
        """
        Search for functions and classes in the indexed Python repository.
        """
        results = search_symbols_logic(query)
        return [result.model_dump() for result in results]

    @app.tool()
    def get_implementation(symbol_name: str, file_path: str | None = None) -> dict:
        """
        Get the implementation of a function or class.
        """
        implementation = get_implementation_logic(symbol_name, file_path)
        return implementation.model_dump()

    return app