"""Repo discovery, configuration, and canonical asset loading."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .model import Asset, AssetKind
from .transform import frontmatter as fm

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

__all__ = [
    "Config",
    "find_repo_root",
    "load_config",
    "discover_assets",
    "load_overlays",
    "CONFIG_NAME",
    "ROOT_INSTRUCTION_CANDIDATES",
]

CONFIG_NAME = "agentmeld.toml"
STATE_NAME = ".state.json"
DEFAULT_CANONICAL = ".ai"

#: Root files that are already a cross-vendor instruction document, most
#: preferred first. When one of these exists we make it the source of truth
#: rather than moving it into the canonical tree: AGENTS.md is the most common
#: AI config file in public repos and its lead grows with popularity, so
#: relocating it charges every adopter a migration for no benefit.
ROOT_INSTRUCTION_CANDIDATES = ("AGENTS.md", "CLAUDE.md")


@dataclass
class Config:
    """Resolved settings for one repo."""

    root: Path
    canonical_dir: str = DEFAULT_CANONICAL
    mode: str = "auto"
    """``auto`` probes for symlink support; ``link`` and ``copy`` force it."""

    git_policy: str = "commit"
    targets: Optional[Sequence[str]] = None
    """Adapter ids to sync. ``None`` means "every tool detected in this repo"."""

    include_unverified: bool = False
    extra_adapter_dirs: Sequence[str] = ()

    instructions: Optional[str] = None
    """Repo-relative path of the canonical instructions file.

    ``None`` means "work it out": a root ``AGENTS.md`` (then ``CLAUDE.md``) if one
    exists, else ``<canonical_dir>/instructions.md``. Set it explicitly to pin
    the source of truth somewhere else.
    """

    @property
    def canonical(self) -> Path:
        return self.root / self.canonical_dir

    @property
    def instructions_rel(self) -> str:
        """Resolved repo-relative canonical instructions path."""
        if self.instructions:
            return self.instructions
        for name in ROOT_INSTRUCTION_CANDIDATES:
            if _is_source_of_truth(self.root / name):
                return name
        return "{}/instructions.md".format(self.canonical_dir)

    @property
    def instructions_path(self) -> Path:
        return self.root / self.instructions_rel

    @property
    def overlays_dir(self) -> Path:
        """Per-tool additions appended to that tool's mirror."""
        return self.canonical / "overlays"

    @property
    def config_path(self) -> Path:
        return self.canonical / CONFIG_NAME

    @property
    def state_path(self) -> Path:
        return self.canonical / STATE_NAME

    def rel(self, path: Path) -> str:
        """Repo-relative POSIX path, for display and for provenance headers.

        Deliberately does *not* resolve symlinks. A mirror that is a symlink into
        the canonical tree would otherwise report the canonical path as its own,
        which would key state by the wrong file and let a write land on the source
        of truth instead of the mirror.
        """
        absolute = Path(os.path.abspath(str(path)))
        try:
            return absolute.relative_to(Path(os.path.abspath(str(self.root)))).as_posix()
        except ValueError:
            return absolute.as_posix()

    def inside_canonical(self, path: Path) -> bool:
        """True when a path lies within the canonical tree."""
        rel = self.rel(path)
        return rel == self.canonical_dir or rel.startswith(self.canonical_dir + "/")


def _is_source_of_truth(path: Path) -> bool:
    """True when ``path`` is a hand-written instruction file, not one of our mirrors.

    Auto-detection has to exclude agentmeld's own output or the source of truth
    moves between runs: sync writes a root AGENTS.md mirror, the next run sees it
    and adopts it as canonical, and nothing is idempotent any more. Three shapes
    are ours -- a symlink, a file carrying the generated header, and a bare import
    line -- and none of them is somebody's authored content.
    """
    if not path.is_file() or path.is_symlink():
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    from .transform import HEADER_TOKEN

    if HEADER_TOKEN in head:
        return False
    stripped = head.strip()
    if stripped.startswith("@") and "\n" not in stripped:
        return False  # a one-line import mirror
    return True


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Nearest ancestor holding ``.git`` or an existing canonical dir, else cwd.

    Falling back to cwd rather than raising keeps the tool usable in a directory
    that is not a git repo yet.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / ".git").exists() or (candidate / DEFAULT_CANONICAL / CONFIG_NAME).exists():
            return candidate
    return current


def load_config(root: Optional[Path] = None, canonical_dir: Optional[str] = None) -> Config:
    """Read ``.ai/agentmeld.toml`` if present; defaults otherwise."""
    root = (root or find_repo_root()).resolve()
    cfg = Config(root=root, canonical_dir=canonical_dir or DEFAULT_CANONICAL)

    path = cfg.config_path
    if not path.is_file():
        return cfg

    with path.open("rb") as handle:
        data: Dict[str, Any] = tomllib.load(handle)

    section = data.get("agentmeld", data)
    cfg.canonical_dir = canonical_dir or section.get("canonical_dir", cfg.canonical_dir)
    cfg.mode = section.get("mode", cfg.mode)
    cfg.git_policy = section.get("git_policy", cfg.git_policy)
    cfg.include_unverified = bool(section.get("include_unverified", cfg.include_unverified))
    cfg.extra_adapter_dirs = tuple(section.get("extra_adapter_dirs", ()))
    cfg.instructions = section.get("instructions", cfg.instructions)
    targets = section.get("targets")
    cfg.targets = tuple(targets) if targets else None

    if cfg.instructions is None and (cfg.canonical / "instructions.md").is_file():
        # An already-initialised repo keeps the source of truth it has. Upgrading
        # agentmeld must not relocate it, and auto-detection could: a copy-mode
        # AGENTS.md mirror with no rules folded in is a plain headerless file, and
        # would otherwise look exactly like an authored one.
        cfg.instructions = "{}/instructions.md".format(cfg.canonical_dir)

    if cfg.mode not in ("auto", "link", "copy"):
        raise ValueError("mode must be auto, link or copy (got {!r})".format(cfg.mode))
    if cfg.git_policy not in ("commit", "ignore"):
        raise ValueError("git_policy must be commit or ignore (got {!r})".format(cfg.git_policy))
    return cfg


# ---------------------------------------------------------------------------
# loading canonical assets
# ---------------------------------------------------------------------------

_SKIP_NAMES = {".state.json", CONFIG_NAME}


def _read(path: Path) -> bytes:
    return path.read_bytes()


def _load_markdown(kind: AssetKind, slug: str, path: Path) -> Asset:
    raw = _read(path)
    front, body = fm.split(raw.decode("utf-8"))
    return Asset(kind=kind, slug=slug, path=path, frontmatter=front, body=body, raw=raw)


def discover_assets(config: Config) -> List[Asset]:
    """Load every canonical asset under the canonical root.

    Missing subdirectories are simply absent, not an error: a repo may have
    instructions and nothing else.
    """
    assets: List[Asset] = []
    base = config.canonical

    instructions = config.instructions_path
    if instructions.is_file():
        assets.append(_load_markdown(AssetKind.INSTRUCTIONS, "instructions", instructions))

    if not base.is_dir():
        # Canonical instructions can live at the repo root with no canonical tree
        # at all, which is the common shape: one file, several mirrors.
        return assets

    for kind, subdir in (
        (AssetKind.RULE, "rules"),
        (AssetKind.AGENT, "agents"),
        (AssetKind.COMMAND, "commands"),
    ):
        directory = base / subdir
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            if path.name in _SKIP_NAMES or not path.is_file():
                continue
            if ".backup" in path.parts:
                continue
            slug = path.relative_to(directory).with_suffix("").as_posix()
            assets.append(_load_markdown(kind, slug, path))

    skills = base / "skills"
    if skills.is_dir():
        for skill_md in sorted(skills.glob("*/SKILL.md")):
            slug = skill_md.parent.name
            asset = _load_markdown(AssetKind.SKILL, slug, skill_md)
            asset.sidecars = sorted(
                p for p in skill_md.parent.rglob("*") if p.is_file() and p != skill_md
            )
            assets.append(asset)

    mcp = base / "mcp.json"
    if mcp.is_file():
        raw = _read(mcp)
        assets.append(
            Asset(
                kind=AssetKind.MCP,
                slug="mcp",
                path=mcp,
                body=raw.decode("utf-8"),
                raw=raw,
            )
        )

    return assets


def load_overlays(config: Config) -> Dict[str, str]:
    """Adapter id -> that tool's extra instructions, from ``overlays/<id>.md``.

    Nearly a third of repos carrying two instruction files write genuinely
    different content in them -- release procedure, CI specifics, tool
    invocation -- so mirroring one file into the other would destroy
    information. Overlays are how that content keeps a home while the shared
    part still has a single source.
    """
    out: Dict[str, str] = {}
    directory = config.overlays_dir
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.md")):
        if not path.is_file():
            continue
        try:
            out[path.stem] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return out
