# Changelog

## Unreleased

### Added

- **`import` strategy.** Where a vendor can be told to read another file, the
  mirror is now one line (`@AGENTS.md`) instead of a symlink. A symlink fails
  silently on Windows without Developer Mode, under `core.symlinks=false`, in
  archive and container builds, and on SMB/CIFS — which serialises it into the
  file body as `XSym`. Three of 67 symlinked mirrors in a sample of 210 public
  repos are already corrupted this way. `CLAUDE.md` uses it.
- **Per-tool overlays** at `.ai/overlays/<tool>.md`, appended to that tool's
  mirror below a marker and never shared with any other tool. This is what the
  ~30% of repos whose instruction files deliberately differ actually need; the
  previous model could only serve repos wanting byte-identical content everywhere.
- **`doctor` reports broken pointer files** — a config file whose body is a
  serialised symlink (`XSym`, or a bare path) rather than instructions. The tool
  reads it literally and loads nothing, and it is invisible to whoever caused it.
- **`doctor` reports symlink portability** and **`.md` files inside
  `.cursor/rules`**, which Cursor ignores with no error.
- `restore` inlines import mirrors so ejected files stand alone.

### Changed

- **The source of truth is `AGENTS.md` at the repo root, and `init` no longer
  moves it.** An existing `AGENTS.md` costs nothing to adopt. A repo with only
  `CLAUDE.md` has it renamed, and `CLAUDE.md` returns as a one-line import.
  Already-initialised repos keep `.ai/instructions.md` — upgrading moves nothing.
- **`init` preserves a divergent second instruction file** as that tool's overlay
  instead of overwriting it.
- **`watch` is report-only unless `--write` is passed.** Automatic fan-out copies
  one tool's content over another's, which is wrong wherever they differ on
  purpose — and Claude Code's `#` shortcut appends to `CLAUDE.md`.

### Fixed

- Generated mirrors were created `0600` because `mkstemp` does; they are now
  `0644` minus umask. An instruction file others cannot read is useless, and the
  mode showed up as a spurious change in every diff.
- An edited `import` mirror could be silently overwritten: being recorded in state
  was treated as proof of ownership without comparing against what was last
  written.

## [0.1.4] - 2026-09-08

## [0.1.3] - 2026-09-08

## [0.1.2] - 2026-09-07

### Added
- Gemini CLI TOML commands can now be adopted, not just generated. A command
  written for Gemini becomes canonical and reaches every other tool; previously
  the round trip was one-way.

## [0.1.1] - 2026-09-07

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

### Added
- `agentmeld restore` — leave the repo in a working state without agentmeld, or
  put the pre-`init` files back from a backup. A tool that moves your files needs
  a supported way back.

### Fixed
- Comments in an existing `.vscode/mcp.json` (JSONC) are reported when a rewrite
  drops them, instead of disappearing without a word.
