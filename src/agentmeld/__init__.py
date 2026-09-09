"""agentmeld -- one AI context, every agent.

A repo used with several AI coding tools ends up holding the same knowledge in
``CLAUDE.md``, ``.github/copilot-instructions.md`` and ``.cursor/rules/*.mdc``,
drifting apart. agentmeld keeps one source of truth -- your root ``AGENTS.md``, left where it is
-- and mirrors it into every vendor location: a one-line import where the tool
can be told to read another file, a symlink or generated file where it cannot,
plus a per-tool overlay for whatever is genuinely specific to one tool.
"""

__all__ = ["__version__"]

__version__ = "0.2.0"
