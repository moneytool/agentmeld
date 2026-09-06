"""Pulling vendor files back into the canonical tree.

This is the direction the existing tools do not automate, and the reason watch
mode can work: when an agent writes a brand-new ``.claude/skills/foo/SKILL.md``,
that content becomes canonical and is fanned out to every other tool, instead of
staying stranded in one vendor's directory.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config
from .model import Adapter, AssetKind, KindSpec, Strategy
from .state import State
from .transform import HEADER_TOKEN, parse_header
from .transform import frontmatter as fm

__all__ = ["classify_path", "reverse_frontmatter", "canonical_dest", "run_adopt", "is_ours"]


# ---------------------------------------------------------------------------
# which adapter/kind does a path belong to?
# ---------------------------------------------------------------------------


def _target_regex(template: str) -> "re.Pattern":
    parts = template.split("{slug}")
    pattern = "(?P<slug>.+)".join(re.escape(p) for p in parts)
    return re.compile("^" + pattern + "$")


def classify_path(
    rel_path: str,
    registry: Dict[str, Adapter],
) -> Optional[Tuple[Adapter, KindSpec, str]]:
    """Match a repo-relative path against every adapter's target templates.

    Templates with a ``{slug}`` are preferred over literal ones, so
    ``.github/instructions/x.instructions.md`` is recognised as a rule rather
    than accidentally matching something broader.
    """
    best: Optional[Tuple[Adapter, KindSpec, str]] = None
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            match = _target_regex(spec.target).match(rel_path)
            if not match:
                continue
            slug = match.groupdict().get("slug") or spec.kind.value
            candidate = (adapter, spec, slug)
            if "{slug}" in spec.target:
                return candidate
            best = best or candidate
    return best


def is_ours(path: Path, rel_path: str, state: State) -> bool:
    """True when this path is already a mirror we manage.

    Checked three ways, because any one of them can be stale: state, a symlink
    pointing into the canonical tree, and our generated header. This is the guard
    that stops watch mode from adopting its own output in a loop.
    """
    if state.get(rel_path) is not None:
        return True
    if path.is_symlink():
        return True
    if path.is_file():
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4096]
        except OSError:
            return False
        if HEADER_TOKEN in head:
            return True
    return False


# ---------------------------------------------------------------------------
# vendor frontmatter -> canonical frontmatter
# ---------------------------------------------------------------------------


def reverse_frontmatter(vendor: Dict[str, object], spec: KindSpec) -> Dict[str, object]:
    """Invert an adapter's frontmatter mapping.

    Ambiguity is real here: Copilot maps both ``globs`` and ``always`` onto
    ``applyTo``. It is resolved by value -- ``applyTo: "**"`` came from
    ``always``, anything else from ``globs``.
    """
    plain: Dict[str, Tuple[str, str]] = {}
    flags: Dict[str, List[Tuple[str, str]]] = {}

    for canonical_key, directive in spec.frontmatter.items():
        if directive == fm.DROP:
            continue
        if "!" in directive:
            vendor_key, _, literal = directive.partition("!")
            flags.setdefault(vendor_key, []).append((canonical_key, literal))
        elif directive.endswith(":comma"):
            plain[directive[: -len(":comma")]] = (canonical_key, "comma")
        else:
            plain[directive] = (canonical_key, "plain")

    out: Dict[str, object] = {}
    for vendor_key, value in vendor.items():
        matched = False
        for canonical_key, literal in flags.get(vendor_key, []):
            if _matches_literal(value, literal):
                out[canonical_key] = True
                matched = True
                break
        if matched:
            continue
        if vendor_key in plain:
            canonical_key, how = plain[vendor_key]
            if how == "comma" and isinstance(value, str):
                out[canonical_key] = [p.strip() for p in value.split(",") if p.strip()]
            else:
                out[canonical_key] = value
            continue
        if vendor_key in spec.defaults and spec.defaults[vendor_key] == value:
            continue  # a default we wrote ourselves carries no information
        if vendor_key not in plain and vendor_key not in flags:
            out[vendor_key] = value  # unknown key: keep it rather than lose it
    return out


def _matches_literal(value: object, literal: str) -> bool:
    lowered = literal.strip().lower()
    if lowered in ("true", "false"):
        return bool(value) is (lowered == "true")
    return value == literal


# ---------------------------------------------------------------------------
# adoption
# ---------------------------------------------------------------------------


def canonical_dest(config: Config, kind: AssetKind, slug: str) -> Path:
    base = config.canonical
    if kind is AssetKind.INSTRUCTIONS:
        return base / "instructions.md"
    if kind is AssetKind.MCP:
        return base / "mcp.json"
    if kind is AssetKind.SKILL:
        return base / "skills" / slug / "SKILL.md"
    return base / {AssetKind.RULE: "rules", AssetKind.AGENT: "agents", AssetKind.COMMAND: "commands"}[kind] / (slug + ".md")


def adopt_path(
    path: Path,
    config: Config,
    registry: Dict[str, Adapter],
    state: State,
    dry_run: bool = False,
) -> Optional[str]:
    """Move one vendor file into the canonical tree. Returns a log line, or None."""
    from .planner import now_iso

    rel = config.rel(path)
    if not path.exists():
        return None
    if is_ours(path, rel, state):
        return None

    hit = classify_path(rel, registry)
    if hit is None:
        return None
    adapter, spec, slug = hit
    if spec.strategy is Strategy.MERGE and hit[1].kind is not AssetKind.MCP:
        return None

    dest = canonical_dest(config, spec.kind, slug)
    if dest.exists():
        return "{}: canonical {} already exists, left alone".format(rel, config.rel(dest))

    if dry_run:
        return "{} -> {} (would adopt)".format(rel, config.rel(dest))

    dest.parent.mkdir(parents=True, exist_ok=True)

    if spec.kind is AssetKind.SKILL:
        # A skill is its whole directory. Moving only SKILL.md would strand the
        # sidecars and leave a real directory where the symlink belongs.
        source_dir, dest_dir = path.parent, dest.parent
        if dest_dir.exists():
            shutil.rmtree(str(dest_dir))
        shutil.move(str(source_dir), str(dest_dir))
        state.record_adoption(config.rel(dest), rel, now_iso())
        return "{} -> {} (adopted whole skill dir from {})".format(
            config.rel(source_dir), config.rel(dest_dir), adapter.name
        )

    if spec.kind is AssetKind.MCP or path.suffix == ".json":
        shutil.move(str(path), str(dest))
    elif path.suffix == ".toml":
        return "{}: adopting TOML commands is not supported yet".format(rel)
    else:
        text = path.read_text(encoding="utf-8")
        vendor_fm, body = fm.split(text)
        canonical_fm = reverse_frontmatter(vendor_fm, spec)
        dest.write_bytes((fm.render(canonical_fm, body)).encode("utf-8"))
        path.unlink()

    state.record_adoption(config.rel(dest), rel, now_iso())
    return "{} -> {} (adopted from {})".format(rel, config.rel(dest), adapter.name)


def run_adopt(config: Config, registry, state: State, args) -> int:
    from .cli import EXIT_ERROR, EXIT_OK

    lines: List[str] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_absolute():
            path = config.root / path
        line = adopt_path(path, config, registry, state, dry_run=args.dry_run)
        lines.append(line or "{}: nothing to adopt (unrecognised, or already managed)".format(raw))

    for line in lines:
        print("  " + line)

    if args.dry_run:
        print("dry run: nothing written")
        return EXIT_OK

    state.save(config.state_path)
    if args.no_sync:
        return EXIT_OK

    print("\nfanning out:")
    from .cli import build_parser

    sync_args = build_parser().parse_args(["sync"])
    sync_args.root = str(config.root)
    sync_args.include_unverified = config.include_unverified
    from .cli import cmd_sync

    return cmd_sync(sync_args)
