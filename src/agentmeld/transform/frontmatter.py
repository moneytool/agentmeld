"""YAML frontmatter parsing and deterministic re-emission.

Determinism matters more than it looks: ``sync`` must be idempotent, so running
it twice has to produce byte-identical output, and ``--check`` compares bytes to
decide whether CI fails. Anything non-deterministic here (dict ordering, quoting
drift) would show up as phantom drift.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

import yaml

__all__ = ["CANONICAL_VOCAB", "split", "render", "map_keys", "DROP"]

DELIM = "---"

#: Frontmatter keys agentmeld considers its own. Anything here that an adapter
#: does not explicitly map is dropped rather than leaked into a vendor file that
#: never asked for it. Keys *outside* this set are the user's own and pass
#: through untouched -- not our vocabulary, not our business.
CANONICAL_VOCAB = frozenset(
    {
        "name",
        "description",
        "globs",
        "always",
        "model",
        "tools",
        "allowed-tools",
        "argument-hint",
        "license",
        "version",
    }
)

# The one directive that is a bare word; everything else is the mini-syntax
# documented on :func:`map_keys`.
DROP = "__drop__"


class FrontmatterError(ValueError):
    """Raised when a file opens a frontmatter block it never closes."""


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith("﻿") else text


def split(text: str) -> Tuple[Dict[str, Any], str]:
    """Split ``text`` into (frontmatter mapping, body).

    Returns an empty mapping when there is no frontmatter block. CRLF input is
    normalised to LF so Windows checkouts do not produce different output than
    POSIX ones.
    """
    text = _strip_bom(text).replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith(DELIM + "\n"):
        return {}, text

    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == DELIM:
            raw = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            loaded = yaml.safe_load(raw) if raw.strip() else {}
            if loaded is None:
                loaded = {}
            if not isinstance(loaded, dict):
                raise FrontmatterError(
                    "frontmatter must be a mapping, got {}".format(type(loaded).__name__)
                )
            return loaded, body.lstrip("\n")
    raise FrontmatterError("unterminated frontmatter block (opened with '---', never closed)")


def _dump(data: Mapping[str, Any]) -> str:
    """Emit YAML with insertion order preserved and no line wrapping."""
    return yaml.safe_dump(
        dict(data),
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
    )


def render(frontmatter: Mapping[str, Any], body: str) -> str:
    """Rebuild a markdown document, guaranteeing exactly one trailing newline."""
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    tail = body + "\n" if body else ""
    if not frontmatter:
        return tail
    return "{d}\n{y}{d}\n\n{b}".format(d=DELIM, y=_dump(frontmatter), b=tail)


def map_keys(
    canonical: Mapping[str, Any],
    mapping: Mapping[str, str],
    defaults: Mapping[str, Any] = (),  # type: ignore[assignment]
) -> Dict[str, Any]:
    """Translate canonical frontmatter into one vendor's vocabulary.

    ``mapping`` is canonical key -> directive, using this mini-syntax:

    ==========================  ====================================================
    ``"__drop__"``              omit the key (the vendor has no equivalent)
    ``"applyTo"``               rename to ``applyTo``
    ``"applyTo:comma"``         rename, joining a list into ``"a, b"``
    ``"applyTo!**"``            if the value is truthy, set ``applyTo`` to ``"**"``
    ==========================  ====================================================

    The ``!`` form exists for vendors that express "always apply" as a
    match-everything glob rather than a boolean, and it is applied *after* plain
    renames so an always-on rule wins over a narrower glob list.

    Keys not in ``mapping`` are dropped when they belong to
    :data:`CANONICAL_VOCAB` (our vocabulary, which this vendor did not ask for)
    and passed through otherwise (the user's own keys, not ours to judge).

    ``defaults`` are vendor keys forced onto the result, and never override a
    value we derived.
    """
    out: Dict[str, Any] = {}
    flags: Dict[str, Any] = {}

    for key, value in canonical.items():
        directive = mapping.get(key)
        if directive is None:
            if key not in CANONICAL_VOCAB:
                out[key] = value  # the user's own key; leave it alone
            continue
        if directive == DROP:
            continue
        if "!" in directive:
            vendor_key, _, literal = directive.partition("!")
            if value:
                flags[vendor_key] = _coerce(literal)
            continue
        if directive.endswith(":comma"):
            out[directive[: -len(":comma")]] = _comma(value)
            continue
        out[directive] = value

    out.update(flags)  # truthy flags win over plain renames

    for key, value in dict(defaults or {}).items():
        out.setdefault(key, value)
    return out


def _coerce(literal: str) -> Any:
    """Interpret a directive literal, so ``!true`` is a bool and ``!**`` a string."""
    lowered = literal.strip().lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    return literal


def _comma(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)
