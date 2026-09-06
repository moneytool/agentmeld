"""Adopting an existing repo into a canonical tree.

``init`` is the one destructive command: it *moves* the AI config you already
have. So it backs everything up first, refuses to run on a dirty worktree, and
reports every move before making the next one.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from .adopt import adopt_path, is_ours
from .config import CONFIG_NAME, Config
from .model import Adapter, AssetKind
from .state import State

__all__ = ["run_init", "candidate_paths", "worktree_dirty"]

CONFIG_TEMPLATE = '''\
# agentmeld -- one AI context, every agent.
# https://github.com/moneytool/agentmeld

[agentmeld]
# Where the single source of truth lives.
canonical_dir = "{canonical_dir}"

# auto: use symlinks where the filesystem allows, copies where it does not.
mode = "{mode}"

# commit: check generated mirrors in, so teammates and CI without agentmeld
#         installed still get working AI config.
# ignore: keep only {canonical_dir}/ in git and let everyone run sync themselves.
git_policy = "{git_policy}"

# Paths not confirmed against vendor documentation are skipped by default.
include_unverified = {include_unverified}

# Limit which tools to mirror to. Omit to mirror to every tool detected here.
# targets = ["claude", "copilot", "cursor"]
'''

#: Instruction files, best first. The richest existing document becomes canonical
#: and the rest become mirrors of it.
INSTRUCTION_PREFERENCE = ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md", "GEMINI.md")


def worktree_dirty(root: Path) -> bool:
    """True when git reports uncommitted changes. False if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def candidate_paths(registry: Dict[str, Adapter], config: Config) -> List[Path]:
    """Existing files that match any adapter target -- what init would migrate."""
    found: List[Path] = []
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            pattern = spec.target.replace("{slug}", "*")
            if "*" in pattern:
                found.extend(sorted(config.root.glob(pattern)))
            else:
                path = config.root / pattern
                if path.is_file():
                    found.append(path)
    unique: List[Path] = []
    seen = set()
    for path in found:
        if path not in seen and path.is_file():
            seen.add(path)
            unique.append(path)
    return unique


def _backup(paths: List[Path], config: Config) -> Path:
    from .planner import now_iso

    stamp = now_iso().replace(":", "").replace("-", "")
    destination = config.canonical / ".backup" / stamp
    for path in paths:
        rel = config.rel(path)
        copy_to = destination / rel
        copy_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(path), str(copy_to))
    return destination


def _pick_instructions(candidates: List[Path], config: Config) -> List[Path]:
    """Order instruction files so the preferred, largest one is adopted first."""
    rels = {config.rel(p): p for p in candidates}
    ordered = [rels[name] for name in INSTRUCTION_PREFERENCE if name in rels]
    others = [p for r, p in sorted(rels.items()) if p not in ordered]
    return ordered + others


def run_init(config: Config, registry: Dict[str, Adapter], state: State, args) -> int:
    from .cli import EXIT_ERROR, EXIT_OK, cmd_sync, build_parser

    if config.config_path.is_file():
        print("already initialised: {}".format(config.rel(config.config_path)))
        print("run 'agentmeld sync' instead")
        return EXIT_OK

    from .detect import detect_tools

    state.remember_tools(detect_tools(registry, config, state))

    migrate = not args.no_migrate
    candidates = [
        p for p in candidate_paths(registry, config) if not is_ours(p, config.rel(p), state)
    ]

    if migrate and candidates and worktree_dirty(config.root) and not args.force:
        print("refusing to migrate with uncommitted changes -- commit first, or pass --force")
        print("would move {} file(s):".format(len(candidates)))
        for path in candidates:
            print("    {}".format(config.rel(path)))
        return EXIT_ERROR

    print("repo: {}".format(config.root))
    if args.dry_run:
        print("would create {}/ and migrate {} file(s):".format(config.canonical_dir, len(candidates)))
        for path in _pick_instructions(candidates, config):
            print("    {}".format(config.rel(path)))
        return EXIT_OK

    config.canonical.mkdir(parents=True, exist_ok=True)

    if migrate and candidates:
        backup = _backup(candidates, config)
        print("backed up {} file(s) to {}".format(len(candidates), config.rel(backup)))
        for path in _pick_instructions(candidates, config):
            line = adopt_path(path, config, registry, state, dry_run=False)
            if line:
                print("  " + line)
        for line in _clear_superseded(candidates, config, registry, state):
            print("  " + line)

    config.config_path.write_bytes((CONFIG_TEMPLATE.format(
            canonical_dir=config.canonical_dir,
            mode=config.mode,
            git_policy=config.git_policy,
            include_unverified=str(config.include_unverified).lower(),
        )).encode("utf-8"))
    print("wrote {}".format(config.rel(config.config_path)))

    if not (config.canonical / "instructions.md").exists():
        (config.canonical / "instructions.md").write_bytes(
            (
                "# Project instructions\n\n"
                "How agents should work in this repo. Every AI tool reads this file,\n"
                "through the mirrors agentmeld maintains.\n"
            ).encode("utf-8")
        )
        print("wrote {}/instructions.md (starter)".format(config.canonical_dir))

    if config.git_policy == "ignore":
        _add_gitignore(config, registry)

    state.save(config.state_path)

    print("\nsyncing:")
    sync_args = build_parser().parse_args(["sync"])
    sync_args.root = str(config.root)
    sync_args.include_unverified = config.include_unverified
    return cmd_sync(sync_args)


def _clear_superseded(candidates, config: Config, registry, state: State) -> List[str]:
    """Remove originals whose content is now canonical, so mirrors can take over.

    Only reached after the backup, and only for files whose canonical counterpart
    exists -- otherwise a second instruction file would sit there unmanaged and
    every sync would report it as a conflict forever.
    """
    from .adopt import canonical_dest, classify_path

    lines = []
    for path in candidates:
        if not path.is_file():
            continue
        hit = classify_path(config.rel(path), registry)
        if hit is None:
            continue
        _adapter, spec, slug = hit
        if spec.strategy.value == "merge":
            continue  # shared config; sync merges into it rather than replacing it
        destination = canonical_dest(config, spec.kind, slug)
        if not destination.exists():
            continue
        path.unlink()
        lines.append(
            "{}: superseded by {} (backed up); a mirror will replace it".format(
                config.rel(path), config.rel(destination)
            )
        )
    return lines


def _add_gitignore(config: Config, registry: Dict[str, Adapter]) -> None:
    lines = {"# agentmeld-managed mirrors (git_policy = \"ignore\")"}
    entries = []
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            entry = spec.target.replace("{slug}", "*")
            if entry not in lines:
                lines.add(entry)
                entries.append(entry)
    path = config.root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    additions = [e for e in entries if e not in existing]
    if not additions:
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n# agentmeld-managed mirrors\n")
        for entry in sorted(additions):
            handle.write(entry + "\n")
    print("appended {} pattern(s) to .gitignore".format(len(additions)))
