"""Gemini CLI custom commands -- the case that proves symlinks cannot suffice.

Gemini reads ``.gemini/commands/<name>.toml`` with a ``prompt`` key. A Markdown
command file cannot be symlinked into that: the container format is different,
not just the field names. So this transformer exists, and with it the whole
``generate`` strategy.

Verified against google-gemini/gemini-cli ``docs/cli/custom-commands.md``.
"""

from __future__ import annotations

from ..model import Asset, KindSpec
from . import GenContext, header_line, register

__all__ = ["gemini_command", "toml_basic_string", "toml_multiline_string"]


def toml_basic_string(value: str) -> str:
    """Quote a TOML basic string, escaping what the spec requires."""
    out = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return '"{}"'.format(out)


def toml_multiline_string(value: str) -> str:
    """Emit a TOML multi-line basic string.

    Backslashes are escaped so prompt bodies containing e.g. ``\\d+`` survive,
    and any literal ``\"\"\"`` is broken up so it cannot terminate the block early.
    """
    out = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if out.endswith('"'):
        out = out[:-1] + '\\"'
    return '"""\n{}\n"""'.format(out)


@register("gemini_command")
def gemini_command(asset: Asset, spec: KindSpec, ctx: GenContext, existing=None) -> bytes:
    lines = [header_line(ctx, comment="#", close="").rstrip() + "\n"]
    description = asset.frontmatter.get("description")
    if description:
        lines.append("description = {}\n".format(toml_basic_string(str(description))))
    lines.append("prompt = {}\n".format(toml_multiline_string(asset.body.strip("\n"))))
    return "".join(lines).encode("utf-8")
