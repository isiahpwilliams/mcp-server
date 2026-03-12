from __future__ import annotations

from typing import Optional

import httpx

from ..config import SETTINGS
from ..models import RemoteBookData


async def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=SETTINGS.openlibrary_base_url, timeout=SETTINGS.remote_timeout)


async def fetch_book_by_isbn(isbn: str) -> Optional[RemoteBookData]:
    async with _get_client() as client:
        # OpenLibrary ISBN API
        resp = await client.get(f"/isbn/{isbn}.json")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return RemoteBookData(
            raw_source=data,
            title=data.get("title"),
            author=None,  # OpenLibrary stores authors as references; keep raw in raw_source
            publish_year=data.get("publish_date"),
        )


async def fetch_book_by_title(title: str) -> Optional[RemoteBookData]:
    async with _get_client() as client:
        resp = await client.get("/search.json", params={"title": title, "limit": 1})
        if resp.status_code != 200:
            return None
        data = resp.json()
        docs = data.get("docs") or []
        if not docs:
            return None
        doc = docs[0]
        authors = doc.get("author_name") or []
        publish_years = doc.get("first_publish_year")
        return RemoteBookData(
            raw_source=doc,
            title=doc.get("title"),
            author=authors[0] if authors else None,
            publish_year=publish_years,
        )

