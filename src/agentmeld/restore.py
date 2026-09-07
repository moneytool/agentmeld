"""Getting back out again.

The headline action moves people's files, so there has to be a supported way
back. Without one, "try it on your repo" is a bigger ask than it should be, and
the honest answer to "what if I hate it?" was previously "copy files out of
.ai/.backup/ by hand and delete the symlinks yourself".

Two modes:

* **eject** (default) -- turn every symlinked mirror into a real file and stop
  managing the repo. Every tool keeps working exactly as it does now; agentmeld
  simply stops being involved.
* **--from-backup** -- put the original files back as they were before ``init``,
  and remove the mirrors that did not exist beforehand.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config
from .model import Adapter, Strategy
from .state import State

__all__ = ["run_restore", "latest_backup", "list_backups"]


def list_backups(config: Config) -> List[Path]:
    root = config.canonical / ".backup"
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)


def latest_backup(config: Config) -> Optional[Path]:
    backups = list_backups(config)
    return backups[-1] if backups else None


def _materialise(path: Path) -> Tuple[bool, str]:
    """Replace a symlink with a real copy of what it points at.

    Directory symlinks (skills) are copied as directories, so sidecars come too.
    """
    if not path.is_symlink():
        return False, ""
    try:
        target = path.resolve()
    except OSError:
        return False, "broken symlink"
    if not target.exists():
        return False, "broken symlink"

    if target.is_dir():
        path.unlink()
        shutil.copytree(str(target), str(path))
        return True, "directory"
    data = target.read_bytes()
    path.unlink()
    path.write_bytes(data)
    return True, "file"


def _remove_hooks(config: Config, dry_run: bool) -> List[str]:
    """Undo install-hooks, touching only the entries we added."""
    from .hooks import MANAGED_HOOK_COMMANDS, PRE_COMMIT_END, PRE_COMMIT_MARKER
    from .transform.json_merge import dumps, load_jsonc

    lines: List[str] = []

    settings = config.root / ".claude" / "settings.json"
    if settings.is_file():
        try:
            document, _ = load_jsonc(settings.read_text(encoding="utf-8"))
        except ValueError:
            document = {}
        hooks = document.get("hooks") or {}
        post = hooks.get("PostToolUse") or []
        # Exact match only. Searching for "agentmeld" anywhere in a command would
        # also delete a hook the user wrote that happens to call agentmeld.
        kept = [
            group
            for group in post
            if not any(
                (h.get("command") or "").strip() in MANAGED_HOOK_COMMANDS
                for h in group.get("hooks", [])
            )
        ]
        if len(kept) != len(post):
            if not dry_run:
                if kept:
                    hooks["PostToolUse"] = kept
                else:
                    hooks.pop("PostToolUse", None)
                if hooks:
                    document["hooks"] = hooks
                else:
                    document.pop("hooks", None)
                settings.write_bytes(dumps(document))
            lines.append("{}: removed the agentmeld hook".format(config.rel(settings)))

    pre_commit = config.root / ".git" / "hooks" / "pre-commit"
    if pre_commit.is_file():
        text = pre_commit.read_text(encoding="utf-8", errors="replace")
        stripped = _strip_hook_block(text)
        if stripped is not None:
            if not dry_run:
                if stripped.strip() in ("", "#!/bin/sh"):
                    pre_commit.unlink()
                else:
                    pre_commit.write_bytes(stripped.encode("utf-8"))
            lines.append(".git/hooks/pre-commit: removed the agentmeld block")

    return lines


def _strip_hook_block(text):
    """Remove our block from a pre-commit hook, or return None if absent.

    Current hooks are delimited by begin/end markers, so removal is exact and a
    user's own additions below ours survive. Hooks written by 0.1.0 had only an
    opening marker, so those fall back to dropping the shell ``if`` block it
    introduced.
    """
    from .hooks import PRE_COMMIT_END, PRE_COMMIT_MARKER

    lines = text.splitlines(True)

    if any(PRE_COMMIT_MARKER in line for line in lines):
        kept, skipping = [], False
        for line in lines:
            if PRE_COMMIT_MARKER in line:
                skipping = True
                continue
            if skipping:
                if PRE_COMMIT_END in line:
                    skipping = False
                continue
            kept.append(line)
        return "".join(kept)

    if any("# agentmeld --" in line for line in lines):  # 0.1.0 layout
        kept, skipping = [], False
        for line in lines:
            if "# agentmeld --" in line:
                skipping = True
                continue
            if skipping:
                if line.startswith("fi"):
                    skipping = False
                continue
            kept.append(line)
        return "".join(kept)

    return None


def _restore_from_backup(config: Config, backup: Path, state: State, dry_run: bool) -> List[str]:
    lines = []
    restored = set()
    for source in sorted(backup.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(backup)
        destination = config.root / rel
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_symlink():
                destination.unlink()
            shutil.copy2(str(source), str(destination))
        restored.add(rel.as_posix())
        lines.append("restored {}".format(rel.as_posix()))

    # Anything we created that was not there before goes away again.
    for managed in state.managed_paths():
        if managed in restored:
            continue
        path = config.root / managed
        if not (path.exists() or path.is_symlink()):
            continue
        entry = state.get(managed)
        if entry is not None and entry.strategy == str(Strategy.MERGE):
            lines.append("left {} alone (shared config you also edit)".format(managed))
            continue
        if not dry_run:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(str(path))
        lines.append("removed {}".format(managed))
    return lines


def run_restore(config: Config, registry: Dict[str, Adapter], state: State, args) -> int:
    from .cli import EXIT_ERROR, EXIT_OK

    if not config.canonical.is_dir():
        print("nothing to restore: no {}/ directory".format(config.canonical_dir))
        return EXIT_ERROR

    dry_run = args.dry_run
    lines: List[str] = []

    if args.from_backup is not None:
        backup = (
            config.canonical / ".backup" / args.from_backup
            if args.from_backup
            else latest_backup(config)
        )
        if backup is None or not backup.is_dir():
            available = [p.name for p in list_backups(config)]
            print("no such backup. available: {}".format(", ".join(available) or "none"))
            return EXIT_ERROR
        print("restoring from {}".format(config.rel(backup)))
        lines.extend(_restore_from_backup(config, backup, state, dry_run))
    else:
        for managed in state.managed_paths():
            path = config.root / managed
            if dry_run:
                if path.is_symlink():
                    lines.append("would turn {} into a real file".format(managed))
                continue
            changed, kind = _materialise(path)
            if changed:
                lines.append("{} is now a real {}".format(managed, kind))

    if not args.keep_hooks:
        lines.extend(_remove_hooks(config, dry_run))

    if not dry_run:
        if config.state_path.is_file():
            config.state_path.unlink()
        lines.append("removed {}".format(config.rel(config.state_path)))

    for line in lines:
        print("  " + line)

    if dry_run:
        print("\ndry run: nothing written")
        return EXIT_OK

    print(
        "\nagentmeld no longer manages this repo. Your {}/ tree is still there --\n"
        "delete it by hand if you want it gone.".format(config.canonical_dir)
    )
    return EXIT_OK
