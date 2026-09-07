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
