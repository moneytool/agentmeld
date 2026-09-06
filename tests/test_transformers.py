import json
import sys
from pathlib import Path

import pytest

from agentmeld.model import Asset, AssetKind, KindSpec, Strategy
from agentmeld.transform import GenContext, get, parse_header
from agentmeld.transform.json_merge import load_jsonc, strip_comments

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


CTX = GenContext(source=".ai/commands/x.md", source_hash="abc123", tool="t")


def command_asset(body: str, description: str = "Do a thing") -> Asset:
    return Asset(
        kind=AssetKind.COMMAND,
        slug="x",
        path=Path("/repo/.ai/commands/x.md"),
        frontmatter={"description": description},
        body=body,
    )


class TestGeminiToml:
    spec = KindSpec(
        kind=AssetKind.COMMAND,
        target=".gemini/commands/{slug}.toml",
        strategy=Strategy.GENERATE,
        transformer="gemini_command",
    )

    def _render(self, body, description="Do a thing"):
        out = get("gemini_command")(command_asset(body, description), self.spec, CTX)
        return out.decode("utf-8")

    def test_output_is_valid_toml(self):
        parsed = tomllib.loads(self._render("Summarise the diff."))
        assert parsed["prompt"].strip() == "Summarise the diff."
        assert parsed["description"] == "Do a thing"

    def test_backslashes_survive(self):
        parsed = tomllib.loads(self._render(r"Match \d+ digits"))
        assert r"\d+" in parsed["prompt"]

    def test_triple_quotes_cannot_terminate_the_block(self):
        parsed = tomllib.loads(self._render('a """ b'))
        assert '"""' in parsed["prompt"]

    def test_trailing_quote_is_escaped(self):
        parsed = tomllib.loads(self._render('ends with "'))
        assert parsed["prompt"].strip().endswith('"')

    def test_quotes_in_description_are_escaped(self):
        parsed = tomllib.loads(self._render("body", description='say "hi"'))
        assert parsed["description"] == 'say "hi"'

    def test_carries_a_provenance_header(self):
        assert parse_header(self._render("body"))["hash"] == "abc123"


class TestMcpMerge:
    asset = Asset(
        kind=AssetKind.MCP,
        slug="mcp",
        path=Path("/repo/.ai/mcp.json"),
        body='{"mcpServers": {"fs": {"command": "npx"}}}',
    )
    spec = KindSpec(kind=AssetKind.MCP, target=".vscode/mcp.json", strategy=Strategy.MERGE)

    def test_preserves_foreign_top_level_keys(self):
        existing = b'{"inputs": [{"id": "t"}], "servers": {}}'
        out = json.loads(get("mcp_servers")(self.asset, self.spec, CTX, existing))
        assert "inputs" in out

    def test_preserves_hand_added_servers(self):
        existing = b'{"servers": {"mine": {"command": "python"}}}'
        out = json.loads(get("mcp_servers")(self.asset, self.spec, CTX, existing))
        assert "mine" in out["servers"]

    def test_removes_only_previously_owned_servers(self):
        existing = b'{"servers": {"mine": {"command": "python"}, "stale": {"command": "x"}}}'
        ctx = GenContext(source="s", source_hash="h", tool="t", owned=("stale",))
        out = json.loads(get("mcp_servers")(self.asset, self.spec, ctx, existing))
        assert "stale" not in out["servers"]
        assert "mine" in out["servers"]

    def test_vscode_gets_explicit_stdio_type(self):
        out = json.loads(get("mcp_servers")(self.asset, self.spec, CTX, None))
        assert out["servers"]["fs"]["type"] == "stdio"

    def test_zed_uses_context_servers_with_source_tag(self):
        out = json.loads(get("mcp_context_servers")(self.asset, self.spec, CTX, b'{"theme": "x"}'))
        assert out["theme"] == "x"
        assert out["context_servers"]["fs"]["source"] == "custom"

    def test_claude_shape_is_passthrough(self):
        out = json.loads(get("mcp_mcp_servers")(self.asset, self.spec, CTX, None))
        assert out["mcpServers"]["fs"] == {"command": "npx"}


class TestJsonc:
    def test_line_comments_removed(self):
        data, had = load_jsonc('{\n // hi\n "a": 1\n}')
        assert data == {"a": 1} and had is True

    def test_block_comments_removed(self):
        data, had = load_jsonc('{/* x */ "a": 1}')
        assert data == {"a": 1} and had is True

    def test_slashes_inside_strings_survive(self):
        data, _ = load_jsonc('{"url": "http://x/y"}')
        assert data["url"] == "http://x/y"

    def test_trailing_commas_tolerated(self):
        data, _ = load_jsonc('{"a": [1, 2,],}')
        assert data == {"a": [1, 2]}

    def test_empty_input_is_empty_mapping(self):
        assert load_jsonc("   ") == ({}, False)

    def test_genuine_syntax_error_still_raises(self):
        with pytest.raises(ValueError):
            load_jsonc('{"a": }')
