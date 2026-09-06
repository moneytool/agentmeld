"""Core value types.

Nothing in here touches the filesystem; ``linker`` and ``canonical`` do that.
Keeping the model pure is what makes ``--dry-run`` trustworthy: a plan is built
from these objects and can be printed without a single write.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# kinds of context
# ---------------------------------------------------------------------------


class AssetKind(str, enum.Enum):
    """The categories of context an AI tool can be configured with."""

    INSTRUCTIONS = "instructions"
    """The single top-level "how to work in this repo" document."""

    RULE = "rule"
    """A scoped instruction, usually attached to file globs."""

    SKILL = "skill"
    """A directory-shaped, on-demand capability (``SKILL.md`` plus sidecars)."""

    AGENT = "agent"
    """A subagent / custom-mode definition."""

    COMMAND = "command"
    """A slash command / reusable prompt."""

    MCP = "mcp"
    """Model Context Protocol server declarations."""

    def __str__(self) -> str:  # nicer CLI output than "AssetKind.RULE"
        return self.value

    @property
    def is_directory_shaped(self) -> bool:
        """True when one asset is a directory of files rather than a single file."""
        return self is AssetKind.SKILL


class Strategy(str, enum.Enum):
    """How a mirror is materialised on disk."""

    LINK = "link"
    """Relative symlink from the vendor path to the canonical file."""

    GENERATE = "generate"
    """A derived file: translated frontmatter plus a provenance header."""

    MERGE = "merge"
    """Surgically update our subtree inside a config file we do not own."""

    AGGREGATE = "aggregate"
    """Concatenate instructions plus every rule into one file.

    Claude Code, Gemini CLI and AGENTS.md have no per-file rule mechanism -- they
    read a single document. Their rules have to land *somewhere*, so they are
    appended, each under its own heading with its globs stated in prose.
    """

    def __str__(self) -> str:
        return self.value


class Confidence(str, enum.Enum):
    """How well an adapter's paths were checked.

    A tool that moves people's files must not act on a guess, so anything not
    confirmed against primary vendor documentation is opt-in only.
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# canonical assets
# ---------------------------------------------------------------------------


@dataclass
class Asset:
    """One piece of canonical context living under the canonical root."""

    kind: AssetKind
    slug: str
    path: Path
    """Absolute path to the canonical file (``SKILL.md`` for a skill)."""

    frontmatter: Dict[str, Any] = field(default_factory=dict)
    """Canonical frontmatter vocabulary -- a superset of every vendor's keys."""

    body: str = ""
    raw: Optional[bytes] = None
    """Original bytes, so ``link`` mirrors are byte-exact."""

    sidecars: List[Path] = field(default_factory=list)
    """Extra files belonging to a directory-shaped asset (skills)."""

    @property
    def root(self) -> Path:
        """The directory that *is* the asset, for directory-shaped kinds."""
        return self.path.parent if self.kind.is_directory_shaped else self.path


# ---------------------------------------------------------------------------
# adapters (loaded from the declarative registry)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KindSpec:
    """What one adapter does with one kind of asset."""

    kind: AssetKind
    target: str
    """Vendor path template, POSIX-style, relative to the repo root.

    Supports ``{slug}``. A template ending in ``/`` means "a directory per
    asset", used for skills.
    """

    strategy: Strategy
    transformer: Optional[str] = None
    """Named transformer for formats plain key-renaming cannot express."""

    frontmatter: Mapping[str, str] = field(default_factory=dict)
    """canonical key -> vendor key, or a ``__directive__``."""

    defaults: Mapping[str, Any] = field(default_factory=dict)
    """Vendor keys forced onto every generated file of this kind."""

    confidence: Optional["Confidence"] = None
    """Per-kind override. A tool's main instruction file may be documented while
    its skills directory is not; pretending otherwise would be dishonest."""

    aggregate_rules: bool = False
    """Fold rules into this file when the adapter has no rule kind.

    A plain ``link`` stays a symlink while no rules exist, and is upgraded to an
    ``aggregate`` the moment one does -- so the symlink-first promise holds in
    the common case without losing rules in the uncommon one.
    """

    note: str = ""

    def render_target(self, slug: str) -> str:
        return self.target.format(slug=slug)


@dataclass(frozen=True)
class Adapter:
    """A declarative description of one AI tool's on-disk configuration."""

    id: str
    name: str
    confidence: Confidence
    detect: Sequence[str] = ()
    """Paths whose presence proves the tool is in use in this repo."""

    kinds: Mapping[AssetKind, KindSpec] = field(default_factory=dict)
    docs: str = ""
    note: str = ""

    def spec(self, kind: AssetKind) -> Optional[KindSpec]:
        return self.kinds.get(kind)

    def supports(self, kind: AssetKind) -> bool:
        return kind in self.kinds


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------


class Action(str, enum.Enum):
    """What ``sync`` intends to do to a single path."""

    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    """A real, unmanaged file is in the way; we refuse to clobber it."""

    SKIP = "skip"

    def __str__(self) -> str:
        return self.value


@dataclass
class Mirror:
    """One intended vendor-side materialisation of one canonical asset."""

    adapter_id: str
    kind: AssetKind
    slug: str
    source: Path
    """Absolute canonical path."""

    target: Path
    """Absolute vendor path."""

    strategy: Strategy
    action: Action = Action.CREATE
    payload: Optional[bytes] = None
    """Bytes to write for ``generate``/``merge``. ``None`` for ``link``."""

    reason: str = ""
    """Human-readable explanation, shown in the plan table and on conflict."""

    dir_link: bool = False
    """Link the asset's whole directory rather than a single file.

    Skills are directory-shaped, so one symlink of the directory carries
    ``SKILL.md`` and every sidecar with it -- and a file the agent adds later
    appears on both sides automatically, with no sync at all.
    """

    @property
    def is_noop(self) -> bool:
        return self.action in (Action.UNCHANGED, Action.SKIP)


@dataclass
class SyncPlan:
    """Everything ``sync`` would do, before anything is written."""

    mirrors: List[Mirror] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __iter__(self):
        return iter(self.mirrors)

    def __len__(self) -> int:
        return len(self.mirrors)

    @property
    def changes(self) -> List[Mirror]:
        """Mirrors that would actually be written. Conflicts are not writes."""
        return [m for m in self.mirrors if m.action in (Action.CREATE, Action.UPDATE)]

    @property
    def conflicts(self) -> List[Mirror]:
        return [m for m in self.mirrors if m.action is Action.CONFLICT]

    @property
    def is_clean(self) -> bool:
        """True when nothing needs writing -- the ``--check`` success condition."""
        return not self.changes
