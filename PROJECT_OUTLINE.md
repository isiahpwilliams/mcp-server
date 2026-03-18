# Loom — Project Outline

Skeletal outline for the code refactoring project. Not fully implemented.

---

## 1. Config (`nexus_mcp/config.py`)

- Add `REPO_PATH` — configurable repo root to index
- Add `INDEX_PATH` — SQLite path for symbol index (replace `books.db`)
- Remove `openlibrary_base_url`, `local_timeout`, `remote_timeout`

---

## 2. Models (`nexus_mcp/models.py`)

- **Symbol** — `file_path`, `symbol_type`, `symbol_name`, `docstring`, `line_start`, `line_end`
- **Implementation** — `file_path`, `symbol_name`, `code`, `line_start`, `line_end`
- **RefactorResult** — `success`, `file_path`, `diff_applied`, `error` (if reverted)
- Keep `NodeError` for index/worker errors
- Remove `LocalBookData`, `RemoteBookData`, `BookContext`

---

## 3. Index Node (`nexus_mcp/nodes/indexer_node.py`)

- **crawl_and_index(repo_path)** — walk repo, parse with Tree-sitter, extract symbols, write to SQLite FTS5
- **Schema:** `symbols(id, file_path, symbol_type, symbol_name, docstring, line_start, line_end)` + FTS5 virtual table
- Replace `nexus_mcp/nodes/local_node.py` (book logic)

---

## 4. Index Logic (`nexus_mcp/logic/indexer.py`)

- **search_symbols(query: str)** — FTS5 search, return list of `Symbol`-like dicts
- Replace `nexus_mcp/logic/aggregator.py`

---

## 5. Worker Node (`nexus_mcp/nodes/worker_node.py`)

- **get_implementation(symbol_name, file_path=None)** — read file, locate symbol via Tree-sitter, return code block
- New file

---

## 6. Refactor Logic (`nexus_mcp/logic/refactor.py`)

- **suggest_refactor(file_path, instructions)** — read file, get index context, call LLM, apply diff
- **Safety check** — re-parse with Tree-sitter after diff; revert if invalid
- New file

---

## 7. Server (`nexus_mcp/server.py`)

- Replace `get_book_context_tool` with:
  - `search_symbols(query: str)`
  - `get_implementation(symbol_name: str, file_path: str | None = None)`
  - `suggest_refactor(file_path: str, instructions: str)`

---

## 8. Removals

- `nexus_mcp/nodes/remote_node.py` — remove
- `nexus_mcp/nodes/local_node.py` — replace by `indexer_node.py`

---

## 9. Dependencies (`pyproject.toml`)

- Add: `tree-sitter`, `tree-sitter-python`
- Remove: `httpx` (optional, if no remote)

---

## 10. File Structure (Target)

```
nexus_mcp/
├── config.py          # REPO_PATH, INDEX_PATH
├── models.py          # Symbol, Implementation, RefactorResult, NodeError
├── server.py          # search_symbols, get_implementation, suggest_refactor
├── nodes/
│   ├── indexer_node.py   # crawl_and_index
│   └── worker_node.py   # get_implementation
├── logic/
│   ├── indexer.py       # search_symbols
│   └── refactor.py      # suggest_refactor + safety check
└── utils/
    └── errors.py       # make_node_error (keep)
```
