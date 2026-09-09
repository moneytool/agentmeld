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

    corrupt = _serialised_symlinks(config, state, registry)
    if corrupt:
        _heading("broken pointer files")
        for line in corrupt:
            print(line)

    portability = _symlink_portability(config, plan, mode)
    if portability:
        _heading("portability")
        for line in portability:
            print(line)

    ignored = _silently_ignored(config)
    if ignored:
        _heading("files the tool will ignore")
        for line in ignored:
            print(line)

    inert = _inert_rules(assets)
    if inert:
        _heading("rules that never load automatically")
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


#: CIFS/SMB writes a symlink as a regular file whose body starts with this.
_XSYM = "XSym"


def _looks_like_a_serialised_link(text: str) -> bool:
    """True when a regular file's body is really a symlink that lost its type.

    Three shapes, all seen in public repos:

    * ``XSym\n0009\n<md5>\ntarget`` -- CIFS/SMB, padded to 1067 bytes with NULs.
    * a body that is nothing but a path to another config file, with no markup --
      a POSIX symlink committed after a checkout with ``core.symlinks=false``.
    * NUL bytes near the start, which no instruction file has.

    Every one of these reads to the tool as an instruction file whose entire
    content is a filename, so it silently instructs nothing. The person who
    created it cannot see the problem: on their machine the symlink works.
    """
    if text.startswith(_XSYM):
        return True
    if "\x00" in text[:200]:
        return True
    stripped = text.strip().strip("\x00").strip()
    if not stripped or "\n" in stripped:
        return False
    if stripped.startswith("@"):
        return False  # a deliberate import, not a lost symlink
    lowered = stripped.lower()
    return lowered.endswith((".md", ".mdc", ".markdown")) and " " not in stripped


def _instruction_like_paths(config: Config, state: State, registry) -> List[Path]:
    """Every path that a tool would read as instructions or rules."""
    from .config import ROOT_INSTRUCTION_CANDIDATES

    seen: List[Path] = []
    for name in ROOT_INSTRUCTION_CANDIDATES:
        seen.append(config.root / name)
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            if spec.kind not in (AssetKind.INSTRUCTIONS, AssetKind.RULE):
                continue
            pattern = spec.target.replace("{slug}", "*")
            if "*" in pattern:
                seen.extend(sorted(config.root.glob(pattern)))
            else:
                seen.append(config.root / pattern)
    for managed in state.managed_paths():
        seen.append(config.root / managed)
    unique: List[Path] = []
    for path in seen:
        if path not in unique:
            unique.append(path)
    return unique


def _serialised_symlinks(config: Config, state: State, registry) -> List[str]:
    """Config files that are a symlink's text rather than a symlink.

    Roughly 4% of symlinked instruction mirrors in a sample of public repos are in
    this state. Nothing else reports it, and it cannot be noticed by whoever
    caused it.
    """
    lines: List[str] = []
    for path in _instruction_like_paths(config, state, registry):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > 8192:
                continue  # far too large to be a pointer
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _looks_like_a_serialised_link(text):
            continue
        preview = text.strip().splitlines()[0][:48] if text.strip() else "(empty)"
        lines.append("{}".format(config.rel(path)))
        lines.append(
            "    contains a link pointer, not instructions: {!r}".format(preview)
        )
        lines.append(
            "    the tool reads this literally, so it loads nothing. Delete it and "
            "run sync -- mode=link is unsafe for this repo; imports or copies are not."
        )
    return lines


def _symlink_portability(config: Config, plan, mode: str) -> List[str]:
    """Warn before a symlink mirror becomes somebody else's silent failure."""
    from .linker import git_symlinks_enabled

    if mode != "link":
        return []
    linked = sorted(
        config.rel(m.target)
        for m in plan.mirrors
        # A skipped mirror is not written at all -- the canonical file's own adapter
        # produces one, and counting it would warn about a symlink that never exists.
        if m.strategy is Strategy.LINK and m.action is not Action.SKIP
    )
    if not linked:
        return []
    lines: List[str] = []
    if git_symlinks_enabled(config.root) is False:
        lines.append(
            "git core.symlinks=false here, so these check out as text files "
            "containing a path:"
        )
    else:
        lines.append(
            "{} mirror(s) are symlinks. They fail silently on a Windows checkout "
            "without Developer Mode, under core.symlinks=false, and on SMB/CIFS "
            "shares:".format(len(linked))
        )
    for rel in linked[:8]:
        lines.append("    {}".format(rel))
    if len(linked) > 8:
        lines.append("    ... and {} more".format(len(linked) - 8))
    lines.append(
        "where the tool supports it, strategy='import' avoids all of that; "
        "otherwise mode='copy' is safe everywhere"
    )
    return lines


def _silently_ignored(config: Config) -> List[str]:
    """Rule files sitting where their tool will not look at them."""
    lines: List[str] = []
    cursor_rules = config.root / ".cursor" / "rules"
    if cursor_rules.is_dir():
        stray = sorted(
            p for p in cursor_rules.rglob("*.md") if p.is_file() and p.suffix == ".md"
        )
        for path in stray:
            lines.append("{}".format(config.rel(path)))
            lines.append(
                "    Cursor reads only .mdc inside .cursor/rules -- a .md file here "
                "is ignored with no error"
            )
    return lines


def _inert_rules(assets) -> List[str]:
    """Rules that no automatic trigger can reach.

    A rule loads automatically when a glob matches the file being edited, when it
    is marked always, or -- in tools that decide by relevance -- when its
    description gives the agent something to judge. With none of the three, the
    only way in is an explicit mention: Cursor calls this the "Apply Manually"
    rule type, included when you @-mention it in chat.

    So this is a question, not a verdict. Some of these are deliberate; some are
    rules whose author believed they were scoped and never noticed otherwise.
    Frontmatter alone cannot tell the two apart, which is why the wording asks
    rather than accuses.

    21.4% of 1,001 rule files sampled from 120 public repositories are in this
    state -- high enough that the ones written by accident are worth surfacing.
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
            "    no globs, no always, no description -- loads only if you @-mention it"
        )
        lines.append(
            "    if that was not intended: add globs, set always: true, or a description"
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
