from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


@dataclass
class Settings:
    # Local data
    sqlite_path: Path = DATA_DIR / "books.db"

    # Remote API (OpenLibrary)
    openlibrary_base_url: str = "https://openlibrary.org"

    # Timeouts (seconds)
    local_timeout: float = float(os.getenv("NEXUS_LOCAL_TIMEOUT", "1.0"))
    remote_timeout: float = float(os.getenv("NEXUS_REMOTE_TIMEOUT", "2.0"))


def get_settings() -> Settings:
    return Settings()


SETTINGS = get_settings()

