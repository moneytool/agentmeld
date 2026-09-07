"""Integration tests: real repos on disk, driven through the CLI."""

import json
import os
from pathlib import Path

import pytest

from agentmeld.cli import EXIT_CONFLICT, EXIT_DRIFT, EXIT_OK

SYMLINKS = os.name != "nt"


def hashes(root: Path) -> dict:
    """Content of every regular file, so idempotence can be asserted on bytes."""
    out = {}
    for path in sorted(root.rglob("*")):
        if any(p in (".git", ".backup") for p in path.parts):
            continue
        if path.name == ".state.json":
            continue  # our own bookkeeping, expected to change
        if path.is_file() and not path.is_symlink():
            out[str(path.relative_to(root))] = path.read_bytes()
    return out


class TestInit:
    def test_adopts_existing_config_into_canonical(self, repo, run_cli):
        assert run_cli("--root", str(repo), "init") == EXIT_OK
        assert (repo / ".ai/instructions.md").is_file()
        assert (repo / ".ai/rules/testing.md").is_file()
        assert (repo / ".ai/skills/deploy/SKILL.md").is_file()
        assert (repo / ".ai/mcp.json").is_file()
        assert (repo / ".ai/agentmeld.toml").is_file()

    def test_backs_up_before_moving_anything(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        backups = list((repo / ".ai/.backup").glob("*/CLAUDE.md"))
        assert backups, "originals must be recoverable"
        assert "Run tests with pytest" in backups[0].read_text()

    def test_refuses_to_migrate_a_dirty_worktree(self, repo, run_cli):
        (repo / "dirty.txt").write_text("uncommitted\n")
        assert run_cli("--root", str(repo), "init") != EXIT_OK
        assert not (repo / ".ai/instructions.md").exists()

    def test_force_overrides_the_dirty_check(self, repo, run_cli):
        (repo / "dirty.txt").write_text("uncommitted\n")
        assert run_cli("--root", str(repo), "init", "--force") == EXIT_OK

    def test_dry_run_writes_nothing(self, repo, run_cli):
        run_cli("--root", str(repo), "init", "--dry-run")
        assert not (repo / ".ai").exists()

    def test_second_init_is_a_no_op(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        assert run_cli("--root", str(repo), "init") == EXIT_OK

    def test_leaves_no_conflicts_behind(self, repo, run_cli):
        """A freshly migrated repo must be fully in sync, with nothing refused."""
        assert run_cli("--root", str(repo), "init") == EXIT_OK
        assert run_cli("--root", str(repo), "sync", "--check") == EXIT_OK

    def test_migration_keeps_mirroring_to_every_tool_it_found(self, repo, run_cli):
        """init moves the files that prove a tool is in use; it must not forget them."""
        run_cli("--root", str(repo), "init")
        assert (repo / ".github/copilot-instructions.md").exists()
        assert (repo / ".github/instructions/testing.instructions.md").exists()


class TestSync:
    @pytest.fixture
    def initialised(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        return repo

    def test_is_idempotent_to_the_byte(self, initialised, run_cli):
        before = hashes(initialised)
        run_cli("--root", str(initialised), "sync")
        assert hashes(initialised) == before

    def test_check_passes_on_a_clean_tree(self, initialised, run_cli):
        assert run_cli("--root", str(initialised), "sync", "--check") == EXIT_OK

    def test_check_reports_drift(self, initialised, run_cli):
        (initialised / ".ai/instructions.md").write_text("# changed\n", encoding="utf-8")
        assert run_cli("--root", str(initialised), "sync", "--check") == EXIT_DRIFT

    def test_check_writes_nothing(self, initialised, run_cli):
        (initialised / ".ai/instructions.md").write_text("# changed\n", encoding="utf-8")
        before = hashes(initialised)
        run_cli("--root", str(initialised), "sync", "--check")
        assert hashes(initialised) == before

    def test_copilot_rule_uses_apply_to(self, initialised):
        text = (initialised / ".github/instructions/testing.instructions.md").read_text()
        assert "applyTo: tests/**" in text
        assert "globs" not in text

    def test_cursor_rule_uses_mdc_vocabulary(self, initialised):
        text = (initialised / ".cursor/rules/testing.mdc").read_text()
        assert "alwaysApply: false" in text
        assert "globs" in text

    def test_rules_fold_into_claude_md(self, initialised):
        """Claude has no per-file rule mechanism, so the rule must appear inline."""
        text = (initialised / "CLAUDE.md").read_text()
        assert "Use fixtures, not setUp." in text
        assert "tests/**" in text

    def test_mcp_is_translated_per_vendor_schema(self, initialised):
        assert "mcpServers" in json.loads((initialised / ".mcp.json").read_text())
        assert "servers" in json.loads((initialised / ".vscode/mcp.json").read_text())

    def test_generated_files_are_marked_as_generated(self, initialised):
        text = (initialised / ".cursor/rules/testing.mdc").read_text()
        assert "agentmeld:generated" in text

    def test_never_writes_inside_the_canonical_tree(self, initialised, run_cli):
        before = hashes(initialised / ".ai")
        run_cli("--root", str(initialised), "sync")
        assert hashes(initialised / ".ai") == before

    def test_state_records_vendor_paths_not_canonical_ones(self, initialised):
        state = json.loads((initialised / ".ai/.state.json").read_text())
        assert state["entries"]
        assert not [k for k in state["entries"] if k.startswith(".ai/")]

    def test_deleting_a_rule_removes_its_mirrors(self, initialised, run_cli):
        mirror = initialised / ".cursor/rules/testing.mdc"
        assert mirror.exists()
        (initialised / ".ai/rules/testing.md").unlink()
        run_cli("--root", str(initialised), "sync")
        assert not mirror.exists()


@pytest.mark.skipif(not SYMLINKS, reason="symlinks unavailable on this platform")
class TestSymlinkMode:
    @pytest.fixture
    def initialised(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        return repo

    def test_instruction_mirror_is_a_symlink(self, initialised):
        assert (initialised / ".github/copilot-instructions.md").is_symlink()

    def test_editing_a_mirror_edits_the_canonical_file(self, initialised):
        """The whole point: one inode, not two copies."""
        mirror = initialised / ".github/copilot-instructions.md"
        with mirror.open("a", encoding="utf-8") as handle:
            handle.write("\nAdded via the mirror.\n")
        assert "Added via the mirror." in (initialised / ".ai/instructions.md").read_text()

    def test_skill_directory_is_linked_whole_so_sidecars_ride_along(self, initialised):
        link = initialised / ".claude/skills/deploy"
        assert link.is_symlink()
        assert (link / "notes.md").is_file()

    def test_symlinks_are_relative_so_the_repo_can_move(self, initialised):
        target = os.readlink(str(initialised / ".github/copilot-instructions.md"))
        assert not os.path.isabs(target)


class TestCopyMode:
    def test_produces_real_files_and_no_symlinks(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "sync", "--mode", "copy")
        leftovers = [p for p in repo.rglob("*") if p.is_symlink() and ".git" not in p.parts]
        assert leftovers == []

    def test_is_idempotent(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "sync", "--mode", "copy")
        before = hashes(repo)
        run_cli("--root", str(repo), "sync", "--mode", "copy")
        assert hashes(repo) == before

    def test_leaves_the_canonical_tree_untouched(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        before = hashes(repo / ".ai")
        run_cli("--root", str(repo), "sync", "--mode", "copy")
        assert hashes(repo / ".ai") == before


class TestConflicts:
    def test_hand_written_file_is_not_overwritten(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        mirror = repo / ".cursor/rules/testing.mdc"
        mirror.unlink()
        mirror.write_text("---\ndescription: mine\n---\nHand written.\n", encoding="utf-8")
        assert run_cli("--root", str(repo), "sync") == EXIT_CONFLICT
        assert "Hand written." in mirror.read_text()

    def test_conflict_is_reported_with_a_reason(self, repo, run_cli, capsys):
        run_cli("--root", str(repo), "init")
        mirror = repo / ".cursor/rules/testing.mdc"
        mirror.unlink()
        mirror.write_text("mine\n", encoding="utf-8")
        run_cli("--root", str(repo), "sync")
        assert "refusing to overwrite" in capsys.readouterr().out


class TestReverseAdoption:
    """The behaviour the existing tools do not automate."""

    @pytest.fixture
    def initialised(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        return repo

    def _agent_written_by_an_ai(self, repo):
        path = repo / ".claude/agents/reviewer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\nname: reviewer\ndescription: Reviews diffs\ntools: Read, Grep\n---\n"
            "Review carefully.\n",
            encoding="utf-8",
        )
        return path

    def test_new_vendor_file_becomes_canonical(self, initialised, run_cli):
        self._agent_written_by_an_ai(initialised)
        run_cli("--root", str(initialised), "sync", "--adopt")
        canonical = initialised / ".ai/agents/reviewer.md"
        assert canonical.is_file()
        assert "Review carefully." in canonical.read_text()

    def test_comma_tools_become_a_canonical_list(self, initialised, run_cli):
        self._agent_written_by_an_ai(initialised)
        run_cli("--root", str(initialised), "sync", "--adopt")
        from agentmeld.transform.frontmatter import split

        front, _ = split((initialised / ".ai/agents/reviewer.md").read_text())
        assert front["tools"] == ["Read", "Grep"]

    def test_provenance_is_recorded(self, initialised, run_cli):
        self._agent_written_by_an_ai(initialised)
        run_cli("--root", str(initialised), "sync", "--adopt")
        state = json.loads((initialised / ".ai/.state.json").read_text())
        assert state["provenance"][".ai/agents/reviewer.md"]["adopted_from"] == (
            ".claude/agents/reviewer.md"
        )

    def test_adopted_command_fans_out_to_other_tools(self, initialised, run_cli):
        path = initialised / ".claude/commands/summarise.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ndescription: Summarise\n---\nSummarise it.\n", encoding="utf-8")
        run_cli("--root", str(initialised), "sync", "--adopt")
        assert (initialised / ".github/prompts/summarise.prompt.md").is_file()

    def test_adoption_reaches_quiescence(self, initialised, run_cli):
        """Adopting must not oscillate: the second pass changes nothing."""
        self._agent_written_by_an_ai(initialised)
        run_cli("--root", str(initialised), "sync", "--adopt")
        before = hashes(initialised)
        run_cli("--root", str(initialised), "sync", "--adopt")
        assert hashes(initialised) == before
        assert run_cli("--root", str(initialised), "sync", "--check") == EXIT_OK

    def test_our_own_mirrors_are_never_adopted(self, initialised, run_cli):
        run_cli("--root", str(initialised), "sync", "--adopt")
        assert not (initialised / ".ai/rules/testing.instructions.md").exists()
        assert not (initialised / ".ai/instructions/instructions.md").exists()


class TestUnverifiedGating:
    def test_unverified_paths_are_skipped_by_default(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        assert not (repo / ".cursor/mcp.json").exists()

    def test_include_unverified_writes_them(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "sync", "--include-unverified")
        assert (repo / ".cursor/mcp.json").is_file()


class TestHooks:
    def test_installs_a_claude_post_tool_use_hook(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "install-hooks", "--kind", "claude")
        settings = json.loads((repo / ".claude/settings.json").read_text())
        commands = [
            hook["command"]
            for group in settings["hooks"]["PostToolUse"]
            for hook in group["hooks"]
        ]
        assert any("agentmeld sync" in c for c in commands)

    def test_preserves_unrelated_settings(self, repo, run_cli):
        settings = repo / ".claude/settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"model": "opus", "hooks": {}}', encoding="utf-8")
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "install-hooks", "--kind", "claude")
        assert json.loads(settings.read_text())["model"] == "opus"

    def test_installing_twice_does_not_duplicate(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "install-hooks", "--kind", "claude")
        run_cli("--root", str(repo), "install-hooks", "--kind", "claude")
        settings = json.loads((repo / ".claude/settings.json").read_text())
        assert len(settings["hooks"]["PostToolUse"]) == 1

    def test_git_pre_commit_hook_is_executable(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "install-hooks", "--kind", "git")
        hook = repo / ".git/hooks/pre-commit"
        assert hook.is_file()
        if os.name != "nt":
            assert os.access(str(hook), os.X_OK)

    def test_does_not_clobber_an_existing_pre_commit_hook(self, repo, run_cli):
        hook = repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "install-hooks", "--kind", "git")
        assert "echo mine" in hook.read_text()


class TestCliSurface:
    def test_detect_finds_the_three_tools(self, repo, run_cli, capsys):
        run_cli("--root", str(repo), "detect")
        out = capsys.readouterr().out
        assert "claude" in out and "copilot" in out and "cursor" in out

    def test_detect_ignores_files_we_created(self, repo, run_cli, capsys):
        """Otherwise the tool becomes self-confirming after the first sync."""
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "detect")
        assert "gemini" not in capsys.readouterr().out

    def test_doctor_runs_on_an_initialised_repo(self, repo, run_cli, capsys):
        run_cli("--root", str(repo), "init")
        run_cli("--root", str(repo), "doctor")
        out = capsys.readouterr().out
        assert "environment" in out and "canonical assets" in out

    def test_doctor_reports_dropped_keys(self, repo, run_cli, capsys):
        run_cli("--root", str(repo), "init")
        rule = repo / ".ai/rules/testing.md"
        rule.write_text(
            "---\ndescription: d\nglobs:\n  - tests/**\nmodel: opus\n---\nBody\n",
            encoding="utf-8",
        )
        run_cli("--root", str(repo), "sync")
        run_cli("--root", str(repo), "doctor")
        assert "dropped in translation" in capsys.readouterr().out

    def test_sync_without_init_is_a_clear_error(self, repo, run_cli, capsys):
        run_cli("--root", str(repo), "sync")
        assert "agentmeld init" in capsys.readouterr().out


class TestStrategyTransitions:
    """A repo's shape changes over time; mirrors must follow without conflicting."""

    def test_link_becomes_aggregate_when_the_first_rule_appears(self, repo, run_cli):
        """Found by running agentmeld on its own repo."""
        run_cli("--root", str(repo), "init")
        # Remove the fixture's rule so instructions start life as a plain symlink.
        (repo / ".ai/rules/testing.md").unlink()
        run_cli("--root", str(repo), "sync")
        assert (repo / "AGENTS.md").is_symlink()

        (repo / ".ai/rules").mkdir(exist_ok=True)
        (repo / ".ai/rules/new.md").write_bytes(
            b"---\ndescription: A new rule\nglobs:\n  - src/**\n---\nDo the thing.\n"
        )
        assert run_cli("--root", str(repo), "sync") == EXIT_OK
        assert not (repo / "AGENTS.md").is_symlink()
        assert "Do the thing." in (repo / "AGENTS.md").read_text()
        assert run_cli("--root", str(repo), "sync", "--check") == EXIT_OK

    def test_aggregate_becomes_link_when_the_last_rule_goes(self, repo, run_cli):
        run_cli("--root", str(repo), "init")
        assert not (repo / "AGENTS.md").is_symlink()  # fixture has a rule
        (repo / ".ai/rules/testing.md").unlink()
        assert run_cli("--root", str(repo), "sync") == EXIT_OK
        assert (repo / "AGENTS.md").is_symlink()

    def test_editing_a_mirror_and_stripping_the_header_is_a_conflict(self, repo, run_cli):
        """Recorded as ours is not the same as unmodified -- do not discard edits."""
        run_cli("--root", str(repo), "init")
        mirror = repo / ".cursor/rules/testing.mdc"
        mirror.write_bytes(b"---\ndescription: x\n---\nhand edited, header removed\n")
        assert run_cli("--root", str(repo), "sync") == EXIT_CONFLICT
        assert "hand edited" in mirror.read_text()

    def test_a_stale_but_untouched_mirror_is_rewritten(self, repo, run_cli):
        """Still byte-identical to our last output, so the source simply moved on."""
        run_cli("--root", str(repo), "init")
        (repo / ".ai/rules/testing.md").write_bytes(
            b"---\ndescription: How to test\nglobs:\n  - tests/**\n---\nUpdated body.\n"
        )
        assert run_cli("--root", str(repo), "sync") == EXIT_OK
        assert "Updated body." in (repo / ".cursor/rules/testing.mdc").read_text()


def test_probing_symlink_support_leaves_nothing_behind(repo):
    """Checking a capability must not litter someone's repo."""
    from agentmeld.linker import probe_symlink_support

    before = {p.name for p in repo.iterdir()}
    probe_symlink_support(repo)
    assert {p.name for p in repo.iterdir()} == before


class TestRootFlagPositions:
    """`agentmeld init --root .` is what people type; it must not error."""

    def test_root_before_the_subcommand(self, repo, run_cli):
        assert run_cli("--root", str(repo), "init", "--dry-run") == EXIT_OK

    def test_root_after_the_subcommand(self, repo, run_cli):
        assert run_cli("init", "--dry-run", "--root", str(repo)) == EXIT_OK

    def test_root_after_the_subcommand_actually_targets_that_repo(self, repo, run_cli):
        assert run_cli("init", "--root", str(repo)) == EXIT_OK
        assert (repo / ".ai/instructions.md").is_file()
