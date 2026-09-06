"""The manifest of what agentmeld manages.

Without this we could not tell "a file we generated and may safely rewrite" from
"a file a human wrote that we must not touch", nor which MCP servers were ours
to remove. It is the difference between a safe tool and a destructive one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["State", "Entry"]

VERSION = 1


@dataclass
class Entry:
    """One managed vendor path."""

    adapter: str
    kind: str
    slug: str
    source: str
    strategy: str
    output_hash: str = ""
    source_hash: str = ""
    owned: List[str] = field(default_factory=list)
    """For merged config: the keys inside the file that are ours."""

    def to_json(self) -> Dict[str, Any]:
        data = {
            "adapter": self.adapter,
            "kind": self.kind,
            "slug": self.slug,
            "source": self.source,
            "strategy": self.strategy,
            "output_hash": self.output_hash,
            "source_hash": self.source_hash,
        }
        if self.owned:
            data["owned"] = sorted(self.owned)
        return data

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Entry":
        return cls(
            adapter=data.get("adapter", ""),
            kind=data.get("kind", ""),
            slug=data.get("slug", ""),
            source=data.get("source", ""),
            strategy=data.get("strategy", ""),
            output_hash=data.get("output_hash", ""),
            source_hash=data.get("source_hash", ""),
            owned=list(data.get("owned", ())),
        )


@dataclass
class State:
    entries: Dict[str, Entry] = field(default_factory=dict)
    """Keyed by repo-relative POSIX vendor path."""

    provenance: Dict[str, Dict[str, str]] = field(default_factory=dict)
    """Canonical path -> where it was adopted from, and when."""

    tools: List[str] = field(default_factory=list)
    """Adapter ids this repo is known to use.

    Detection alone is not enough: ``init`` moves the very files that prove a tool
    is in use, so without a record, migrating a repo would stop mirroring to the
    tool whose config it just adopted.
    """

    path: Optional[Path] = None

    # -- io ---------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "State":
        """Read state, tolerating absence and corruption.

        A corrupt manifest must not brick the repo: we fall back to empty, which
        makes every managed file look unmanaged, so ``sync`` reports conflicts
        instead of overwriting anything.
        """
        if not path.is_file():
            return cls(path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return cls(path=path)
        entries = {
            key: Entry.from_json(value) for key, value in dict(data.get("entries", {})).items()
        }
        return cls(
            entries=entries,
            provenance=dict(data.get("provenance", {})),
            tools=list(data.get("tools", ())),
            path=path,
        )

    def save(self, path: Optional[Path] = None) -> None:
        target = path or self.path
        if target is None:
            raise ValueError("no path to save state to")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": VERSION,
            "entries": {key: entry.to_json() for key, entry in sorted(self.entries.items())},
            "provenance": dict(sorted(self.provenance.items())),
            "tools": sorted(set(self.tools)),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes((text).encode("utf-8"))
        tmp.replace(target)

    # -- queries ----------------------------------------------------------

    def get(self, rel_path: str) -> Optional[Entry]:
        return self.entries.get(rel_path)

    def owned_in(self, rel_path: str) -> List[str]:
        entry = self.entries.get(rel_path)
        return list(entry.owned) if entry else []

    def managed_paths(self) -> List[str]:
        return sorted(self.entries)

    def remember_tools(self, adapter_ids) -> None:
        self.tools = sorted(set(self.tools) | set(adapter_ids))

    def record_adoption(self, canonical_rel: str, source_rel: str, when: str) -> None:
        self.provenance[canonical_rel] = {"adopted_from": source_rel, "at": when}
