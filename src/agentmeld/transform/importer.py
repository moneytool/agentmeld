"""Building an import mirror: a file that points at the canonical one.

Where a vendor can be told to read another file, that beats both a symlink and a
copy. A symlink fails silently in four common situations -- Windows without
Developer Mode, ``core.symlinks=false``, archive or container builds that drop
links, and non-POSIX filesystems that serialise the link into the file body -- and
in every one of them the tool reads the pointer text as instructions and quietly
follows nothing. An import is a real file with real text, so none of that
applies, and it stays legible to a human reading the repo.

Two shapes come out of here:

* **bare** -- exactly the import line, nothing else. This is what the ecosystem
  already writes by hand (21 of 30 sampled pointer files are literally
  ``@AGENTS.md``), and adding a provenance header to an 11-byte file would make
  agentmeld's output *less* idiomatic than what people do without it. With no
  header, ownership is established from state, the same way a copy-mode mirror is.
* **with content** -- the import line plus a per-tool overlay and/or folded-in
  rules, under a provenance header that says where to edit instead.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from ..model import Asset, KindSpec
from . import GenContext, header_line
from .aggregate import rules_sections

__all__ = ["render_import", "overlay_marker", "OVERLAY_TOKEN", "split_overlay"]

#: Marks where a tool-specific overlay begins inside an import mirror. Content
#: below it belongs to one tool and is deliberately *not* shared -- which is what
#: makes it safe for Claude Code's ``#`` append to land here.
OVERLAY_TOKEN = "agentmeld:overlay"


def overlay_marker(source: str) -> str:
    return "<!-- {tok} source={src} -- tool-specific; not shared with other tools -->".format(
        tok=OVERLAY_TOKEN, src=source
    )


def render_import(
    spec: KindSpec,
    canonical_rel: str,
    ctx: GenContext,
    overlay: Optional[str] = None,
    overlay_source: str = "",
    rules: Sequence[Asset] = (),
) -> bytes:
    """The bytes of an import mirror."""
    line = spec.render_import(canonical_rel)
    overlay_body = (overlay or "").strip("\n")
    rule_parts = rules_sections(rules)

    if not overlay_body and not rule_parts:
        return (line + "\n").encode("utf-8")

    parts: List[str] = [line, "", header_line(ctx).rstrip("\n"), ""]
    if rule_parts:
        parts.extend(rule_parts)
    if overlay_body:
        parts.extend([overlay_marker(overlay_source), "", overlay_body, ""])

    text = "\n".join(parts).rstrip("\n") + "\n"
    return text.encode("utf-8")


def split_overlay(text: str) -> Optional[str]:
    """The overlay portion of an existing import mirror, or ``None``.

    Used by ``adopt``: a hand edit below the overlay marker is tool-specific
    content, and belongs back in that tool's overlay file rather than in the
    shared source -- which is exactly where Claude Code's ``#`` shortcut writes.
    """
    marker_at = None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if OVERLAY_TOKEN in line:
            marker_at = index
            break
    if marker_at is None:
        return None
    return "\n".join(lines[marker_at + 1 :]).strip("\n") or ""
