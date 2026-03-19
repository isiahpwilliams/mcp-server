from __future__ import annotations


from nexus_mcp.server import create_app



def main() -> None:
    app = create_app()
    app.run()   # <-- THIS replaces run(app)


if __name__ == "__main__":
    main()
