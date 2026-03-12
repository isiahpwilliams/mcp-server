from __future__ import annotations

from mcp.server.fastmcp import run

from nexus_mcp.server import create_app


def main() -> None:
    """
    Entry point for running the Nexus-MCP server.
    """
    app = create_app()
    run(app)


if __name__ == "__main__":
    main()
