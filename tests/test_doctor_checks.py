"""Diagnostics for the failures that actually happen in public repos.

The symlink checks are here because of a measurement: in a sample of 210 public
repos carrying both AGENTS.md and CLAUDE.md, 67 use a symlink and three of them
have already been silently corrupted -- one serialised by CIFS into an ``XSym``
text blob, two committed as a plain file whose whole body is the word
``AGENTS.md``. In every case the tool reads the pointer as its instructions and
follows nothing, and the person who caused it cannot see the problem, because on
their machine the symlink works.
"""

import os

import pytest

SYMLINKS = os.name != "nt"


def doctor(root, run_cli, capsys):
    run_cli("--root", str(root), "doctor")
    return capsys.readouterr().out


@pytest.fixture
def initialised(repo, run_cli):
    run_cli("--root", str(repo), "init")
    return repo


class TestSerialisedSymlinks:
    def test_cifs_xsym_pointer_is_reported(self, initialised, run_cli, capsys):
        """CIFS writes a symlink as 'XSym', a length, an md5 and the target."""
        (initialised / "CLAUDE.md").write_bytes(
            b"XSym\n0009\nbc5441b46c60dc9086061eb9793d0283\nAGENTS.md\n" + b"\x00" * 1013
        )
        out = doctor(initialised, run_cli, capsys)
        assert "broken pointer files" in out
        assert "CLAUDE.md" in out
        assert "loads nothing" in out

    def test_a_body_that_is_only_a_path_is_reported(self, initialised, run_cli, capsys):
        """A POSIX symlink checked out with core.symlinks=false looks exactly like this."""
        (initialised / "CLAUDE.md").write_bytes(b"AGENTS.md")
        out = doctor(initialised, run_cli, capsys)
        assert "broken pointer files" in out
        assert "CLAUDE.md" in out

    def test_a_real_import_is_not_reported(self, initialised, run_cli, capsys):
        """@AGENTS.md is the fix, not the bug -- flagging it would be noise."""
        (initialised / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
        out = doctor(initialised, run_cli, capsys)
        assert "broken pointer files" not in out

    def test_a_normal_instruction_file_is_not_reported(self, initialised, run_cli, capsys):
        out = doctor(initialised, run_cli, capsys)
        assert "broken pointer files" not in out

    def test_detection_is_unit_testable(self):
        from agentmeld.doctor import _looks_like_a_serialised_link as broken

        assert broken("XSym\n0009\nabc\nAGENTS.md\n")
        assert broken("AGENTS.md")
        assert broken("../AGENTS.md\n")
        assert broken("docs/CONTEXT.md\n")
        assert broken("AGENTS.md\n" + "\x00" * 100)
        assert not broken("@AGENTS.md\n")
        assert not broken("# Project\n\nUse uv.\n")
        assert not broken("")
        assert not broken("See AGENTS.md for details.\n")


class TestSilentlyIgnoredFiles:
    def test_a_md_rule_inside_cursor_rules_is_reported(self, initialised, run_cli, capsys):
        """Cursor reads only .mdc there, and ignores .md with no error at all."""
        rules = initialised / ".cursor" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "style.md").write_text("Use tabs.\n", encoding="utf-8")
        out = doctor(initialised, run_cli, capsys)
        assert "files the tool will ignore" in out
        assert "style.md" in out
        assert ".mdc" in out

    def test_the_mdc_files_we_generate_are_not_reported(self, initialised, run_cli, capsys):
        out = doctor(initialised, run_cli, capsys)
        assert "files the tool will ignore" not in out


@pytest.mark.skipif(not SYMLINKS, reason="symlinks unavailable on this platform")
class TestPortability:
    def test_symlink_mirrors_are_called_out(self, tidy_repo, run_cli, capsys):
        run_cli("--root", str(tidy_repo), "init")
        out = doctor(tidy_repo, run_cli, capsys)
        assert "portability" in out
        assert "core.symlinks" in out or "Windows" in out

    def test_an_import_only_repo_gets_no_warning(self, tmp_path, run_cli, capsys):
        """Nothing to warn about when no mirror is a symlink."""
        (tmp_path / "AGENTS.md").write_text("# P\n\nShared.\n", encoding="utf-8")
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "commands").mkdir()
        (tmp_path / ".claude" / "commands" / "s.md").write_text("Ship.\n", encoding="utf-8")
        run_cli("--root", str(tmp_path), "init", "--force")
        out = doctor(tmp_path, run_cli, capsys)
        assert "portability" not in out


class TestWatchIsReportOnlyByDefault:
    def test_a_new_vendor_file_is_reported_not_adopted(self, initialised, run_cli, capsys):
        """Fanning out automatically is wrong when tools differ on purpose."""
        stray = initialised / ".cursor" / "rules" / "extra.mdc"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"---\ndescription: Extra\nglobs:\n  - src/**\n---\nBe careful.\n")

        run_cli("--root", str(initialised), "watch", "--once")
        out = capsys.readouterr().out
        assert "report-only" in out
        assert not (initialised / ".ai" / "rules" / "extra.md").exists()
        assert stray.is_file(), "nothing may be moved without --write"

    def test_write_actually_adopts(self, initialised, run_cli):
        stray = initialised / ".cursor" / "rules" / "extra.mdc"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"---\ndescription: Extra\nglobs:\n  - src/**\n---\nBe careful.\n")

        run_cli("--root", str(initialised), "watch", "--once", "--write")
        assert (initialised / ".ai" / "rules" / "extra.md").is_file()
