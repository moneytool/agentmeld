"""Diagnostics: what is drifting, what is stuck, and what got dropped in translation.

The last of those matters most. Every vendor accepts a different subset of the
canonical vocabulary, so mirroring inevitably loses information -- and losing it
*silently* is how people stop trusting a tool like this. Doctor names every key
that did not survive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .config import Config, discover_assets
from .detect import detect_tools
from .model import Action, Adapter, AssetKind, Confidence, Strategy
from .registry import kind_confidence
from .state import State
from .transform.frontmatter import CANONICAL_VOCAB

__all__ = ["run_doctor"]


def _heading(text: str) -> None:
    print("\n{}".format(text))
    print("-" * len(text))


def run_doctor(config: Config, registry: Dict[str, Adapter], state: State, args) -> int:
    from .cli import EXIT_CONFLICT, EXIT_DRIFT, EXIT_OK
    from .linker import git_symlinks_enabled, probe_symlink_support, resolve_mode
    from .planner import build_plan, select_adapters

    _heading("environment")
    print("repo             {}".format(config.root))
    print("canonical        {}/".format(config.canonical_dir))
    if not config.canonical.is_dir():
        print("\nno canonical tree yet -- run 'agentmeld init'")
        return EXIT_OK
    mode = resolve_mode(config.mode, config.root)
    print("mode             {} (configured: {})".format(mode, config.mode))
    print("symlinks usable  {}".format(probe_symlink_support(config.root)))
    core = git_symlinks_enabled(config.root)
    print("git core.symlinks {}".format("unset" if core is None else core))
    print("git policy       {}".format(config.git_policy))

    assets = discover_assets(config)
    _heading("canonical assets")
    if not assets:
        print("none found under {}/".format(config.canonical_dir))
    counts: Dict[AssetKind, int] = {}
    for asset in assets:
        counts[asset.kind] = counts.get(asset.kind, 0) + 1
    for kind in AssetKind:
        if counts.get(kind):
            print("{:<14} {}".format(str(kind), counts[kind]))

    _heading("tools")
    detected = detect_tools(registry, config, state)
    adapters = select_adapters(registry, config, state, None)
    for adapter in adapters:
        evidence = detected.get(adapter.id)
        why = ", ".join(evidence) if evidence else "recorded in state / baseline"
        print("{:<10} {:<26} {}".format(adapter.id, adapter.name, why))

    gated = [
        "{}/{}".format(a.id, k)
        for a in registry.values()
        for k in a.kinds
        if kind_confidence(a, k) is Confidence.UNVERIFIED
    ]
    if gated and not config.include_unverified:
        print("\n{} unverified path(s) skipped: {}".format(len(gated), ", ".join(sorted(gated))))
        print("pass --include-unverified to sync them anyway")

    plan = build_plan(config, assets, adapters, state, mode)

    _heading("drift")
    if plan.is_clean:
        print("all {} mirror(s) up to date".format(len(plan)))
    else:
        for mirror in plan.changes:
            print("{:<9} {}".format(str(mirror.action), config.rel(mirror.target)))

    if plan.conflicts:
        _heading("conflicts")
        for mirror in plan.conflicts:
            print("{}".format(config.rel(mirror.target)))
            print("    {}".format(mirror.reason))

    inert = _inert_rules(assets)
    if inert:
        _heading("rules that can never load")
        for line in inert:
            print(line)

    orphans = _orphans(config, state)
    if orphans:
        _heading("orphans")
        for line in orphans:
            print(line)

    dropped = _dropped_keys(config, assets, adapters)
    if dropped:
        _heading("dropped in translation")
        for line in dropped:
            print(line)

    if plan.warnings:
        _heading("notes")
        for warning in plan.warnings:
            print(warning)

    if plan.conflicts:
        return EXIT_CONFLICT
    return EXIT_DRIFT if plan.changes else EXIT_OK


def _inert_rules(assets) -> List[str]:
    """Rules with no activation path at all.

    A rule loads when a glob matches the file being edited, when it is marked
    always, or -- in tools that decide by relevance -- when its description gives
    the agent something to judge. With none of the three, nothing can trigger it:
    the file sits in the repo looking like configuration and is never read.

    Measured at 21.4% of 1,001 rule files sampled from 120 public repositories,
    so this is a common mistake rather than a hypothetical one -- and it is
    invisible without a check like this, because the file looks perfectly fine.
    """
    lines = []
    for asset in assets:
        if asset.kind is not AssetKind.RULE:
            continue
        front = asset.frontmatter
        globs = front.get("globs")
        has_globs = bool(globs) if not isinstance(globs, str) else bool(globs.strip())
        if has_globs or front.get("always") or str(front.get("description", "")).strip():
            continue
        lines.append("{}".format(asset.path.name))
        lines.append(
            "    no globs, always is not set, no description -- nothing will load this"
        )
        lines.append(
            "    fix: add globs, set always: true, or write a description"
        )
    return lines


def _orphans(config: Config, state: State) -> List[str]:
    """Managed paths whose file or whose canonical source has vanished."""
    lines = []
    for rel, entry in sorted(state.entries.items()):
        target = config.root / rel
        if not (target.exists() or target.is_symlink()):
            lines.append("{} -- managed but missing (sync will recreate it)".format(rel))
            continue
        if entry.source:
            source = config.root / entry.source
            if not source.exists():
                lines.append(
                    "{} -- source {} is gone (sync will remove the mirror)".format(
                        rel, entry.source
                    )
                )
    return lines


def _dropped_keys(config: Config, assets, adapters) -> List[str]:
    """Canonical frontmatter keys each vendor cannot express."""
    lines = []
    for adapter in adapters:
        for asset in assets:
            spec = adapter.spec(asset.kind)
            if spec is None or spec.strategy is not Strategy.GENERATE:
                continue
            present = set(asset.frontmatter) & CANONICAL_VOCAB
            kept = {k for k in present if spec.frontmatter.get(k) not in (None, "__drop__")}
            lost = sorted(present - kept)
            if lost:
                lines.append(
                    "{}: {} -> {} drops {}".format(
                        adapter.id, config.rel(asset.path), spec.render_target(asset.slug),
                        ", ".join(lost),
                    )
                )
    return lines
