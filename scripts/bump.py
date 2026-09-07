"""Compute and apply the next version.

Kept as a script rather than inline shell in the workflow so the interesting part
-- deciding what the next version is, and rewriting files without corrupting them
-- can be unit tested. A release process that is only exercised during a release
is a release process nobody has tested.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys
from typing import Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "src/agentmeld/__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r'^__version__ = "(?P<version>\d+\.\d+\.\d+)"$', re.M)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

PARTS = ("major", "minor", "patch")


class BumpError(ValueError):
    """Something about the request or the files does not add up."""


def read_version(text: str) -> str:
    match = VERSION_RE.search(text)
    if match is None:
        raise BumpError("no __version__ = \"X.Y.Z\" line found")
    return match.group("version")


def parse(version: str) -> Tuple[int, int, int]:
    if not SEMVER_RE.match(version):
        raise BumpError("{!r} is not X.Y.Z".format(version))
    major, minor, patch = (int(p) for p in version.split("."))
    return major, minor, patch


def next_version(current: str, part: str) -> str:
    """Bump one component, resetting the ones below it."""
    if part not in PARTS:
        raise BumpError("part must be one of {}, got {!r}".format(", ".join(PARTS), part))
    major, minor, patch = parse(current)
    if part == "major":
        return "{}.0.0".format(major + 1)
    if part == "minor":
        return "{}.{}.0".format(major, minor + 1)
    return "{}.{}.{}".format(major, minor, patch + 1)


def ensure_forward(current: str, new: str) -> None:
    """Refuse to go backwards or stand still.

    PyPI will not accept a re-upload of an existing version, so catching this
    here turns a confusing mid-release failure into a clear one.
    """
    if parse(new) <= parse(current):
        raise BumpError(
            "new version {} is not ahead of current version {}".format(new, current)
        )


def apply_version(text: str, new: str) -> str:
    updated, count = VERSION_RE.subn('__version__ = "{}"'.format(new), text, count=1)
    if count != 1:
        raise BumpError("expected exactly one __version__ line, replaced {}".format(count))
    return updated


def update_changelog(text: str, new: str, today: str) -> str:
    """Insert a heading for the new version under the title.

    If an [Unreleased] section exists it is renamed, so notes written during
    development are carried into the release rather than stranded.
    """
    heading = "## [{}] - {}".format(new, today)
    if "## [Unreleased]" in text:
        return text.replace("## [Unreleased]", heading, 1)

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## "):
            lines.insert(index, heading)
            lines.insert(index + 1, "")
            return "\n".join(lines) + "\n"
    return text.rstrip("\n") + "\n\n" + heading + "\n"


def resolve(current: str, part: str = "", explicit: str = "") -> str:
    if bool(part) == bool(explicit):
        raise BumpError("pass exactly one of a part (major/minor/patch) or an explicit version")
    new = explicit.lstrip("v") if explicit else next_version(current, part)
    ensure_forward(current, new)
    return new


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bump the agentmeld version.")
    parser.add_argument("--part", default="", help="major, minor or patch")
    parser.add_argument("--version", default="", dest="explicit", help="an explicit X.Y.Z")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        source = VERSION_FILE.read_text(encoding="utf-8")
        current = read_version(source)
        new = resolve(current, args.part, args.explicit)
    except BumpError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2

    print("current={}".format(current))
    print("new={}".format(new))
    if args.dry_run:
        return 0

    VERSION_FILE.write_bytes(apply_version(source, new).encode("utf-8"))
    if CHANGELOG.is_file():
        today = dt.date.today().isoformat()
        CHANGELOG.write_bytes(
            update_changelog(CHANGELOG.read_text(encoding="utf-8"), new, today).encode("utf-8")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
