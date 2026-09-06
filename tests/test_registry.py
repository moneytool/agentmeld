from collections import Counter

import pytest

from agentmeld.model import AssetKind, Confidence, Strategy
from agentmeld.registry import kind_confidence, load_registry
from agentmeld.registry.schema import AdapterSchemaError, parse_adapter
from agentmeld.transform import names as transformer_names


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_bundled_adapters_load(registry):
    assert {"agents", "claude", "copilot", "cursor", "gemini"} <= set(registry)


def test_every_target_is_repo_relative(registry):
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            assert not spec.target.startswith("/")
            assert ".." not in spec.target.split("/")


def test_no_two_adapters_claim_the_same_path(registry):
    counts = Counter(
        spec.render_target("slug")
        for adapter in registry.values()
        for spec in adapter.kinds.values()
    )
    assert [t for t, n in counts.items() if n > 1] == []


def test_every_named_transformer_exists(registry):
    available = set(transformer_names())
    for adapter in registry.values():
        for spec in adapter.kinds.values():
            if spec.transformer:
                assert spec.transformer in available


def test_generate_and_merge_kinds_declare_a_transformer(registry):
    for adapter in registry.values():
        for kind, spec in adapter.kinds.items():
            if spec.strategy is Strategy.MERGE:
                assert spec.transformer, "{}/{}".format(adapter.id, kind)


def test_gemini_commands_cannot_be_symlinked(registry):
    """The case that justifies the generate strategy existing at all."""
    spec = registry["gemini"].spec(AssetKind.COMMAND)
    assert spec.strategy is Strategy.GENERATE
    assert spec.target.endswith(".toml")


def test_cursor_rules_use_mdc_not_md(registry):
    """Cursor ignores plain .md inside .cursor/rules."""
    assert registry["cursor"].spec(AssetKind.RULE).target.endswith(".mdc")


def test_only_agents_adapter_owns_agents_md(registry):
    owners = [
        adapter.id
        for adapter in registry.values()
        for spec in adapter.kinds.values()
        if spec.target == "AGENTS.md"
    ]
    assert owners == ["agents"]


def test_per_kind_confidence_overrides_adapter(registry):
    copilot = registry["copilot"]
    assert copilot.confidence is Confidence.VERIFIED
    assert kind_confidence(copilot, AssetKind.AGENT) is Confidence.UNVERIFIED
    assert kind_confidence(copilot, AssetKind.RULE) is Confidence.VERIFIED


class TestSchemaValidation:
    def test_missing_id_rejected(self):
        with pytest.raises(AdapterSchemaError):
            parse_adapter({"name": "x", "confidence": "verified", "kinds": {}})

    def test_absolute_target_rejected(self):
        with pytest.raises(AdapterSchemaError):
            parse_adapter({
                "id": "x", "name": "x", "confidence": "verified",
                "kinds": {"rule": {"target": "/etc/passwd", "strategy": "link"}},
            })

    def test_upward_traversal_rejected(self):
        with pytest.raises(AdapterSchemaError):
            parse_adapter({
                "id": "x", "name": "x", "confidence": "verified",
                "kinds": {"rule": {"target": "../outside.md", "strategy": "link"}},
            })

    def test_unknown_strategy_rejected(self):
        with pytest.raises(AdapterSchemaError):
            parse_adapter({
                "id": "x", "name": "x", "confidence": "verified",
                "kinds": {"rule": {"target": "a.md", "strategy": "teleport"}},
            })

    def test_adapter_without_kinds_rejected(self):
        with pytest.raises(AdapterSchemaError):
            parse_adapter({"id": "x", "name": "x", "confidence": "verified"})
