import subprocess
from pathlib import Path

import pytest


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text).encode("utf-8"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo carrying three tools' worth of drifted AI config."""
    _write(tmp_path / "CLAUDE.md", "# Working here\n\nRun tests with pytest.\n")
    _write(tmp_path / ".github/copilot-instructions.md", "# Guidance\nUse pytest. (drifted)\n")
    _write(
        tmp_path / ".cursor/rules/testing.mdc",
        "---\ndescription: How to test\nglobs:\n  - tests/**\nalwaysApply: false\n---\n"
        "Use fixtures, not setUp.\n",
    )
    _write(
        tmp_path / ".claude/skills/deploy/SKILL.md",
        "---\nname: deploy\ndescription: Deploy to staging\n---\nRun deploy.\n",
    )
    _write(tmp_path / ".claude/skills/deploy/notes.md", "reference\n")
    _write(
        tmp_path / ".mcp.json",
        '{"mcpServers": {"fs": {"command": "npx", "args": ["-y", "server-fs"]}}}\n',
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for key, value in (("user.email", "t@t.t"), ("user.name", "t")):
        subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


@pytest.fixture
def tidy_repo(tmp_path: Path) -> Path:
    """A repo whose instruction files agree, so mirrors stay plain symlinks.

    The ``repo`` fixture deliberately has *drifted* content, which now becomes a
    per-tool overlay -- and a file with an overlay cannot be a symlink. Shape
    tests need a repo where nothing diverges.
    """
    shared = "# Working here\n\nRun tests with pytest.\n"
    _write(tmp_path / "AGENTS.md", shared)
    _write(tmp_path / ".github/copilot-instructions.md", shared)
    _write(tmp_path / "GEMINI.md", shared)
    _write(
        tmp_path / ".claude/skills/deploy/SKILL.md",
        "---\nname: deploy\ndescription: Deploy to staging\n---\nRun deploy.\n",
    )
    _write(tmp_path / ".claude/skills/deploy/notes.md", "reference\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for key, value in (("user.email", "t@t.t"), ("user.name", "t")):
        subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


@pytest.fixture
def run_cli():
    """Invoke the CLI in-process and return its exit code."""
    from agentmeld.cli import main

    def call(*argv: str) -> int:
        return main(list(argv))

    return call
