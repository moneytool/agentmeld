"""Watch mode: report -- and optionally fan out -- as files change.

**Read-only unless you pass ``--write``.** Fanning out automatically is the wrong
default. Nearly a third of repos carrying two instruction files write genuinely
different content in each, on purpose, and copying one over the other destroys
that. Worse, Claude Code's ``#`` shortcut appends to CLAUDE.md, so an eager
watcher would take a Claude-specific note and broadcast it to every other tool.

Prefer ``sync --check`` in CI: a failing check cannot be quietly lost, whereas a
daemon dies silently and nobody notices for a week.

Polling, deliberately. A ``watchdog``-style native watcher would cut latency, but
a poll of a handful of small config directories costs almost nothing, behaves the
same on all three platforms, and needs no dependency.

The hazard here is feedback: syncing *writes* files into the very directories we
watch, so a naive loop would see its own output and sync forever. Three guards:

* our own mirrors are recognised (state, symlink, or generated header) and never
  adopted;
* the snapshot is refreshed *after* we write, so self-inflicted changes are never
  compared against;
* a runaway budget stops the loop if it somehow still oscillates, rather than
  spinning silently on someone's laptop.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from .adopt import adopt_path, classify_path, is_ours
from .config import Config
from .model import Adapter
from .state import State

__all__ = ["run_watch", "watch_roots", "snapshot", "reconcile"]

#: Consecutive change-producing cycles tolerated before we assume a feedback loop.
RUNAWAY_BUDGET = 25

_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".backup", ".venv"}


def watch_roots(config: Config, registry: Dict[str, Adapter]) -> List[Path]:
    """Canonical tree plus every directory or file an adapter writes to."""
    roots: Set[Path] = {config.canonical}
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            first = spec.target.split("/")[0]
            if "{slug}" in first:
                continue
            roots.add(config.root / first)
    return sorted(r for r in roots if r.exists())


def snapshot(roots: Iterable[Path]) -> Dict[str, Tuple[float, int]]:
    """Map every watched file to (mtime, size)."""
    seen: Dict[str, Tuple[float, int]] = {}
    for root in roots:
        if root.is_file():
            try:
                stat = root.stat()
                seen[str(root)] = (stat.st_mtime, stat.st_size)
            except OSError:
                pass
            continue
        for path in root.rglob("*"):
            if any(part in _IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file() and not path.is_symlink():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            seen[str(path)] = (stat.st_mtime, stat.st_size)
    return seen


def _added(previous: Dict[str, Tuple[float, int]], current: Dict[str, Tuple[float, int]]) -> List[str]:
    return sorted(set(current) - set(previous))


def _changed(previous, current) -> bool:
    return previous != current


def reconcile(
    config: Config,
    registry: Dict[str, Adapter],
    state: State,
    dry_run: bool = False,
) -> List[str]:
    """Adopt every unmanaged vendor file that belongs in the canonical tree.

    This is a full pass over the watched locations rather than a diff, because the
    interesting case -- an agent wrote a file a moment ago -- is already on disk by
    the time anything asks us to look.
    """
    adopted: List[str] = []
    for root in watch_roots(config, registry):
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if any(part in _IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file() or path.is_symlink():
                continue
            rel = config.rel(path)
            if rel == config.canonical_dir or rel.startswith(config.canonical_dir + "/"):
                continue
            if is_ours(path, rel, state) or classify_path(rel, registry) is None:
                continue
            line = adopt_path(path, config, registry, state, dry_run=dry_run)
            if line:
                adopted.append(line)
    if adopted and not dry_run:
        state.save(config.state_path)
    return adopted


def _sync_once(config: Config, quiet: bool = True, check: bool = False) -> int:
    from .cli import build_parser, cmd_sync

    argv = ["sync", "--check"] if check else ["sync"]
    args = build_parser().parse_args(argv)
    args.root = str(config.root)
    args.include_unverified = config.include_unverified
    args.quiet = quiet
    return cmd_sync(args)


def run_watch(config: Config, registry: Dict[str, Adapter], state: State, args) -> int:
    from .cli import EXIT_ERROR, EXIT_OK

    if not config.canonical.is_dir():
        print("no {}/ directory -- run 'agentmeld init' first".format(config.canonical_dir))
        return EXIT_ERROR

    write = bool(getattr(args, "write", False))
    roots = watch_roots(config, registry)
    print(
        "watching {} location(s) every {}s -- ctrl-c to stop".format(len(roots), args.interval)
    )
    if not write:
        print(
            "report-only: changes are listed, nothing is written. Pass --write to "
            "adopt and fan out automatically -- note that doing so copies one tool's "
            "new content to every other tool, which is wrong when they differ on "
            "purpose."
        )
    for root in roots:
        print("  {}".format(config.rel(root)))

    if args.once:
        return _cycle(config, registry, state, write, quiet=False)

    previous = snapshot(roots)
    started = time.time()
    busy_cycles = 0

    while True:
        time.sleep(max(0.05, args.interval))

        current = snapshot(roots)
        if _changed(previous, current):
            _cycle(config, registry, state, write, quiet=True)

            # Refresh *after* writing, so our own output is never seen as a change.
            roots = watch_roots(config, registry)
            previous = snapshot(roots)
            busy_cycles += 1
            if busy_cycles > RUNAWAY_BUDGET:
                print(
                    "stopping: {} consecutive sync cycles suggests a feedback loop. "
                    "Run 'agentmeld doctor' to see what keeps changing.".format(busy_cycles)
                )
                return EXIT_ERROR
        else:
            previous = current
            busy_cycles = 0

        if args.timeout is not None and time.time() - started >= args.timeout:
            return EXIT_OK


def _cycle(config: Config, registry, state: State, write: bool, quiet: bool) -> int:
    """One pass: either report what would change, or adopt and fan out."""
    from .cli import EXIT_DRIFT, EXIT_OK

    if not write:
        pending = reconcile(config, registry, state, dry_run=True)
        for line in pending:
            print("  would adopt: {}".format(line))
        code = _sync_once(config, quiet=quiet, check=True)
        return EXIT_DRIFT if (pending or code == EXIT_DRIFT) else EXIT_OK

    for line in reconcile(config, registry, state):
        print("  adopted: {}".format(line))
    return _sync_once(config, quiet=quiet)


def _adopt_new(paths: List[str], config: Config, registry, state: State) -> List[str]:
    """Adopt brand-new vendor files an agent just wrote."""
    adopted = []
    for raw in paths:
        path = Path(raw)
        rel = config.rel(path)
        if rel.startswith(config.canonical_dir + "/") or rel == config.canonical_dir:
            continue
        if is_ours(path, rel, state) or classify_path(rel, registry) is None:
            continue
        line = adopt_path(path, config, registry, state, dry_run=False)
        if line:
            print("  adopted: {}".format(line))
            adopted.append(line)
    return adopted
