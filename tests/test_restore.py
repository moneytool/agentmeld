"""Getting back out must actually work.

A tool that moves your files and cannot put them back is one people are right to
refuse to try.
"""

import json
import os

import pytest

from agentmeld.cli import EXIT_OK

SYMLINKS = os.name != "nt"


@pytest.fixture
def initialised(repo, run_cli):
    run_cli("--root", str(repo), "init")
    return repo


class TestEject:
    def test_mirrors_become_real_files(self, initialised, run_cli):
        mirror = initialised / ".github/copilot-instructions.md"
        assert run_cli("--root", str(initialised), "restore") == EXIT_OK
        assert not mirror.is_symlink()
        assert mirror.is_file()

    def test_content_survives(self, initialised, run_cli):
        expected = (initialised / ".ai/instructions.md").read_text()
        run_cli("--root", str(initialised), "restore")
        assert (initialised / ".github/copilot-instructions.md").read_text() == expected

    @pytest.mark.skipif(not SYMLINKS, reason="symlinks unavailable")
    def test_skill_directory_becomes_a_real_directory_with_sidecars(
        self, initialised, run_cli
    ):
        run_cli("--root", str(initialised), "restore")
        skill = initialised / ".claude/skills/deploy"
        assert not skill.is_symlink()
        assert (skill / "SKILL.md").is_file()
        assert (skill / "notes.md").is_file(), "sidecars must come along"

    def test_every_tool_still_has_its_config(self, initialised, run_cli):
        run_cli("--root", str(initialised), "restore")
        for path in (
            "CLAUDE.md",
            "AGENTS.md",
            ".github/copilot-instructions.md",
            ".cursor/rules/testing.mdc",
        ):
            assert (initialised / path).is_file(), path

    def test_state_is_removed(self, initialised, run_cli):
        run_cli("--root", str(initialised), "restore")
        assert not (initialised / ".ai/.state.json").exists()

    def test_canonical_tree_is_left_alone(self, initialised, run_cli):
        """Deleting someone's source of truth on their behalf would be rude."""
        run_cli("--root", str(initialised), "restore")
        assert (initialised / ".ai/instructions.md").is_file()

    def test_dry_run_changes_nothing(self, initialised, run_cli):
        mirror = initialised / ".github/copilot-instructions.md"
        was_link = mirror.is_symlink()
        run_cli("--root", str(initialised), "restore", "--dry-run")
        assert mirror.is_symlink() == was_link
        assert (initialised / ".ai/.state.json").exists()


class TestHookRemoval:
    def test_claude_hook_is_removed(self, initialised, run_cli):
        run_cli("--root", str(initialised), "install-hooks", "--kind", "claude")
        run_cli("--root", str(initialised), "restore")
        settings = json.loads((initialised / ".claude/settings.json").read_text())
        commands = [
            hook.get("command", "")
            for group in settings.get("hooks", {}).get("PostToolUse", [])
            for hook in group.get("hooks", [])
        ]
        assert not any("agentmeld" in c for c in commands)

    def test_unrelated_settings_survive(self, initialised, run_cli):
        settings = initialised / ".claude/settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_bytes(b'{"model": "opus"}')
        run_cli("--root", str(initialised), "install-hooks", "--kind", "claude")
        run_cli("--root", str(initialised), "restore")
        assert json.loads(settings.read_text())["model"] == "opus"

    def test_keep_hooks_leaves_them(self, initialised, run_cli):
        run_cli("--root", str(initialised), "install-hooks", "--kind", "claude")
        run_cli("--root", str(initialised), "restore", "--keep-hooks")
        settings = json.loads((initialised / ".claude/settings.json").read_text())
        assert settings["hooks"]["PostToolUse"]


class TestRestoreFromBackup:
    def test_original_file_comes_back_byte_for_byte(self, repo, run_cli):
        before = (repo / "CLAUDE.md").read_bytes()
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "restore", "--from-backup")
        assert (repo / "CLAUDE.md").read_bytes() == before

    def test_the_drifted_copy_comes_back_too(self, repo, run_cli):
        """init deletes superseded originals; restore must undo that."""
        before = (repo / ".github/copilot-instructions.md").read_bytes()
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "restore", "--from-backup")
        assert (repo / ".github/copilot-instructions.md").read_bytes() == before

    def test_files_we_invented_are_removed(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        invented = repo / ".github/instructions/testing.instructions.md"
        assert invented.exists()
        run_cli("--root", str(repo), "restore", "--from-backup")
        assert not invented.exists()

    def test_unknown_backup_is_an_error(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        assert run_cli("--root", str(repo), "restore", "--from-backup", "nope") != EXIT_OK

    def test_dry_run_changes_nothing(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        invented = repo / ".github/instructions/testing.instructions.md"
        run_cli("--root", str(repo), "restore", "--from-backup", "--dry-run")
        assert invented.exists()


def test_restore_without_a_canonical_tree_is_a_clear_error(repo, run_cli):
    assert run_cli("--root", str(repo), "restore") != EXIT_OK


class TestJsoncCommentWarning:
    def test_comment_loss_is_reported(self, repo, run_cli, capsys):
        """We can parse comments but not preserve them; say so rather than delete quietly."""
        vscode = repo / ".vscode"
        vscode.mkdir(parents=True, exist_ok=True)
        (vscode / "mcp.json").write_bytes(
            b'{\n  // a note the user wrote\n  "servers": {}\n}'
        )
        run_cli("--root", str(repo), "init", "--force")  # the new file dirties the tree
        assert "comments" in capsys.readouterr().out.lower()


class TestHookRemovalPrecision:
    """Reported by Copilot on PR #4: substring matching deleted user hooks."""

    def _settings(self, repo, groups):
        path = repo / ".claude/settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps({"hooks": {"PostToolUse": groups}}).encode())
        return path

    def test_a_user_hook_that_calls_agentmeld_survives(self, initialised, run_cli):
        from agentmeld.hooks import HOOK_COMMAND

        path = self._settings(
            initialised,
            [
                {"matcher": "Write", "hooks": [{"type": "command", "command": HOOK_COMMAND}]},
                {"matcher": "Edit", "hooks": [{"type": "command", "command": "agentmeld doctor"}]},
            ],
        )
        run_cli("--root", str(initialised), "restore")
        remaining = [
            h["command"]
            for g in json.loads(path.read_text())["hooks"]["PostToolUse"]
            for h in g["hooks"]
        ]
        assert remaining == ["agentmeld doctor"]

    def test_a_hook_merely_mentioning_agentmeld_survives(self, initialised, run_cli):
        path = self._settings(
            initialised,
            [{"matcher": "Write", "hooks": [{"type": "command", "command": "echo agentmeld"}]}],
        )
        run_cli("--root", str(initialised), "restore")
        assert json.loads(path.read_text())["hooks"]["PostToolUse"]

    def test_a_command_installed_by_an_older_version_is_still_cleaned_up(
        self, initialised, run_cli
    ):
        path = self._settings(
            initialised,
            [{"matcher": "Write", "hooks": [{"type": "command", "command": "agentmeld sync --quiet"}]}],
        )
        run_cli("--root", str(initialised), "restore")
        assert not json.loads(path.read_text()).get("hooks", {}).get("PostToolUse")


class TestPreCommitBlockRemoval:
    def test_user_additions_below_our_block_survive(self, initialised, run_cli):
        hook = initialised / ".git/hooks/pre-commit"
        run_cli("--root", str(initialised), "install-hooks", "--kind", "git")
        with hook.open("a", encoding="utf-8") as handle:
            handle.write('\necho "my own check"\n')
        run_cli("--root", str(initialised), "restore")
        assert hook.is_file()
        text = hook.read_text()
        assert "my own check" in text
        assert "agentmeld" not in text

    def test_a_hook_that_is_only_ours_is_deleted(self, initialised, run_cli):
        run_cli("--root", str(initialised), "install-hooks", "--kind", "git")
        run_cli("--root", str(initialised), "restore")
        assert not (initialised / ".git/hooks/pre-commit").exists()

    def test_the_0_1_0_hook_layout_is_still_removable(self, initialised, run_cli):
        """Upgrades must be able to clean up what an older release wrote."""
        hook = initialised / ".git/hooks/pre-commit"
        hook.write_bytes(
            b"#!/bin/sh\n# agentmeld -- keep AI config mirrors in sync\n"
            b"if command -v agentmeld >/dev/null 2>&1; then\n"
            b"    agentmeld sync --quiet || exit 1\n"
            b"fi\n"
            b'echo "mine"\n'
        )
        run_cli("--root", str(initialised), "restore")
        text = hook.read_text()
        assert "mine" in text
        assert "agentmeld" not in text


class TestCommentWarningHasNoSharedState:
    """Reported by Copilot on PR #4: a module-level set leaked between runs."""

    def test_warning_does_not_persist_into_a_later_plan(self, repo, run_cli):
        from agentmeld.config import discover_assets, load_config
        from agentmeld.planner import build_plan, select_adapters
        from agentmeld.registry import load_registry
        from agentmeld.state import State

        vscode = repo / ".vscode"
        vscode.mkdir(parents=True, exist_ok=True)
        (vscode / "mcp.json").write_bytes(b'{\n  // note\n  "servers": {}\n}')
        run_cli("--root", str(repo), "init", "--force")

        config = load_config(repo)
        registry = load_registry()
        state = State.load(config.state_path)
        assets = discover_assets(config)
        adapters = select_adapters(registry, config, state, None)

        first = build_plan(config, assets, adapters, state, "link")
        assert not any("comment" in w.lower() for w in first.warnings), (
            "comments are gone after the first sync, so nothing should warn now"
        )
        second = build_plan(config, assets, adapters, state, "link")
        assert first.warnings == second.warnings, "plan building must not accumulate state"

    def test_has_comments_is_a_pure_query(self):
        from agentmeld.transform.mcp import has_comments

        assert has_comments(b'{\n // hi\n "a": 1\n}')
        assert not has_comments(b'{"a": 1}')
        assert not has_comments(None)
        assert not has_comments(b"not json at all {{{")
