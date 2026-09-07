"""Tests for the release bump.

The release path runs a few times a year, so bugs in it surface at the worst
moment. These exercise the decisions without touching the real files.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import bump  # noqa: E402


class TestNextVersion:
    @pytest.mark.parametrize(
        "current,part,expected",
        [
            ("0.1.0", "patch", "0.1.1"),
            ("0.1.0", "minor", "0.2.0"),
            ("0.1.0", "major", "1.0.0"),
            ("1.2.3", "patch", "1.2.4"),
            ("1.2.3", "minor", "1.3.0"),
            ("1.9.9", "major", "2.0.0"),
            ("0.9.0", "minor", "0.10.0"),
        ],
    )
    def test_bumps(self, current, part, expected):
        assert bump.next_version(current, part) == expected

    def test_lower_components_reset(self):
        assert bump.next_version("1.4.7", "minor") == "1.5.0"
        assert bump.next_version("1.4.7", "major") == "2.0.0"

    def test_unknown_part_rejected(self):
        with pytest.raises(bump.BumpError):
            bump.next_version("1.0.0", "epoch")


class TestGuards:
    def test_going_backwards_is_refused(self):
        with pytest.raises(bump.BumpError):
            bump.ensure_forward("0.2.0", "0.1.0")

    def test_republishing_the_same_version_is_refused(self):
        """PyPI rejects a re-upload; fail here instead, where the message is clear."""
        with pytest.raises(bump.BumpError):
            bump.ensure_forward("0.1.0", "0.1.0")

    def test_non_semver_rejected(self):
        for bad in ("1.0", "v1.0.0", "1.0.0-rc1", "", "abc"):
            with pytest.raises(bump.BumpError):
                bump.parse(bad)

    def test_part_and_explicit_are_mutually_exclusive(self):
        with pytest.raises(bump.BumpError):
            bump.resolve("0.1.0", part="patch", explicit="0.5.0")

    def test_one_of_them_is_required(self):
        with pytest.raises(bump.BumpError):
            bump.resolve("0.1.0")

    def test_explicit_version_may_carry_a_v_prefix(self):
        assert bump.resolve("0.1.0", explicit="v0.4.0") == "0.4.0"


class TestRewriting:
    SOURCE = '"""Docs."""\n\n__all__ = ["__version__"]\n\n__version__ = "0.1.0"\n'

    def test_reads_the_current_version(self):
        assert bump.read_version(self.SOURCE) == "0.1.0"

    def test_missing_version_line_is_an_error(self):
        with pytest.raises(bump.BumpError):
            bump.read_version("nothing here\n")

    def test_rewrites_only_the_version(self):
        out = bump.apply_version(self.SOURCE, "0.2.0")
        assert '__version__ = "0.2.0"' in out
        assert '__all__ = ["__version__"]' in out
        assert out.count("__version__") == self.SOURCE.count("__version__")

    def test_rewrite_is_reversible(self):
        assert bump.read_version(bump.apply_version(self.SOURCE, "9.9.9")) == "9.9.9"


class TestChangelog:
    def test_unreleased_section_is_renamed_not_duplicated(self):
        text = "# Changelog\n\n## [Unreleased]\n\n### Added\n- thing\n"
        out = bump.update_changelog(text, "0.2.0", "2026-09-07")
        assert "## [0.2.0] - 2026-09-07" in out
        assert "[Unreleased]" not in out
        assert "- thing" in out, "notes written during development must survive"

    def test_heading_goes_above_the_previous_release(self):
        text = "# Changelog\n\n## [0.1.0] - 2026-09-07\n\nFirst release.\n"
        out = bump.update_changelog(text, "0.2.0", "2026-09-08")
        assert out.index("[0.2.0]") < out.index("[0.1.0]")


def test_the_packaged_version_matches_the_source_of_truth():
    """pyproject reads the version from the module; nothing may reintroduce a copy."""
    pyproject = (pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in pyproject
    assert "\nversion = " not in pyproject, "a second copy of the version can drift"
