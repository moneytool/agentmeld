"""Reading and rewriting vendor JSON we do not own.

Two hazards make this more than ``json.load``:

* ``.vscode/mcp.json`` is JSONC -- VS Code permits ``//`` and ``/* */`` comments,
  which :mod:`json` rejects outright.
* these files hold user settings we must not lose, so writes replace only our
  own subtree and leave every sibling key alone.

We can parse comments but cannot preserve them through a rewrite, so their
presence is reported as a warning rather than silently discarded.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

__all__ = ["load_jsonc", "dumps", "strip_comments"]


def strip_comments(text: str) -> Tuple[str, bool]:
    """Remove JSONC comments and trailing commas. Returns (json, had_comments).

    String literals are tracked so a ``//`` inside a value survives.
    """
    out = []
    had_comments = False
    i = 0
    n = len(text)
    in_string = False
    escape = False

    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                had_comments = True
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                had_comments = True
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(ch)
        i += 1

    cleaned = _drop_trailing_commas("".join(out))
    return cleaned, had_comments


def _drop_trailing_commas(text: str) -> str:
    result = []
    in_string = False
    escape = False
    for idx, ch in enumerate(text):
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            continue
        if ch == ",":
            rest = text[idx + 1 :].lstrip()
            if rest[:1] in ("}", "]"):
                continue
        result.append(ch)
    return "".join(result)


def load_jsonc(text: str) -> Tuple[Dict[str, Any], bool]:
    """Parse JSON or JSONC. Returns (data, had_comments).

    Empty input yields an empty mapping, so a missing file and an empty file
    behave the same.
    """
    if not text.strip():
        return {}, False
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        cleaned, had_comments = strip_comments(text)
        data = json.loads(cleaned)  # a genuine syntax error still raises
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object at the top level")
        return data, had_comments


def dumps(data: Dict[str, Any]) -> bytes:
    """Serialise with the 2-space indent every one of these vendors uses."""
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
