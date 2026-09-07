"""The release trigger must not fire on the moving action tag.

GitHub Actions filter patterns are not fnmatch and not regex: `+` means "one or
more of the preceding character", `?` means "zero or one", `*` matches anything
but `/`, and `[]` is a character range. This translates that subset faithfully
so the assertions below reflect what GitHub will actually do.
"""

import pathlib
import re

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/release.yml"


def tag_patterns():
    # PyYAML reads the bare `on:` key as the boolean True.
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))
    return triggers["push"]["tags"]


def to_regex(pattern):
    out = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "[":
            close = pattern.index("]", i)
            out.append(pattern[i : close + 1])
            i = close + 1
        elif char in "+?":
            out.append(char)
            i += 1
        elif char == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(tag):
    return any(to_regex(p).match(tag) for p in tag_patterns())


def test_translator_handles_the_github_syntax():
    """Guard the guard: a wrong translator would make every assertion meaningless."""
    assert to_regex("v[0-9]+.[0-9]+.[0-9]+").match("v1.2.3")
    assert not to_regex("v[0-9]+.[0-9]+.[0-9]+").match("v1")
    assert to_regex("v*").match("v1")


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
