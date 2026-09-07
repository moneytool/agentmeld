# Changelog

## [0.1.0] - 2026-09-07

First release. https://pypi.org/project/agentmeld/

### Added
- Canonical `.ai/` tree for instructions, rules, skills, agents, commands and MCP.
- Declarative adapter registry (TOML, no Python needed to add a tool) covering
  AGENTS.md, Claude Code, GitHub Copilot, Cursor, Gemini CLI and Zed, each path
  marked `verified` or `unverified` against the vendor's own documentation.
- Four mirror strategies: `link` (symlink), `generate` (translated frontmatter
  with a provenance header), `merge` (surgical edits to shared config such as
  MCP), and `aggregate` (rules folded into single-document tools).
- Reverse adoption: a file written by any agent is pulled into the canonical tree
  and fanned out to every other tool, with provenance recorded.
- Automatic triggers: `install-hooks` (Claude Code PostToolUse + git pre-commit),
  `watch` (dependency-free polling daemon with feedback-loop guards), and
  `sync --check` for CI, plus a bundled GitHub Action.
- Windows support: symlink capability is probed, with automatic fallback to real
  copies and a `--mode {link,copy,auto}` override.
- `doctor`, reporting drift, conflicts, orphans, gated paths, and every
  frontmatter key dropped in translation.
