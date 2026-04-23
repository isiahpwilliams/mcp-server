MCP Server
==========

Loom MCP Server
---------------

This repo is an MCP server for **codebase navigation + symbol-scoped refactoring**:

- Index Python symbols (functions/classes) into SQLite + FTS5
- Search symbols via `search_symbols`
- Fetch a specific implementation via `get_implementation`
- Apply symbol-scoped refactors via `suggest_refactor` (replacement code) or `suggest_refactor_llm` (Gemini)

## Setup

**Install dependencies**

```bash
uv sync
```

## Run the server

```bash
uv run python main.py
```

## Environment variables (Gemini)

`suggest_refactor_llm` requires:

- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- `GEMINI_MODEL` (e.g. `gemini-2.0-flash`)

```bash
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-2.0-flash"
```

## MCP tools

### `index_repo()`

Build/rebuild the full repo symbol index.

### `reindex_file(file_path: str)`

Incrementally re-index one file (used after edits).

### `search_symbols(query: str)`

Returns up to 25 matches (FTS5-ranked). Each result includes `file_path` and `line_start` for disambiguation.

### `get_implementation(symbol_name: str, file_path: str | None = None, line_start: int | None = None)`

Fetches the exact function/class body using Tree-sitter. Prefer passing `file_path` + `line_start` from `search_symbols`.

### `suggest_refactor(file_path: str, symbol_name: str, instructions: str)`

Applies a **symbol-scoped replacement**. `instructions` must be the full replacement code block starting with:

- `def ...`
- `async def ...`
- `class ...`

Includes a Tree-sitter safety gate (rejects parse errors and missing tokens), and re-indexes the file on success.

### `suggest_refactor_llm(file_path: str, symbol_name: str, instructions: str)`

Same as `suggest_refactor`, but uses Gemini to generate the replacement symbol code from high-level instructions.