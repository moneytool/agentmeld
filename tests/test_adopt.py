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


class TestSharedConfigIsNeverMoved:
    """Found by testing a live repo: adoption moved the user's whole settings file.

    `.gemini/settings.json` is all of Gemini's settings and `.vscode/mcp.json`
    also holds the user's `inputs`. Moving either into `.ai/mcp.json` deletes
    real configuration from where the tool reads it.
    """

    def test_vscode_mcp_file_stays_put(self, repo, run_cli):
        vscode = repo / ".vscode"
        vscode.mkdir(parents=True, exist_ok=True)
        (vscode / "mcp.json").write_bytes(
            b'{"inputs": [{"id": "tok"}], "servers": {"mine": {"command": "python"}}}'
        )
        run_cli("--root", str(repo), "init", "--force")
        assert (vscode / "mcp.json").is_file(), "the user's file must not be moved away"
        assert "inputs" in (vscode / "mcp.json").read_text()

    def test_only_our_servers_are_taken(self, repo, run_cli):
        import json

        vscode = repo / ".vscode"
        vscode.mkdir(parents=True, exist_ok=True)
        (vscode / "mcp.json").write_bytes(
            b'{"inputs": [{"id": "tok"}], "servers": {"mine": {"command": "python", '
            b'"type": "stdio"}}}'
        )
        run_cli("--root", str(repo), "init", "--force")
        canonical = json.loads((repo / ".ai/mcp.json").read_text())["mcpServers"]
        assert "mine" in canonical
        assert "type" not in canonical["mine"], "vendor-shape keys should not come back"
        assert "inputs" not in canonical

    def test_a_non_json_settings_file_does_not_corrupt_canonical(self, repo, run_cli):
        """The original failure: a non-JSON file became .ai/mcp.json and every
        later command died with an unattributed decode error."""
        gemini = repo / ".gemini"
        gemini.mkdir(parents=True, exist_ok=True)
        (gemini / "settings.json").write_bytes(b"placeholder, not json\n")
        run_cli("--root", str(repo), "init", "--force")
        assert (gemini / "settings.json").read_bytes() == b"placeholder, not json\n"
        from agentmeld.cli import EXIT_OK

        assert run_cli("--root", str(repo), "sync") == EXIT_OK


class TestAdoptionRespectsConfidence:
    def test_unverified_paths_are_not_adopted_from(self, repo, run_cli):
        """Syncing skips unverified paths; adopting from them is worse, since it
        moves a file the user did not ask us to touch."""
        cursor = repo / ".cursor"
        cursor.mkdir(parents=True, exist_ok=True)
        (cursor / "mcp.json").write_bytes(b'{"mcpServers": {"unverified": {"command": "x"}}}')
        run_cli("--root", str(repo), "init", "--force")
        import json

        canonical = json.loads((repo / ".ai/mcp.json").read_text())["mcpServers"]
        assert "unverified" not in canonical

    def test_include_unverified_opts_in(self, repo, run_cli):
        import json

        cursor = repo / ".cursor"
        cursor.mkdir(parents=True, exist_ok=True)
        (cursor / "mcp.json").write_bytes(b'{"mcpServers": {"optedin": {"command": "x"}}}')
        run_cli("--root", str(repo), "init", "--force", "--include-unverified")
        canonical = json.loads((repo / ".ai/mcp.json").read_text())["mcpServers"]
        assert "optedin" in canonical


def test_bad_canonical_json_names_the_file(tmp_path):
    from pathlib import Path

    from agentmeld.model import Asset, AssetKind
    from agentmeld.transform.mcp import canonical_servers

    asset = Asset(kind=AssetKind.MCP, slug="mcp", path=Path("/repo/.ai/mcp.json"), body="nope")
    import pytest as _pytest

    with _pytest.raises(ValueError) as excinfo:
        canonical_servers(asset)
    assert "mcp.json" in str(excinfo.value), "the message must say which file to fix"
