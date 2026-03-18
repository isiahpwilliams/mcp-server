from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


@dataclass
class Settings:
    # Repo to index (default: project root)
    repo_path: Path = BASE_DIR

    # Symbol index (SQLite with FTS5)
    index_path: Path = DATA_DIR / "symbols.db"


def get_settings() -> Settings:
    return Settings()


SETTINGS = get_settings()

