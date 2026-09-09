"""Parsing adapter TOML into :class:`~agentmeld.model.Adapter` objects.

Adapters are data, not code. That is what makes supporting a moving target of a
dozen vendors maintainable, and what lets someone add their tool with a pull
request that contains no Python.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from ..model import Adapter, AssetKind, Confidence, KindSpec, Strategy

__all__ = ["parse_adapter", "AdapterSchemaError"]


class AdapterSchemaError(ValueError):
    """An adapter file is malformed. Raised eagerly, with the file named."""


def _require(data: Mapping[str, Any], key: str, where: str) -> Any:
    try:
        return data[key]
    except KeyError:
        raise AdapterSchemaError("{}: missing required key {!r}".format(where, key)) from None


def _enum(cls, value: Any, where: str, key: str):
    try:
        return cls(value)
    except ValueError:
        valid = ", ".join(sorted(m.value for m in cls))
        raise AdapterSchemaError(
            "{}: {}={!r} is not one of: {}".format(where, key, value, valid)
        ) from None


def parse_adapter(data: Mapping[str, Any], where: str = "<adapter>") -> Adapter:
    """Build an Adapter from a parsed TOML mapping, validating as we go."""
    adapter_id = _require(data, "id", where)
    name = _require(data, "name", where)
    confidence = _enum(Confidence, _require(data, "confidence", where), where, "confidence")

    detect = tuple(data.get("detect", ()))
    if not all(isinstance(d, str) for d in detect):
        raise AdapterSchemaError("{}: every 'detect' entry must be a string".format(where))

    kinds: Dict[AssetKind, KindSpec] = {}
    for raw_kind, block in dict(data.get("kinds", {})).items():
        loc = "{}[kinds.{}]".format(where, raw_kind)
        kind = _enum(AssetKind, raw_kind, loc, "kind")
        strategy = _enum(Strategy, _require(block, "strategy", loc), loc, "strategy")
        target = _require(block, "target", loc)
        if not isinstance(target, str) or not target:
            raise AdapterSchemaError("{}: 'target' must be a non-empty string".format(loc))
        if target.startswith("/") or ".." in target.split("/"):
            raise AdapterSchemaError(
                "{}: 'target' must be repo-relative and must not escape upward".format(loc)
            )

        import_line = block.get("import_line", "")
        if strategy is Strategy.IMPORT:
            if not import_line:
                raise AdapterSchemaError(
                    "{}: strategy='import' needs 'import_line' (e.g. \"@{{path}}\")".format(loc)
                )
            if "{path}" not in import_line:
                raise AdapterSchemaError(
                    "{}: 'import_line' must contain {{path}}".format(loc)
                )
        elif import_line:
            raise AdapterSchemaError(
                "{}: 'import_line' only means something with strategy='import'".format(loc)
            )

        raw_conf = block.get("confidence")
        kinds[kind] = KindSpec(
            kind=kind,
            target=target,
            strategy=strategy,
            transformer=block.get("transformer"),
            import_line=import_line,
            frontmatter=dict(block.get("frontmatter", {})),
            defaults=dict(block.get("defaults", {})),
            confidence=_enum(Confidence, raw_conf, loc, "confidence") if raw_conf else None,
            aggregate_rules=bool(block.get("aggregate_rules", False)),
            note=block.get("note", ""),
        )

    if not kinds:
        raise AdapterSchemaError("{}: declares no [kinds.*] blocks".format(where))

    return Adapter(
        id=adapter_id,
        name=name,
        confidence=confidence,
        detect=detect,
        kinds=kinds,
        docs=data.get("docs", ""),
        note=data.get("note", ""),
    )
