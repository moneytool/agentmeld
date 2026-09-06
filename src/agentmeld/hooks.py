"""Installing the triggers that make syncing automatic.

Hooks are preferred over the watch daemon as the default, for one blunt reason: a
daemon dies quietly and nobody notices for a week, whereas a pre-commit hook and
a CI check cannot be silently lost.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Dict, List

from .config import Config
from .model import Adapter
from .state import State
from .transform.json_merge import dumps, load_jsonc

__all__ = ["run_install_hooks", "PRE_COMMIT_MARKER"]

PRE_COMMIT_MARKER = "# agentmeld"

_PRE_COMMIT = """#!/bin/sh
{marker} -- keep AI config mirrors in sync
if command -v agentmeld >/dev/null 2>&1; then
    agentmeld sync --adopt --quiet || exit 1
    git add -A {canonical} 2>/dev/null || true
fi
""".format(marker=PRE_COMMIT_MARKER, canonical="{canonical}")

_PRE_COMMIT_CONFIG = """\
# For repos using the pre-commit framework:
#   repos:
#     - repo: local
#       hooks:
#         - id: agentmeld
#           name: agentmeld sync
#           entry: agentmeld sync --quiet
#           language: system
#           pass_filenames: false
- id: agentmeld
  name: agentmeld sync
  description: Keep AI config mirrors in sync with the canonical tree.
  entry: agentmeld sync --quiet
  language: system
  pass_filenames: false
  always_run: true
"""


def _install_claude_hook(config: Config, dry_run: bool) -> str:
    """Add a PostToolUse hook to .claude/settings.json without disturbing it."""
    path = config.root / ".claude" / "settings.json"
    document: Dict = {}
    if path.is_file():
        try:
            document, _ = load_jsonc(path.read_text(encoding="utf-8"))
        except ValueError:
            return "{}: unparseable JSON, left alone".format(config.rel(path))

    hooks = document.setdefault("hooks", {})
    post = hooks.setdefault("PostToolUse", [])
    command = "agentmeld sync --adopt --quiet"

    for group in post:
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                return "{}: already installed".format(config.rel(path))

    post.append(
        {
            "matcher": "Write|Edit|MultiEdit",
            "hooks": [{"type": "command", "command": command}],
        }
    )
    if dry_run:
        return "{}: would add PostToolUse hook".format(config.rel(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(document))
    return "{}: PostToolUse hook installed".format(config.rel(path))


def _install_git_hook(config: Config, dry_run: bool) -> str:
    hooks_dir = config.root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        return "no .git/hooks directory -- not a git repo, skipped"

    path = hooks_dir / "pre-commit"
    body = _PRE_COMMIT.format(canonical=config.canonical_dir)

    if path.is_file():
        existing = path.read_text(encoding="utf-8", errors="replace")
        if PRE_COMMIT_MARKER in existing:
            return ".git/hooks/pre-commit: already installed"
        if dry_run:
            return ".git/hooks/pre-commit: would append to existing hook"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n" + body.split("\n", 1)[1])
        return ".git/hooks/pre-commit: appended to existing hook"

    if dry_run:
        return ".git/hooks/pre-commit: would create"
    path.write_bytes((body).encode("utf-8"))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return ".git/hooks/pre-commit: created"


def _write_pre_commit_config(config: Config, dry_run: bool) -> str:
    path = config.root / ".pre-commit-hooks.yaml"
    if path.is_file():
        return "{}: already present".format(config.rel(path))
    if dry_run:
        return "{}: would create".format(config.rel(path))
    path.write_bytes((_PRE_COMMIT_CONFIG).encode("utf-8"))
    return "{}: created (for consumers using the pre-commit framework)".format(config.rel(path))


def run_install_hooks(config: Config, registry: Dict[str, Adapter], state: State, args) -> int:
    from .cli import EXIT_OK

    kinds = set(args.kind or ("claude", "git"))
    lines: List[str] = []
    if "claude" in kinds:
        lines.append(_install_claude_hook(config, args.dry_run))
    if "git" in kinds:
        lines.append(_install_git_hook(config, args.dry_run))
        lines.append(_write_pre_commit_config(config, args.dry_run))

    for line in lines:
        print("  " + line)
    if args.dry_run:
        print("dry run: nothing written")
    else:
        print("\nAlso add 'agentmeld sync --check' to CI -- it is the one trigger")
        print("that cannot be silently lost.")
    return EXIT_OK
