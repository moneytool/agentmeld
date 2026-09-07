"""Building the sync plan, and applying it.

Everything the tool would do is decided here first, as data, so ``--dry-run`` and
``--check`` are exactly the same code path as a real sync minus the writes.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .config import Config
from .detect import detect_tools
from .model import (
    Action,
    Adapter,
    Asset,
    AssetKind,
    Confidence,
    Mirror,
    Strategy,
    SyncPlan,
)
from .registry import kind_confidence
from .state import Entry, State
from .transform import GenContext, get as get_transformer, source_hash
from .transform.aggregate import aggregate

__all__ = ["select_adapters", "build_plan", "apply_plan"]


def select_adapters(
    adapters: Dict[str, Adapter],
    config: Config,
    state: State,
    explicit: Optional[Sequence[str]] = None,
) -> List[Adapter]:
    """Which adapters to sync: an explicit list, the config, or what is detected.

    A repo that has been initialised keeps syncing every tool already recorded in
    state, so removing the last ``.cursor`` file does not silently stop mirroring
    to Cursor mid-session.
    """
    wanted = list(explicit or config.targets or ())
    if wanted:
        missing = [name for name in wanted if name not in adapters]
        if missing:
            raise KeyError("unknown adapter(s): {}".format(", ".join(sorted(missing))))
        return [adapters[name] for name in wanted]

    ids = set(detect_tools(adapters, config, state))
    ids.update(entry.adapter for entry in state.entries.values())
    ids.update(state.tools)
    ids.add("agents")  # the cross-vendor baseline is always worth writing
    return [adapters[i] for i in sorted(ids) if i in adapters]


def _by_kind(assets: Sequence[Asset]) -> Dict[AssetKind, List[Asset]]:
    grouped: Dict[AssetKind, List[Asset]] = {}
    for asset in assets:
        grouped.setdefault(asset.kind, []).append(asset)
    return grouped


def _context(config: Config, asset: Optional[Asset], tool: str, extra: bytes = b"") -> GenContext:
    raw = (asset.raw or b"") if asset is not None else b""
    return GenContext(
        source=config.rel(asset.path) if asset is not None else "",
        source_hash=source_hash(raw + extra),
        tool=tool,
    )


def build_plan(
    config: Config,
    assets: Sequence[Asset],
    adapters: Sequence[Adapter],
    state: State,
    mode: str,
) -> SyncPlan:
    """Compute every intended mirror, and what would happen to it."""
    from .linker import classify

    plan = SyncPlan()
    grouped = _by_kind(assets)
    rules = grouped.get(AssetKind.RULE, [])

    for adapter in adapters:
        for kind, spec in adapter.kinds.items():
            confidence = kind_confidence(adapter, kind)
            if confidence is Confidence.UNVERIFIED and not config.include_unverified:
                plan.warnings.append(
                    "skipped {}/{}: path not confirmed against vendor docs "
                    "(--include-unverified to sync anyway)".format(adapter.id, kind)
                )
                continue

            if kind is AssetKind.INSTRUCTIONS:
                plan.mirrors.extend(
                    _plan_instructions(config, adapter, spec, grouped, rules, state, mode)
                )
                continue

            for asset in grouped.get(kind, []):
                plan.mirrors.extend(
                    _plan_asset(config, adapter, spec, asset, state, mode, plan)
                )

    _check_collisions(plan)
    _reject_canonical_targets(plan, config)
    return plan


def _plan_instructions(config, adapter, spec, grouped, rules, state, mode) -> List[Mirror]:
    from .linker import classify

    instructions = (grouped.get(AssetKind.INSTRUCTIONS) or [None])[0]
    folds_rules = spec.aggregate_rules and rules and not adapter.supports(AssetKind.RULE)

    if instructions is None and not folds_rules:
        return []

    target = config.root / spec.render_target("instructions")
    source = instructions.path if instructions is not None else config.canonical / "instructions.md"

    if folds_rules:
        extra = b"".join(sorted((r.raw or b"") for r in rules))
        ctx = _context(config, instructions, adapter.id, extra=extra)
        if instructions is None:
            ctx = GenContext(
                source=config.rel(config.canonical / "rules"),
                source_hash=source_hash(extra),
                tool=adapter.id,
            )
        mirror = Mirror(
            adapter_id=adapter.id,
            kind=AssetKind.INSTRUCTIONS,
            slug="instructions",
            source=source,
            target=target,
            strategy=Strategy.AGGREGATE,
            payload=aggregate(instructions, rules, ctx),
            reason="{} has no per-file rule mechanism; {} rule(s) folded in".format(
                adapter.name, len(rules)
            ),
        )
    else:
        mirror = Mirror(
            adapter_id=adapter.id,
            kind=AssetKind.INSTRUCTIONS,
            slug="instructions",
            source=source,
            target=target,
            strategy=spec.strategy,
            payload=None if mode == "link" else (instructions.raw or b""),
        )

    mirror.action = classify(mirror, state.get(config.rel(target)), mode, config.canonical)
    return [mirror]


def _plan_asset(config, adapter, spec, asset, state, mode, plan=None) -> List[Mirror]:
    from .linker import classify
    from .transform.mcp import has_comments

    rendered = spec.render_target(asset.slug)
    target = config.root / rendered

    # Directory-shaped assets link as a directory, so sidecars ride along.
    if asset.kind.is_directory_shaped and spec.strategy is Strategy.LINK and mode == "link":
        mirror = Mirror(
            adapter_id=adapter.id,
            kind=asset.kind,
            slug=asset.slug,
            source=asset.root,
            target=target.parent,
            strategy=Strategy.LINK,
            dir_link=True,
            reason="whole skill directory linked, so sidecars need no separate sync",
        )
        mirror.action = classify(mirror, state.get(config.rel(target.parent)), mode, config.canonical)
        return [mirror]

    mirrors: List[Mirror] = []
    payload: Optional[bytes] = None
    if spec.strategy in (Strategy.GENERATE, Strategy.MERGE):
        existing = target.read_bytes() if target.is_file() else None
        if plan is not None and spec.strategy is Strategy.MERGE and has_comments(existing):
            plan.warnings.append(
                "{}: comments in {} cannot survive a JSON rewrite and were "
                "dropped".format(adapter.id, config.rel(target))
            )
        ctx = _context(config, asset, adapter.id)
        if spec.strategy is Strategy.MERGE:
            ctx = GenContext(
                source=ctx.source,
                source_hash=ctx.source_hash,
                tool=adapter.id,
                owned=tuple(state.owned_in(config.rel(target))),
            )
        transformer = get_transformer(spec.transformer or "markdown")
        payload = transformer(asset, spec, ctx, existing)
    elif mode == "copy":
        payload = asset.raw or b""

    mirror = Mirror(
        adapter_id=adapter.id,
        kind=asset.kind,
        slug=asset.slug,
        source=asset.path,
        target=target,
        strategy=spec.strategy,
        payload=payload,
    )
    mirror.action = classify(mirror, state.get(config.rel(target)), mode, config.canonical)
    mirrors.append(mirror)

    # copy mode has to carry each sidecar itself
    if asset.kind.is_directory_shaped and mode == "copy":
        for sidecar in asset.sidecars:
            rel = sidecar.relative_to(asset.root)
            side_target = target.parent / rel
            side = Mirror(
                adapter_id=adapter.id,
                kind=asset.kind,
                slug="{}/{}".format(asset.slug, rel.as_posix()),
                source=sidecar,
                target=side_target,
                strategy=Strategy.LINK,
                payload=sidecar.read_bytes(),
            )
            side.action = classify(side, state.get(config.rel(side_target)), mode, config.canonical)
            mirrors.append(side)

    return mirrors


def _reject_canonical_targets(plan: SyncPlan, config: Config) -> None:
    """Refuse to write a mirror into the canonical tree.

    Nothing should generate such a target, but the consequence of one slipping
    through is overwriting the source of truth, so it is checked rather than
    assumed.
    """
    kept = []
    for mirror in plan.mirrors:
        if config.inside_canonical(mirror.target):
            plan.warnings.append(
                "refused: {} targets the canonical tree ({}/) -- skipped".format(
                    mirror.adapter_id, config.canonical_dir
                )
            )
            continue
        kept.append(mirror)
    plan.mirrors[:] = kept


def _check_collisions(plan: SyncPlan) -> None:
    """Two adapters writing one path would fight; say so instead of racing."""
    seen: Dict[Path, Mirror] = {}
    for mirror in plan.mirrors:
        previous = seen.get(mirror.target)
        if previous is not None and previous.payload != mirror.payload:
            plan.warnings.append(
                "collision: {} and {} both write {} with different content".format(
                    previous.adapter_id, mirror.adapter_id, mirror.target
                )
            )
        seen.setdefault(mirror.target, mirror)


def apply_plan(plan: SyncPlan, config: Config, state: State, mode: str) -> int:
    """Write every non-conflicting change and update state. Returns count written."""
    from .linker import apply_mirror
    from .transform.mcp import canonical_servers

    written = 0
    for mirror in plan.mirrors:
        if mirror.action is Action.CONFLICT:
            continue
        if mirror.action is not Action.UNCHANGED:
            apply_mirror(mirror, mode, canonical=config.canonical)
            written += 1

        rel = config.rel(mirror.target)
        owned: List[str] = []
        if mirror.strategy is Strategy.MERGE:
            try:
                asset_body = mirror.source.read_text(encoding="utf-8")
                owned = sorted(
                    canonical_servers(
                        Asset(kind=AssetKind.MCP, slug="mcp", path=mirror.source, body=asset_body)
                    )
                )
            except (OSError, ValueError):
                owned = state.owned_in(rel)

        state.entries[rel] = Entry(
            adapter=mirror.adapter_id,
            kind=str(mirror.kind),
            slug=mirror.slug,
            source=config.rel(mirror.source),
            strategy=str(mirror.strategy),
            output_hash=source_hash(mirror.payload) if mirror.payload is not None else "",
            source_hash=source_hash(
                mirror.source.read_bytes() if mirror.source.is_file() else b""
            ),
            owned=owned,
        )

    _prune(plan, config, state)
    state.save(config.state_path)
    return written


def _prune(plan: SyncPlan, config: Config, state: State) -> None:
    """Forget managed paths whose canonical source is gone, and delete the mirror.

    Only files we recorded are removed, and only when their source no longer
    exists -- deleting a rule should not leave its mirrors behind forever.
    """
    planned = {config.rel(m.target) for m in plan.mirrors}
    for rel in list(state.entries):
        if rel in planned:
            continue
        entry = state.entries[rel]
        if entry.strategy == str(Strategy.MERGE):
            continue  # shared config: leaving a stale server is safer than editing blind
        source = config.root / entry.source if entry.source else None
        if source is not None and source.exists():
            continue
        path = config.root / rel
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir() and entry.strategy == str(Strategy.LINK):
                pass  # a real directory is never removed automatically
        except OSError:
            pass
        state.entries.pop(rel, None)


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
