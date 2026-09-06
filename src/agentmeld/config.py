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

__all__ = ["Config", "find_repo_root", "load_config", "discover_assets", "CONFIG_NAME"]

CONFIG_NAME = "agentmeld.toml"
STATE_NAME = ".state.json"
DEFAULT_CANONICAL = ".ai"


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

    @property
    def canonical(self) -> Path:
        return self.root / self.canonical_dir

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
    targets = section.get("targets")
    cfg.targets = tuple(targets) if targets else None

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
    if not base.is_dir():
        return assets

    instructions = base / "instructions.md"
    if instructions.is_file():
        assets.append(_load_markdown(AssetKind.INSTRUCTIONS, "instructions", instructions))

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
