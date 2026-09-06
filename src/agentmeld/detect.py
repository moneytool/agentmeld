"""Working out which AI tools a repo actually uses."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .config import Config
from .model import Adapter
from .state import State

__all__ = ["detect_tools", "evidence_for"]


def _exists(root: Path, pattern: str) -> bool:
    path = root / pattern.rstrip("/")
    return path.is_dir() if pattern.endswith("/") else (path.is_file() or path.is_dir())


def evidence_for(adapter: Adapter, config: Config, state: State) -> List[str]:
    """Paths proving this tool is in use, excluding anything we created.

    Without that exclusion the tool becomes self-confirming: sync writes
    ``.cursor/rules/``, and from then on every repo looks like a Cursor repo.
    """
    managed = set(state.managed_paths())
    hits = []
    for pattern in adapter.detect:
        rel = pattern.rstrip("/")
        if rel in managed:
            continue
        if any(m == rel or m.startswith(rel + "/") for m in managed):
            continue
        if _exists(config.root, pattern):
            hits.append(pattern)
    return hits


def detect_tools(adapters: Dict[str, Adapter], config: Config, state: State) -> Dict[str, List[str]]:
    """``{adapter_id: [evidence, ...]}`` for every tool with at least one hit."""
    found = {}
    for adapter_id, adapter in adapters.items():
        hits = evidence_for(adapter, config, state)
        if hits:
            found[adapter_id] = hits
    return found
