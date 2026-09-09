"""Folding rules into a single instructions file.

Claude Code, Gemini CLI and AGENTS.md read one document; they have no per-file
rule mechanism. Their rules have to land somewhere, so each becomes a section
with its scope stated in prose -- the glob cannot be enforced by these tools, but
saying "applies to src/**" still tells the agent when the section is relevant.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from ..model import Asset
from . import GenContext, header_line

__all__ = ["aggregate", "rules_sections"]

RULES_HEADING = "## Rules"


def _scope_line(asset: Asset) -> str:
    if asset.frontmatter.get("always"):
        return "_Applies to: the whole repository._"
    globs = asset.frontmatter.get("globs")
    if isinstance(globs, (list, tuple)) and globs:
        return "_Applies to: {}._".format(", ".join(str(g) for g in globs))
    if isinstance(globs, str) and globs.strip():
        return "_Applies to: {}._".format(globs.strip())
    return ""


def rules_sections(rules: Sequence[Asset]) -> List[str]:
    """The ``## Rules`` block: one section per rule, scope stated in prose.

    Shared with the ``import`` strategy, which appends these below an import line
    instead of below a copy of the instructions body.
    """
    if not rules:
        return []
    parts: List[str] = [RULES_HEADING, ""]
    for rule in sorted(rules, key=lambda a: a.slug):
        title = rule.frontmatter.get("name") or rule.slug
        parts.append("### {}".format(title))
        description = rule.frontmatter.get("description")
        if description:
            parts.append("")
            parts.append(str(description))
        scope = _scope_line(rule)
        if scope:
            parts.append("")
            parts.append(scope)
        rule_body = rule.body.strip("\n")
        if rule_body:
            parts.extend(["", rule_body])
        parts.append("")
    return parts


def aggregate(
    instructions: Asset,
    rules: Sequence[Asset],
    ctx: GenContext,
    overlay: str = "",
    overlay_source: str = "",
) -> bytes:
    """Build one document from the instructions, every rule, and any overlay.

    The overlay lands last and under its own marker, so a tool that appends to
    its own instruction file (Claude Code's ``#`` shortcut) writes into the
    tool-specific region rather than into content shared with other tools.
    """
    from .importer import overlay_marker

    parts: List[str] = [header_line(ctx).rstrip("\n"), ""]

    body = instructions.body.strip("\n") if instructions is not None else ""
    if body:
        parts.extend([body, ""])

    parts.extend(rules_sections(rules))

    overlay_body = (overlay or "").strip("\n")
    if overlay_body:
        parts.extend([overlay_marker(overlay_source), "", overlay_body, ""])

    text = "\n".join(parts).rstrip("\n") + "\n"
    return text.encode("utf-8")
