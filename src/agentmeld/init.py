"""Adopting an existing repo into a canonical tree.

``init`` is the one destructive command: it *moves* the AI config you already
have. So it backs everything up first, refuses to run on a dirty worktree, and
reports every move before making the next one.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .adopt import adopt_path, is_ours
from .config import CONFIG_NAME, ROOT_INSTRUCTION_CANDIDATES, Config
from .model import Adapter, AssetKind
from .state import State

__all__ = [
    "run_init",
    "candidate_paths",
    "worktree_dirty",
    "plan_canonical_instructions",
    "seed_overlays",
]

CONFIG_TEMPLATE = '''\
# agentmeld -- one AI context, every agent.
# https://github.com/moneytool/agentmeld

[agentmeld]
# The single source of truth for instructions. Left at the repo root when a file
# is already there, so no tool has to be reconfigured and nothing moves.
instructions = "{instructions}"

# Rules, skills, agents, commands, MCP config and per-tool overlays live here.
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

#: Overlap below which two instruction files are treated as saying different
#: things rather than as drifted copies of one thing. Public repos carrying both
#: AGENTS.md and CLAUDE.md are bimodal on this measure -- most pairs sit under
#: 0.1 or over 0.9, with very little between -- so the exact cut matters little.
DIVERGENCE_OVERLAP = 0.9


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


def _overlap(left: str, right: str) -> float:
    """Jaccard overlap of the word sets of two documents.

    Set overlap rather than sequence similarity on purpose: a difference-based
    ratio is biased by length, and scored the same real pairs at 0.019 where this
    scores them 0.246.
    """
    import re

    words = re.compile(r"[A-Za-z0-9_./-]+")
    a = {w.lower() for w in words.findall(left) if len(w) > 1}
    b = {w.lower() for w in words.findall(right) if len(w) > 1}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


#: Content left after removing references to the canonical file, below which a
#: file is a pointer rather than a document of its own. Matches the threshold used
#: to classify hand-written pointer files in public repos.
POINTER_RESIDUAL_BYTES = 200


def _is_pointer_only(text: str, canonical_rel: str) -> bool:
    """True when this file's only content is "read the other one".

    Someone who already wrote ``@AGENTS.md`` by hand has solved the problem the way
    we would. Treating that one line as tool-specific content to preserve would
    fold the pointer into an overlay and emit it *twice*.
    """
    import re

    name = re.escape(Path(canonical_rel).name)
    if not re.search(name, text, re.IGNORECASE):
        # No mention of the canonical file at all, so whatever this says, it is not
        # "read the other one". Without this guard a short file of real guidance
        # looks like a pointer purely because it is short.
        return False

    residual = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if re.search(name, line, re.IGNORECASE):
            continue
        if line.lstrip().startswith("#"):
            continue  # a heading is scaffolding, not content
        residual.append(line.strip())
    return len("\n".join(residual).encode("utf-8")) <= POINTER_RESIDUAL_BYTES


def plan_canonical_instructions(candidates: List[Path], config: Config):
    """Where the source of truth should live: ``(canonical_rel, rename_from)``.

    AGENTS.md, always, when the repo has any root instruction file at all. Three
    reasons, in order of weight:

    * It is the vendor-neutral standard, read directly by most tools, the most
      common AI config file in public repos, and the only one whose share grows
      with a project's popularity. An existing AGENTS.md therefore needs **no
      migration whatsoever** -- which is the common case.
    * The source of truth must not be a *vendor's* own path. If CLAUDE.md were
      canonical, Claude Code would have no mirror -- and a tool with no mirror
      cannot receive rules folded into one, so its rules would silently never
      load.
    * A repo with only CLAUDE.md is renamed to AGENTS.md rather than copied.
      CLAUDE.md comes straight back as a one-line import, so Claude Code is
      unaffected, no content changes, and the diff is a rename plus an 11-byte
      file rather than a second copy of the same document.
    """
    rels = {config.rel(p): p for p in candidates}
    if "AGENTS.md" in rels:
        return "AGENTS.md", None
    for name in ROOT_INSTRUCTION_CANDIDATES:
        if name in rels:
            return "AGENTS.md", rels[name]
    return None, None


def seed_overlays(
    candidates: List[Path],
    canonical_rel: str,
    config: Config,
    registry: Dict[str, Adapter],
) -> List[str]:
    """Preserve a sibling instruction file whose content is genuinely different.

    Two root instruction files usually mean one of two things. Either they are
    copies, in which case the second is redundant and a mirror replaces it -- or
    they say different things, because someone deliberately wrote tool-specific
    guidance. Nearly a third of such pairs in public repos are the second kind, so
    overwriting the loser would be data loss. Instead its content becomes that
    tool's overlay: still reaching that tool, no longer duplicated.
    """
    from .adopt import classify_path

    lines: List[str] = []
    try:
        canonical_text = (config.root / canonical_rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return lines

    for path in candidates:
        rel = config.rel(path)
        if rel == canonical_rel or not path.is_file():
            continue
        hit = classify_path(rel, registry)
        if hit is None:
            continue
        adapter, spec, _slug = hit
        if spec.kind is not AssetKind.INSTRUCTIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not text.strip():
            continue
        if _is_pointer_only(text, canonical_rel):
            continue  # already points at the canonical file; there is nothing to keep
        if _overlap(canonical_text, text) >= DIVERGENCE_OVERLAP:
            continue  # a copy; the mirror supersedes it
        destination = config.overlays_dir / "{}.md".format(adapter.id)
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(text.strip("\n").encode("utf-8") + b"\n")
        lines.append(
            "{} differs from {} -- kept as {} so it still reaches {}".format(
                rel, canonical_rel, config.rel(destination), adapter.name
            )
        )
    return lines


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

    # An existing root instruction file becomes the source of truth where it is.
    keep_in_place, rename_from = (
        plan_canonical_instructions(candidates, config) if migrate else (None, None)
    )
    if keep_in_place:
        config.instructions = keep_in_place

    if migrate and candidates:
        backup = _backup(candidates, config)
        print("backed up {} file(s) to {}".format(len(candidates), config.rel(backup)))
        if rename_from is not None:
            import os as _os

            destination = config.root / keep_in_place
            _os.replace(str(rename_from), str(destination))
            candidates = [p for p in candidates if p != rename_from] + [destination]
            print(
                "  {} -> {} (renamed; it comes back as a one-line import)".format(
                    config.rel(rename_from), keep_in_place
                )
            )
        if keep_in_place:
            print("  {} is the source of truth".format(keep_in_place))
            for line in seed_overlays(candidates, keep_in_place, config, registry):
                print("  " + line)
        for path in _pick_instructions(candidates, config):
            if keep_in_place and _is_instructions(path, config, registry):
                # One instruction file is already canonical. Adopting another
                # would create a second source of truth -- and its content is
                # either a duplicate (a mirror replaces it) or divergent (already
                # preserved as an overlay just above).
                continue
            line = adopt_path(path, config, registry, state, dry_run=False)
            if line:
                print("  " + line)
        for line in _clear_superseded(candidates, config, registry, state):
            print("  " + line)

    config.config_path.write_bytes((CONFIG_TEMPLATE.format(
            instructions=config.instructions_rel,
            canonical_dir=config.canonical_dir,
            mode=config.mode,
            git_policy=config.git_policy,
            include_unverified=str(config.include_unverified).lower(),
        )).encode("utf-8"))
    print("wrote {}".format(config.rel(config.config_path)))

    if not keep_in_place and not (config.canonical / "instructions.md").exists():
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


def _is_instructions(path: Path, config: Config, registry: Dict[str, Adapter]) -> bool:
    from .adopt import classify_path

    hit = classify_path(config.rel(path), registry)
    return hit is not None and hit[1].kind is AssetKind.INSTRUCTIONS


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
        if spec.kind is AssetKind.INSTRUCTIONS:
            # Instructions may be canonical at the repo root rather than inside the
            # canonical tree, so ask the config where the source of truth is.
            destination = config.instructions_path
            if config.rel(path) == config.instructions_rel:
                continue  # this *is* the source of truth
        else:
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
