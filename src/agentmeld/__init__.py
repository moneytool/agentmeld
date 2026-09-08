"""agentmeld -- one AI context, every agent.

A repo used with several AI coding tools ends up holding the same knowledge in
``CLAUDE.md``, ``.github/copilot-instructions.md`` and ``.cursor/rules/*.mdc``,
drifting apart. agentmeld keeps one canonical copy in ``.ai/`` and mirrors it
into every vendor location -- as a real symlink where the formats agree, and as
a small generated file where they do not.
"""

__all__ = ["__version__"]

__version__ = "0.1.3"
