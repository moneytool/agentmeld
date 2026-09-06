"""Turning one canonical asset into one vendor's file format.

Most vendors differ only in frontmatter key names, which the declarative
registry handles as data. The rest need real code -- Gemini CLI commands are
TOML, and MCP config comes in three incompatible JSON schemas -- so those get a
named transformer referenced from the adapter's TOML.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence, Tuple

from ..model import Asset, KindSpec
from . import frontmatter as fm

__all__ = [
    "GenContext",
    "HEADER_TOKEN",
    "register",
    "get",
    "source_hash",
    "parse_header",
]

#: Marker that identifies a file as ours. Its absence on a file we expected to
#: manage is what distinguishes "someone hand-wrote this" from "we generated it",
#: which is the difference between a conflict and a safe overwrite.
HEADER_TOKEN = "agentmeld:generated"

_EDIT_NOTE = "edit the source, not this file"


@dataclass(frozen=True)
class GenContext:
    """Provenance stamped into every generated file."""

    source: str
    """Canonical source path, repo-relative, POSIX-style."""

    source_hash: str
    tool: str

    owned: Tuple[str, ...] = ()
    """Names inside a merged config that we managed on the previous run.

    Only these may be removed; anything else in the file was put there by a
    human and is not ours to delete.
    """


def source_hash(data: bytes) -> str:
    """Short, stable digest of canonical bytes."""
    return hashlib.sha256(data).hexdigest()[:12]


def header_line(ctx: GenContext, comment: str = "<!--", close: str = "-->") -> str:
    return "{open} {tok} source={src} hash={h} -- {note} {close}\n".format(
        open=comment,
        tok=HEADER_TOKEN,
        src=ctx.source,
        h=ctx.source_hash,
        note=_EDIT_NOTE,
        close=close,
    )


def parse_header(text: str) -> Dict[str, str]:
    """Extract ``source=``/``hash=`` from a generated file, or ``{}`` if absent.

    Only the first 40 lines are scanned: a header we did not put near the top is
    not a header we wrote.
    """
    for line in text.splitlines()[:40]:
        if HEADER_TOKEN not in line:
            continue
        out: Dict[str, str] = {}
        for token in line.split():
            if "=" in token:
                key, _, value = token.partition("=")
                if key in ("source", "hash"):
                    out[key] = value
        return out
    return {}


# ---------------------------------------------------------------------------
# transformer registry
# ---------------------------------------------------------------------------

Transformer = Callable[..., bytes]
"""``(asset, spec, ctx, existing=None) -> bytes``.

``existing`` carries the current on-disk bytes and is only meaningful for
the ``merge`` strategy, where the vendor file is shared with the user.
"""

_REGISTRY: Dict[str, Transformer] = {}


def register(name: str) -> Callable[[Transformer], Transformer]:
    def decorate(func: Transformer) -> Transformer:
        _REGISTRY[name] = func
        return func

    return decorate


def get(name: str) -> Transformer:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            "unknown transformer {!r}; registered: {}".format(name, sorted(_REGISTRY))
        ) from None


def names() -> list:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# the default: markdown with translated frontmatter
# ---------------------------------------------------------------------------


@register("markdown")
def markdown(asset: Asset, spec: KindSpec, ctx: GenContext, existing=None) -> bytes:
    """Markdown out, with frontmatter mapped into the vendor's vocabulary."""
    mapped = fm.map_keys(asset.frontmatter, spec.frontmatter, spec.defaults)
    body = asset.body.strip("\n")
    head = header_line(ctx)
    if mapped:
        text = "---\n{y}---\n{head}\n{body}\n".format(
            y=fm._dump(mapped), head=head, body=body
        )
    else:
        text = "{head}\n{body}\n".format(head=head, body=body)
    return text.encode("utf-8")


# Importing these registers the remaining transformers.
from . import mcp as _mcp  # noqa: E402,F401
from . import toml_cmd as _toml_cmd  # noqa: E402,F401
