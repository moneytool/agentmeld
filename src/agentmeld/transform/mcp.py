"""MCP server declarations, which come in three incompatible schemas.

=====================  =========================  ====================
file                   top-level key              per-server shape
=====================  =========================  ====================
``.mcp.json``          ``mcpServers``             command/args/env
``.vscode/mcp.json``   ``servers``                adds ``type: stdio``
``.zed/settings.json`` ``context_servers``        adds ``source: custom``
=====================  =========================  ====================

These files hold user settings, so every transformer here merges: it replaces
the servers agentmeld owns and leaves everything else -- other top-level keys,
and servers a human added by hand -- untouched.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

from ..model import Asset, KindSpec
from . import GenContext, register
from .json_merge import dumps, load_jsonc

__all__ = ["canonical_servers", "SHAPES"]


def canonical_servers(asset: Asset) -> Dict[str, Any]:
    """Read ``.ai/mcp.json``, accepting either a wrapped or bare mapping."""
    text = asset.body if asset.body.strip() else "{}"
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(".ai/mcp.json must contain a JSON object")
    servers = data.get("mcpServers", data)
    if not isinstance(servers, dict):
        raise ValueError(".ai/mcp.json: 'mcpServers' must be an object")
    return servers


def _shape_passthrough(server: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(server)


def _shape_vscode(server: Mapping[str, Any]) -> Dict[str, Any]:
    """VS Code wants an explicit transport for stdio servers."""
    out = dict(server)
    if "url" not in out and "type" not in out:
        out["type"] = "stdio"
    return out


def _shape_zed(server: Mapping[str, Any]) -> Dict[str, Any]:
    """Zed calls them context servers and tags externally-defined ones."""
    out = {"source": "custom"}
    for key in ("command", "args", "env", "url"):
        if key in server:
            out[key] = server[key]
    for key, value in server.items():
        out.setdefault(key, value)
    return out


SHAPES = {
    "mcpServers": _shape_passthrough,
    "servers": _shape_vscode,
    "context_servers": _shape_zed,
}


def _merge(
    asset: Asset,
    ctx: GenContext,
    existing: Optional[bytes],
    key: str,
) -> bytes:
    shape = SHAPES[key]
    wanted = {name: shape(cfg) for name, cfg in canonical_servers(asset).items()}

    document: Dict[str, Any] = {}
    if existing:
        document, _had_comments = load_jsonc(existing.decode("utf-8"))

    section = dict(document.get(key) or {})

    # Drop only servers we previously owned and no longer declare. A server a
    # human added by hand is not ours to delete.
    for name in ctx.owned:
        if name not in wanted:
            section.pop(name, None)

    section.update(wanted)
    document[key] = section
    return dumps(document)


@register("mcp_mcp_servers")
def mcp_mcp_servers(asset, spec, ctx, existing=None):  # noqa: ANN001
    return _merge(asset, ctx, existing, "mcpServers")


@register("mcp_servers")
def mcp_servers(asset, spec, ctx, existing=None):  # noqa: ANN001
    return _merge(asset, ctx, existing, "servers")


@register("mcp_context_servers")
def mcp_context_servers(asset, spec, ctx, existing=None):  # noqa: ANN001
    return _merge(asset, ctx, existing, "context_servers")
