from __future__ import annotations

from typing import Any, Dict

from ..models import NodeError


def make_node_error(node: str, exc: Exception) -> NodeError:
    return NodeError(node=node, error_type=type(exc).__name__, message=str(exc))


def error_to_dict(node_error: NodeError) -> Dict[str, Any]:
    return node_error.model_dump()

