from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from nexus_mcp.logic.indexer import search_symbols as search_symbols_logic
from nexus_mcp.logic.refactor import (
    suggest_refactor as suggest_refactor_logic,
    suggest_refactor_llm as suggest_refactor_llm_logic,
)
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
    def get_implementation(
        symbol_name: str, file_path: str | None = None, line_start: int | None = None
    ) -> dict:
        """
        Get the implementation of a function or class.
        """
        implementation = get_implementation_logic(symbol_name, file_path, line_start)
        return implementation.model_dump()

    @app.tool()
    def suggest_refactor(file_path: str, symbol_name: str, instructions: str) -> dict:
        """
        Apply a symbol-scoped refactor to a file with a syntax safety gate.

        `instructions` must contain the full replacement `def ...` / `class ...` block.
        """
        result = suggest_refactor_logic(file_path=file_path, symbol_name=symbol_name, instructions=instructions)
        return result.model_dump()

    @app.tool()
    def suggest_refactor_llm(file_path: str, symbol_name: str, instructions: str) -> dict:
        """
        LLM-driven symbol-scoped refactor (Gemini).

        `instructions` is high-level guidance; the LLM will produce the full replacement code.
        Requires `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and `GEMINI_MODEL` in the environment.
        """
        result = suggest_refactor_llm_logic(file_path=file_path, symbol_name=symbol_name, instructions=instructions)
        return result.model_dump()

    return app