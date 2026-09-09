"""The import strategy, per-tool overlays, and a root source of truth.

These three change what agentmeld is for. The old model assumed every tool wants
byte-identical content, which is true of a minority of real repos: of 210 public
repos carrying both AGENTS.md and CLAUDE.md, 59.5% already point one at the other
and 30.5% deliberately write different things in each. Only 5.7% keep two copies.
So the interesting cases are "point at it" and "share a base, differ on top".
"""

import os
from pathlib import Path

import pytest

from agentmeld.cli import EXIT_CONFLICT, EXIT_DRIFT, EXIT_OK

SYMLINKS = os.name != "nt"


@pytest.fixture
def agents_repo(tmp_path: Path, run_cli) -> Path:
    """The most common real shape: one root AGENTS.md, plus evidence of Claude Code."""
    (tmp_path / "AGENTS.md").write_text("# Project\n\nUse uv, never pip.\n", encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "commands").mkdir()
    (tmp_path / ".claude" / "commands" / "ship.md").write_text("Ship it.\n", encoding="utf-8")
    run_cli("--root", str(tmp_path), "init", "--force")
    return tmp_path


class TestImportStrategy:
    def test_claude_md_is_exactly_the_import_line(self, agents_repo):
        """Not a symlink, not a copy: the 11 bytes the ecosystem already writes."""
        assert (agents_repo / "CLAUDE.md").read_bytes() == b"@AGENTS.md\n"

    def test_the_import_is_a_real_file_not_a_symlink(self, agents_repo):
        """The whole point -- a symlink is what fails silently on other platforms."""
        assert not (agents_repo / "CLAUDE.md").is_symlink()
        assert (agents_repo / "CLAUDE.md").is_file()

    def test_mirrors_are_group_readable(self, agents_repo):
        """mkstemp makes 0600 files; an instruction file others cannot read is useless."""
        if os.name == "nt":
            pytest.skip("POSIX modes only")
        mode = (agents_repo / "CLAUDE.md").stat().st_mode & 0o777
        assert mode & 0o044, oct(mode)

    def test_the_source_is_never_mirrored_onto_itself(self, agents_repo, run_cli, capsys):
        """AGENTS.md is canonical here, so writing a mirror over it would be a loop."""
        before = (agents_repo / "AGENTS.md").read_bytes()
        run_cli("--root", str(agents_repo), "sync")
        assert (agents_repo / "AGENTS.md").read_bytes() == before

    def test_sync_is_idempotent(self, agents_repo, run_cli):
        assert run_cli("--root", str(agents_repo), "sync", "--check") == EXIT_OK

    def test_a_hand_written_import_is_adopted_without_a_conflict(self, tmp_path, run_cli):
        """Someone who already wrote @AGENTS.md by hand should not be fought with."""
        (tmp_path / "AGENTS.md").write_text("# P\n\nShared.\n", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        assert run_cli("--root", str(tmp_path), "init", "--force") == EXIT_OK
        assert (tmp_path / "CLAUDE.md").read_bytes() == b"@AGENTS.md\n"
        assert run_cli("--root", str(tmp_path), "sync", "--check") == EXIT_OK

    def test_a_different_hand_written_file_is_a_conflict_not_a_clobber(self, agents_repo, run_cli):
        (agents_repo / "CLAUDE.md").write_text("# Mine\n\nDo not lose this.\n", encoding="utf-8")
        assert run_cli("--root", str(agents_repo), "sync") == EXIT_CONFLICT
        assert "Do not lose this." in (agents_repo / "CLAUDE.md").read_text()

    def test_rules_reach_a_tool_that_has_no_rule_mechanism(self, agents_repo, run_cli):
        """Claude Code reads one document, so a rule must arrive below the import."""
        rules = agents_repo / ".ai" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "testing.md").write_bytes(
            b"---\ndescription: How to test\nglobs:\n  - tests/**\n---\nUse fixtures.\n"
        )
        assert run_cli("--root", str(agents_repo), "sync") == EXIT_OK
        text = (agents_repo / "CLAUDE.md").read_text()
        assert text.splitlines()[0] == "@AGENTS.md"
        assert "Use fixtures." in text
        assert "tests/**" in text

    def test_import_path_is_relative_to_the_importing_file(self):
        """@ imports resolve from the importing file's directory, not the repo root."""
        from agentmeld.planner import _import_path

        root = Path("/repo")
        assert _import_path(root / "AGENTS.md", root / "CLAUDE.md") == "AGENTS.md"
        assert (
            _import_path(root / "AGENTS.md", root / ".github" / "copilot-instructions.md")
            == "../AGENTS.md"
        )


class TestOverlays:
    def test_an_overlay_reaches_only_its_own_tool(self, agents_repo, run_cli):
        overlays = agents_repo / ".ai" / "overlays"
        overlays.mkdir(parents=True, exist_ok=True)
        (overlays / "claude.md").write_text("Use `claude --resume`.\n", encoding="utf-8")
        assert run_cli("--root", str(agents_repo), "sync") == EXIT_OK

        claude = (agents_repo / "CLAUDE.md").read_text()
        assert "claude --resume" in claude
        assert claude.splitlines()[0] == "@AGENTS.md", "the shared base is still imported"
        assert "claude --resume" not in (agents_repo / "AGENTS.md").read_text(), (
            "tool-specific content must not leak into the shared source"
        )

    def test_editing_an_overlay_is_drift(self, agents_repo, run_cli):
        overlays = agents_repo / ".ai" / "overlays"
        overlays.mkdir(parents=True, exist_ok=True)
        (overlays / "claude.md").write_text("First.\n", encoding="utf-8")
        run_cli("--root", str(agents_repo), "sync")
        (overlays / "claude.md").write_text("Second.\n", encoding="utf-8")
        assert run_cli("--root", str(agents_repo), "sync", "--check") == EXIT_DRIFT

    def test_overlays_are_idempotent(self, agents_repo, run_cli):
        overlays = agents_repo / ".ai" / "overlays"
        overlays.mkdir(parents=True, exist_ok=True)
        (overlays / "claude.md").write_text("Stable.\n", encoding="utf-8")
        run_cli("--root", str(agents_repo), "sync")
        first = (agents_repo / "CLAUDE.md").read_bytes()
        run_cli("--root", str(agents_repo), "sync")
        assert (agents_repo / "CLAUDE.md").read_bytes() == first

    @pytest.mark.skipif(not SYMLINKS, reason="symlinks unavailable on this platform")
    def test_an_overlay_forces_a_real_file_instead_of_a_symlink(self, tidy_repo, run_cli):
        """A symlink cannot carry per-tool content, so it has to stop being one."""
        run_cli("--root", str(tidy_repo), "init")
        assert (tidy_repo / "GEMINI.md").is_symlink()
        overlays = tidy_repo / ".ai" / "overlays"
        overlays.mkdir(parents=True, exist_ok=True)
        (overlays / "gemini.md").write_text("Gemini only.\n", encoding="utf-8")
        assert run_cli("--root", str(tidy_repo), "sync") == EXIT_OK
        assert not (tidy_repo / "GEMINI.md").is_symlink()
        assert "Gemini only." in (tidy_repo / "GEMINI.md").read_text()


class TestRootCanonical:
    def test_an_existing_agents_md_is_not_moved(self, tmp_path, run_cli):
        """The common case must cost nothing: no migration, no new directory for it."""
        (tmp_path / "AGENTS.md").write_text("# Keep me here\n", encoding="utf-8")
        run_cli("--root", str(tmp_path), "init", "--force")
        assert (tmp_path / "AGENTS.md").read_text() == "# Keep me here\n"
        assert not (tmp_path / ".ai" / "instructions.md").exists()

    def test_detection_ignores_agentmeld_s_own_output(self, tmp_path, run_cli):
        """Regression: a generated AGENTS.md was adopted as canonical on the next run,
        moving the source of truth between runs and breaking idempotence."""
        (tmp_path / "CLAUDE.md").write_text("# Only Claude\n\nShared.\n", encoding="utf-8")
        run_cli("--root", str(tmp_path), "init", "--force")
        first = (tmp_path / "AGENTS.md").read_bytes()
        for _ in range(3):
            assert run_cli("--root", str(tmp_path), "sync") == EXIT_OK
        assert (tmp_path / "AGENTS.md").read_bytes() == first

    def test_an_explicit_instructions_path_is_respected(self, tmp_path, run_cli):
        """Pinning the source of truth elsewhere must beat auto-detection."""
        (tmp_path / ".ai").mkdir()
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "commands").mkdir()
        (tmp_path / ".claude" / "commands" / "ship.md").write_text("Ship.\n", encoding="utf-8")
        (tmp_path / ".ai" / "docs.md").write_text("# Elsewhere\n", encoding="utf-8")
        (tmp_path / ".ai" / "agentmeld.toml").write_text(
            '[agentmeld]\ninstructions = ".ai/docs.md"\n', encoding="utf-8"
        )
        assert run_cli("--root", str(tmp_path), "sync") == EXIT_OK
        assert (tmp_path / "CLAUDE.md").read_text().strip() == "@.ai/docs.md"


class TestAdapterSchema:
    def test_import_without_an_import_line_is_rejected(self):
        from agentmeld.registry.schema import AdapterSchemaError, parse_adapter

        data = {
            "id": "x",
            "name": "X",
            "confidence": "verified",
            "kinds": {"instructions": {"target": "X.md", "strategy": "import"}},
        }
        with pytest.raises(AdapterSchemaError, match="import_line"):
            parse_adapter(data, "x.toml")

    def test_an_import_line_without_a_path_placeholder_is_rejected(self):
        from agentmeld.registry.schema import AdapterSchemaError, parse_adapter

        data = {
            "id": "x",
            "name": "X",
            "confidence": "verified",
            "kinds": {
                "instructions": {
                    "target": "X.md",
                    "strategy": "import",
                    "import_line": "@AGENTS.md",
                }
            },
        }
        with pytest.raises(AdapterSchemaError, match=r"\{path\}"):
            parse_adapter(data, "x.toml")

    def test_an_import_line_on_another_strategy_is_rejected(self):
        """Silently ignoring it would let an adapter look right and do nothing."""
        from agentmeld.registry.schema import AdapterSchemaError, parse_adapter

        data = {
            "id": "x",
            "name": "X",
            "confidence": "verified",
            "kinds": {
                "instructions": {
                    "target": "X.md",
                    "strategy": "link",
                    "import_line": "@{path}",
                }
            },
        }
        with pytest.raises(AdapterSchemaError, match="only means something"):
            parse_adapter(data, "x.toml")


class TestUpgradesFromOlderLayouts:
    """An existing install must not have its source of truth moved underneath it."""

    def test_an_existing_canonical_instructions_file_stays_canonical(self, tmp_path, run_cli):
        (tmp_path / ".ai").mkdir()
        (tmp_path / ".ai" / "agentmeld.toml").write_text(
            '[agentmeld]\ncanonical_dir = ".ai"\n', encoding="utf-8"
        )
        (tmp_path / ".ai" / "instructions.md").write_text("# Canonical\n", encoding="utf-8")
        # A copy-mode mirror: a real file, no header, indistinguishable by content
        # alone from something a person wrote.
        (tmp_path / "AGENTS.md").write_text("# Canonical\n", encoding="utf-8")

        from agentmeld.config import load_config

        assert load_config(tmp_path).instructions_rel == ".ai/instructions.md"

    def test_a_fresh_repo_still_auto_detects_the_root_file(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Authored\n", encoding="utf-8")

        from agentmeld.config import load_config

        assert load_config(tmp_path).instructions_rel == "AGENTS.md"
