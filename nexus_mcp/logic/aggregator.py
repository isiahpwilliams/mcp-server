from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple

from ..config import SETTINGS
from ..models import BookContext, LocalBookData, RemoteBookData
from ..nodes import local_node, remote_node
from ..utils.errors import make_node_error


async def _fetch_local(title: Optional[str], isbn: Optional[str]) -> Optional[LocalBookData]:
    if isbn:
        return local_node.fetch_book_by_isbn(isbn)
    if title:
        return local_node.fetch_book_by_title(title)
    return None


async def _fetch_remote(title: Optional[str], isbn: Optional[str]) -> Optional[RemoteBookData]:
    if isbn:
        return await remote_node.fetch_book_by_isbn(isbn)
    if title:
        return await remote_node.fetch_book_by_title(title)
    return None


def _merge(local: Optional[LocalBookData], remote: Optional[RemoteBookData]) -> BookContext:
    context = BookContext()

    if local:
        context.id = local.id
        context.isbn = context.isbn or local.isbn
        context.title = context.title or local.title
        context.author = context.author or local.author
        context.local_data = local

    if remote:
        context.isbn = context.isbn or remote.raw_source.get("isbn") or context.isbn
        context.title = context.title or remote.title
        context.author = context.author or remote.author
        context.remote_data = remote

    combined: Dict[str, Any] = {}
    if local:
        combined["local_description"] = local.description
    if remote:
        combined["remote_publish_year"] = remote.publish_year

    combined["sources"] = {
        "local": bool(local),
        "remote": bool(remote),
    }

    context.combined_view = combined
    context.provenance = {
        "local_present": bool(local),
        "remote_present": bool(remote),
    }
    return context


async def get_book_context(
    title: Optional[str] = None,
    isbn: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Orchestrate concurrent fetches from local and remote nodes, apply timeouts,
    and merge into a unified context object.
    """
    node_errors = []

    async def safe_local() -> Tuple[Optional[LocalBookData], Optional[Exception]]:
        try:
            result = await asyncio.to_thread(_fetch_local, title, isbn)
            return result, None
        except Exception as exc:  # noqa: BLE001
            return None, exc

    async def safe_remote() -> Tuple[Optional[RemoteBookData], Optional[Exception]]:
        try:
            result = await _fetch_remote(title, isbn)
            return result, None
        except Exception as exc:  # noqa: BLE001
            return None, exc

    local_task = asyncio.wait_for(safe_local(), timeout=SETTINGS.local_timeout)
    remote_task = asyncio.wait_for(safe_remote(), timeout=SETTINGS.remote_timeout)

    local_result, remote_result = await asyncio.gather(
        local_task,
        remote_task,
        return_exceptions=True,
    )

    local_data: Optional[LocalBookData] = None
    remote_data: Optional[RemoteBookData] = None

    if isinstance(local_result, Exception):
        node_errors.append(make_node_error("local", local_result))
    else:
        local_data, local_exc = local_result
        if local_exc:
            node_errors.append(make_node_error("local", local_exc))

    if isinstance(remote_result, Exception):
        node_errors.append(make_node_error("remote", remote_result))
    else:
        remote_data, remote_exc = remote_result
        if remote_exc:
            node_errors.append(make_node_error("remote", remote_exc))

    if not local_data and not remote_data and node_errors:
        # All failed: raise a structured error to the client.
        return {
            "success": False,
            "error": "Both local and remote nodes failed or timed out.",
            "node_errors": [e.model_dump() for e in node_errors],
        }

    context = _merge(local_data, remote_data)
    context.node_errors = node_errors
    response = context.to_response()
    response["success"] = True
    return response

