"""Checks on the files we ship but do not import.

The GitHub Action shipped as invalid YAML once, because a `description` scalar
contained `": "`. Nothing imported it, so nothing caught it -- it would have
failed only in a stranger's CI.
"""

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {".git", ".venv", "dist", "node_modules"}


def shipped_yaml():
    return [
        p
        for p in sorted(ROOT.rglob("*.y*ml"))
        if not any(part in SKIP for part in p.relative_to(ROOT).parts)
    ]


@pytest.mark.parametrize("path", shipped_yaml(), ids=lambda p: str(p.name))
def test_yaml_is_parseable(path):
    yaml.safe_load(path.read_text(encoding="utf-8"))


def test_action_declares_the_expected_interface():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert set(action["inputs"]) == {"args", "version", "working-directory"}
    assert action["runs"]["using"] == "composite"


def test_workflows_reference_the_current_package_name():
    for name in ("ci.yml", "release.yml"):
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "monocontext" not in text


def test_no_stale_project_name_anywhere_we_ship():
    """The rename must not leave half the repo pointing at the old name."""
    for path in sorted((ROOT / "src").rglob("*")):
        if path.suffix in (".py", ".toml"):
            assert "monocontext" not in path.read_text(encoding="utf-8"), path
