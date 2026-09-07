"""The release trigger must not fire on the moving action tag."""

import fnmatch
import pathlib

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/release.yml"


def tag_patterns():
    # PyYAML reads the bare `on:` key as the boolean True.
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))
    return triggers["push"]["tags"]


def matches(tag):
    return any(fnmatch.fnmatch(tag, pattern) for pattern in tag_patterns())


def test_release_fires_on_a_version_tag():
    assert matches("v0.1.0")
    assert matches("v1.2.3")
    assert matches("v10.20.30")


def test_release_does_not_fire_on_the_moving_action_tag():
    """`v1` is re-pointed whenever the action changes; publishing then is wrong."""
    assert not matches("v1")
    assert not matches("v2")


def test_release_does_not_fire_on_unrelated_tags():
    assert not matches("nightly")
    assert not matches("v1.0")
