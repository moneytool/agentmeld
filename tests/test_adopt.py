import pytest

from agentmeld.model import AssetKind
from agentmeld.registry import load_registry
from agentmeld.adopt import classify_path, reverse_frontmatter


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.mark.parametrize(
    "path,adapter,kind,slug",
    [
        (".cursor/rules/testing.mdc", "cursor", AssetKind.RULE, "testing"),
        (".github/instructions/t.instructions.md", "copilot", AssetKind.RULE, "t"),
        ("CLAUDE.md", "claude", AssetKind.INSTRUCTIONS, "instructions"),
        (".claude/skills/deploy/SKILL.md", "claude", AssetKind.SKILL, "deploy"),
        (".claude/agents/rev.md", "claude", AssetKind.AGENT, "rev"),
        (".gemini/commands/x.toml", "gemini", AssetKind.COMMAND, "x"),
    ],
)
def test_classify_path(registry, path, adapter, kind, slug):
    hit = classify_path(path, registry)
    assert hit is not None
    assert (hit[0].id, hit[1].kind, hit[2]) == (adapter, kind, slug)


def test_unrelated_path_is_not_claimed(registry):
    assert classify_path("src/main.py", registry) is None
    assert classify_path("docs/readme.md", registry) is None


class TestReverseFrontmatter:
    def test_copilot_glob_all_becomes_always(self, registry):
        spec = registry["copilot"].spec(AssetKind.RULE)
        assert reverse_frontmatter({"applyTo": "**"}, spec) == {"always": True}

    def test_copilot_scoped_globs_split_on_comma(self, registry):
        spec = registry["copilot"].spec(AssetKind.RULE)
        out = reverse_frontmatter({"applyTo": "src/**, lib/**"}, spec)
        assert out == {"globs": ["src/**", "lib/**"]}

    def test_cursor_always_apply_true(self, registry):
        spec = registry["cursor"].spec(AssetKind.RULE)
        out = reverse_frontmatter({"description": "d", "alwaysApply": True}, spec)
        assert out == {"description": "d", "always": True}

    def test_cursor_default_false_carries_no_information(self, registry):
        spec = registry["cursor"].spec(AssetKind.RULE)
        out = reverse_frontmatter({"description": "d", "alwaysApply": False}, spec)
        assert "always" not in out

    def test_unknown_vendor_key_is_kept_not_lost(self, registry):
        spec = registry["cursor"].spec(AssetKind.RULE)
        out = reverse_frontmatter({"somethingNew": 7}, spec)
        assert out == {"somethingNew": 7}
