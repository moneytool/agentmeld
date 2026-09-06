"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .config import Config, load_config
from .model import Action, AssetKind, Confidence
from .registry import kind_confidence, load_registry
from .state import State

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_CONFLICT = 2
EXIT_ERROR = 3


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------

_SYMBOL = {
    Action.CREATE: "+",
    Action.UPDATE: "~",
    Action.UNCHANGED: " ",
    Action.CONFLICT: "!",
    Action.SKIP: "-",
}


def _print_plan(plan, config: Config, verbose: bool = False) -> None:
    rows = plan.mirrors if verbose else plan.changes + plan.conflicts
    if not rows:
        print("everything already in sync ({} mirror(s) checked)".format(len(plan)))
    for mirror in rows:
        print(
            "  {sym} {target:<48} {strategy:<9} {adapter}".format(
                sym=_SYMBOL[mirror.action],
                target=config.rel(mirror.target),
                strategy=str(mirror.strategy),
                adapter=mirror.adapter_id,
            )
        )
        if mirror.reason and mirror.action is Action.CONFLICT:
            print("      {}".format(mirror.reason))
    for warning in plan.warnings:
        print("  note: {}".format(warning))


def _context(args) -> "tuple":
    config = load_config(Path(args.root).resolve() if args.root else None)
    if getattr(args, "include_unverified", False):
        config.include_unverified = True
    if getattr(args, "mode", None):
        config.mode = args.mode
    registry = load_registry([config.root / d for d in config.extra_adapter_dirs])
    state = State.load(config.state_path)
    return config, registry, state


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_detect(args) -> int:
    from .detect import detect_tools

    config, registry, state = _context(args)
    found = detect_tools(registry, config, state)
    print("repo: {}".format(config.root))
    if not found:
        print("no AI tool configuration detected")
        print("run 'agentmeld init' to start a canonical {}/ tree".format(config.canonical_dir))
        return EXIT_OK
    print("detected {} tool(s):".format(len(found)))
    for adapter_id, evidence in sorted(found.items()):
        adapter = registry[adapter_id]
        print("  {:<10} {:<26} {}".format(adapter_id, adapter.name, ", ".join(evidence)))
    return EXIT_OK


def cmd_list_adapters(args) -> int:
    config, registry, _state = _context(args)
    print("{:<10} {:<26} {:<13} {}".format("id", "tool", "kind", "confidence / strategy"))
    for adapter_id, adapter in sorted(registry.items()):
        for kind, spec in adapter.kinds.items():
            confidence = kind_confidence(adapter, kind)
            flag = "" if confidence is Confidence.VERIFIED else "  (opt-in)"
            print(
                "{:<10} {:<26} {:<13} {} / {}{}".format(
                    adapter_id, adapter.name, str(kind), confidence, spec.strategy, flag
                )
            )
    print()
    print("Unverified paths are excluded from sync unless --include-unverified is passed.")
    return EXIT_OK


def cmd_sync(args) -> int:
    from .config import discover_assets
    from .linker import git_symlinks_enabled, resolve_mode
    from .planner import apply_plan, build_plan, select_adapters

    config, registry, state = _context(args)
    if not config.canonical.is_dir():
        print("no {}/ directory -- run 'agentmeld init' first".format(config.canonical_dir))
        return EXIT_ERROR

    mode = resolve_mode(config.mode, config.root)
    if mode == "copy" and config.mode == "auto":
        print("note: symlinks unavailable here, mirroring as copies instead")
    if git_symlinks_enabled(config.root) is False and mode == "link":
        print("warning: git core.symlinks=false -- links may not survive a fresh clone")

    if getattr(args, "adopt", False):
        from .watch import reconcile

        for line in reconcile(config, registry, state):
            print("  adopted: {}".format(line))

    assets = discover_assets(config)
    if not assets:
        print("no canonical assets found under {}/".format(config.canonical_dir))
        return EXIT_OK

    adapters = select_adapters(registry, config, state, args.targets or None)
    plan = build_plan(config, assets, adapters, state, mode)

    quiet = getattr(args, "quiet", False)
    if not (quiet and plan.is_clean):
        print("{} asset(s) -> {} tool(s), mode={}".format(len(assets), len(adapters), mode))
        _print_plan(plan, config, verbose=args.verbose)

    if args.check:
        if plan.conflicts:
            return EXIT_CONFLICT
        return EXIT_DRIFT if plan.changes else EXIT_OK

    if args.dry_run:
        print("\ndry run: nothing written")
        return EXIT_CONFLICT if plan.conflicts else EXIT_OK

    written = apply_plan(plan, config, state, mode)
    if not (quiet and written == 0):
        print("\nwrote {} file(s)".format(written))
    if plan.conflicts:
        print(
            "{} conflict(s) left untouched -- resolve by hand, or delete the file to "
            "let agentmeld own it".format(len(plan.conflicts))
        )
        return EXIT_CONFLICT
    return EXIT_OK


def cmd_doctor(args) -> int:
    from .config import discover_assets
    from .doctor import run_doctor

    config, registry, state = _context(args)
    return run_doctor(config, registry, state, args)


def cmd_init(args) -> int:
    from .init import run_init

    config, registry, state = _context(args)
    return run_init(config, registry, state, args)


def cmd_adopt(args) -> int:
    from .adopt import run_adopt

    config, registry, state = _context(args)
    return run_adopt(config, registry, state, args)


def cmd_watch(args) -> int:
    from .watch import run_watch

    config, registry, state = _context(args)
    return run_watch(config, registry, state, args)


def cmd_install_hooks(args) -> int:
    from .hooks import run_install_hooks

    config, registry, state = _context(args)
    return run_install_hooks(config, registry, state, args)


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentmeld",
        description="One AI context, every agent. Keep one canonical copy of your "
        "AI instructions, rules, skills, agents, commands and MCP config, "
        "mirrored into every tool's location.",
    )
    parser.add_argument("--version", action="version", version="agentmeld " + __version__)
    parser.add_argument("--root", help="repo root (default: nearest .git or .ai ancestor)")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument(
            "--include-unverified",
            action="store_true",
            help="also sync paths not confirmed against vendor documentation",
        )
        return p

    p = sub.add_parser("detect", help="show which AI tools this repo uses")
    common(p).set_defaults(func=cmd_detect)

    p = sub.add_parser("list-adapters", help="show the support matrix")
    common(p).set_defaults(func=cmd_list_adapters)

    p = sub.add_parser("init", help="create the canonical tree, adopting existing config")
    common(p)
    p.add_argument("--force", action="store_true", help="proceed on a dirty worktree")
    p.add_argument("--no-migrate", action="store_true", help="do not move existing files")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("sync", help="materialise every mirror")
    common(p)
    p.add_argument("--check", action="store_true", help="exit 1 on drift, writing nothing (CI)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true", help="list unchanged mirrors too")
    p.add_argument("-q", "--quiet", action="store_true", help="only print on change or error")
    p.add_argument("--mode", choices=["auto", "link", "copy"])
    p.add_argument("--targets", nargs="*", help="limit to these adapter ids")
    p.add_argument(
        "--adopt",
        action="store_true",
        help="first pull any new vendor files into the canonical tree",
    )
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("adopt", help="pull a vendor file into canonical, then fan out")
    common(p)
    p.add_argument("paths", nargs="+", help="vendor file(s) to adopt")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-sync", action="store_true", help="adopt without fanning out")
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("watch", help="adopt and fan out automatically as files change")
    common(p)
    p.add_argument("--interval", type=float, default=1.0, help="poll interval in seconds")
    p.add_argument("--once", action="store_true", help="one pass, for testing")
    p.add_argument("--timeout", type=float, help="stop after this many seconds")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("install-hooks", help="auto-sync on agent writes and on commit")
    common(p)
    p.add_argument(
        "--kind",
        nargs="*",
        choices=["claude", "git"],
        help="which hooks to install (default: both)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_install_hooks)

    p = sub.add_parser("doctor", help="report drift, conflicts, orphans and dropped keys")
    common(p)
    p.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or EXIT_OK)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return EXIT_ERROR
    except (OSError, ValueError, KeyError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
