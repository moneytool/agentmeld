"""Loading the bundled adapter registry (and any the user adds)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..model import Adapter, AssetKind, Confidence
from .schema import AdapterSchemaError, parse_adapter

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on the 3.9/3.10 CI legs
    import tomli as tomllib

__all__ = ["load_registry", "ADAPTER_DIR", "AdapterSchemaError", "kind_confidence"]

ADAPTER_DIR = Path(__file__).parent / "adapters"

_CACHE: Optional[Dict[str, Adapter]] = None


def load_registry(extra_dirs: Iterable[Path] = ()) -> Dict[str, Adapter]:
    """Return ``{adapter_id: Adapter}``, bundled adapters first.

    Results are cached, since the bundled files cannot change at runtime. Passing
    ``extra_dirs`` bypasses the cache so a repo can ship its own adapter.
    """
    global _CACHE
    extra = [Path(d) for d in extra_dirs]
    if _CACHE is not None and not extra:
        return dict(_CACHE)

    adapters: Dict[str, Adapter] = {}
    for directory in [ADAPTER_DIR] + extra:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.toml")):
            with path.open("rb") as handle:
                data = tomllib.load(handle)
            adapter = parse_adapter(data, where=path.name)
            if adapter.id in adapters and directory is ADAPTER_DIR:
                raise AdapterSchemaError(
                    "duplicate adapter id {!r} in {}".format(adapter.id, path.name)
                )
            adapters[adapter.id] = adapter

    if not extra:
        _CACHE = dict(adapters)
    return adapters


def kind_confidence(adapter: Adapter, kind: AssetKind) -> Confidence:
    """Effective confidence for one kind: the per-kind override, else the tool's."""
    spec = adapter.spec(kind)
    if spec is not None and spec.confidence is not None:
        return spec.confidence
    return adapter.confidence


def verified_ids(adapters: Dict[str, Adapter]) -> List[str]:
    return sorted(a.id for a in adapters.values() if a.confidence is Confidence.VERIFIED)
