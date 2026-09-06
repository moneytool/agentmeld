# agentmeld

**One AI context, every agent.**

Your repo is used with Claude Code, Copilot, and Cursor. So you maintain
`CLAUDE.md`, `.github/copilot-instructions.md`, and `.cursor/rules/*.mdc` — three
copies of the same knowledge, drifting apart. Add a fourth tool, write it a
fourth time.

agentmeld keeps **one canonical copy in `.ai/`** and mirrors it into every
vendor location — a **real symlink** where the formats agree, a small
**generated file** where they genuinely differ.

```
.ai/rules/testing.md          ← you edit this, once
   ├─ .cursor/rules/testing.mdc                    generated: description / globs / alwaysApply
   ├─ .github/instructions/testing.instructions.md generated: applyTo
   └─ CLAUDE.md                                    folded in (Claude has no rule files)
```

## Install

```bash
uv tool install agentmeld
```

Or `pipx install agentmeld`, or `pip install agentmeld`. `agm` is a shorter
alias for the same CLI.

## Use

```bash
agentmeld detect          # which AI tools does this repo actually use?
agentmeld init            # create .ai/, adopt existing config, mirror it back
agentmeld sync            # materialise every mirror
agentmeld sync --adopt    # pull in new vendor files first, then mirror
agentmeld sync --check    # CI: exit 1 if any mirror is stale
agentmeld install-hooks   # auto-sync on agent writes and on commit
agentmeld watch           # or run a daemon instead
agentmeld doctor          # drift, conflicts, orphans, dropped keys
agentmeld list-adapters   # the support matrix, with confidence levels
```

## Why not the existing tools?

[rulesync](https://github.com/dyoshikawa/rulesync) and
[ruler](https://github.com/intellectronica/ruler) are mature, excellent, and
support far more tools than agentmeld does. **If you want the widest tool
coverage, use them** — that is not false modesty, rulesync covers 40+ tools and
tracks vendor minutiae in real depth.

agentmeld exists for two things neither of them does:

| | rulesync / ruler | agentmeld |
|---|---|---|
| Mirrors are | generated copies | **symlinks** wherever the format allows |
| Editing a mirror | discarded on next generate | **writes straight to the canonical file** |
| Runs | manually (`npx … generate`) | **automatically** — agent hooks, watch, pre-commit |
| A file your agent just wrote | stays vendor-local until you import | **adopted into canonical and fanned out** |
| Runtime | Node | Python, no Node required |
| Tool coverage | 40+ | a handful, each checked against vendor docs |

That last row is deliberate. Read on.

## Support matrix

| Tool | instructions | rules | skills | agents | commands | MCP |
|---|---|---|---|---|---|---|
| AGENTS.md (open standard) | link | — | — | — | — | — |
| Claude Code | link | — | link | gen | gen | merge |
| GitHub Copilot | link | gen | — | gen&nbsp;※ | gen | merge |
| Cursor | — | gen | link&nbsp;※ | — | gen&nbsp;※ | merge&nbsp;※ |
| Gemini CLI | link | — | — | — | gen | merge&nbsp;※ |
| Zed | — | — | — | — | — | merge&nbsp;※ |

`link` = symlink · `gen` = generated file · `merge` = surgical edit of shared
config · `link/agg` = symlink until a rule exists, then an aggregate ·
**※ = unverified**

### Unverified means excluded

Every path is marked `verified` or `unverified`. **Unverified paths are skipped
unless you pass `--include-unverified`.** `verified` means the path and its
frontmatter keys are stated in the vendor's own documentation, linked from the
adapter file.

This is not bureaucracy. A tool that moves your files cannot act on a guess: a
wrong path does not fail loudly, it scatters your context into a directory the
tool never reads. Much of what a web search returns on this subject is
AI-generated filler that contradicts itself, so anything not confirmed at the
source is opt-in. Correcting one is a one-line pull request.

## Automatic syncing

Three triggers, in order of how much you should rely on them:

```bash
agentmeld install-hooks   # 1. a Claude Code PostToolUse hook + a git pre-commit hook
agentmeld watch           # 2. a polling daemon, for editors without hooks
agentmeld sync --check    # 3. in CI
```

Hooks and CI are the defaults on purpose: **a daemon dies quietly and nobody
notices for a week**, whereas a failing CI check cannot be silently lost.

In CI, via the bundled action:

```yaml
- uses: moneytool/agentmeld@v1
  with:
    args: sync --check
```

### Adoption, not just generation

When any agent writes a new `.claude/skills/foo/SKILL.md`, agentmeld moves it
into `.ai/skills/foo/`, records where it came from, and fans it out to every
other tool. Your context converges on one source instead of accumulating in
whichever tool happened to create it.

## The canonical tree

```
.ai/
├── agentmeld.toml     # config
├── instructions.md      # the main "how to work here" doc
├── rules/<slug>.md      # scoped rules (frontmatter: description, globs, always)
├── skills/<slug>/SKILL.md
├── agents/<slug>.md
├── commands/<slug>.md
├── mcp.json             # canonical MCP servers (mcpServers schema)
└── .state.json          # what we manage, and its hashes
```

Canonical frontmatter is a **superset vocabulary**, using the hyphenated Agent
Skills spelling (`allowed-tools`, `argument-hint`) so skills can stay symlinks.
Each adapter maps it down and drops what its vendor cannot express — and
`doctor` lists every key it had to drop, so nothing vanishes quietly.

## Why symlinks *and* generated files

Because a symlink is sometimes physically impossible:

- Gemini CLI commands are **TOML** with a `prompt =` key; Claude commands are
  Markdown. Different container format, not just different field names.
- Copilot rules need `applyTo:`; Cursor needs `globs:` and `alwaysApply:` — and
  Cursor **ignores plain `.md` files** inside `.cursor/rules`.
- MCP config is three incompatible schemas: `mcpServers` (Claude), `servers`
  (VS Code), `context_servers` (Zed).

So there are four strategies:

- **link** — the vendor reads the canonical bytes as-is → relative symlink.
- **generate** — a derived file with a provenance header and a content hash, so
  drift is detectable and your hand edits are never silently discarded (you get a
  reported conflict instead).
- **merge** — the target is shared config we do not own → parse it, replace only
  our subtree, **preserve every other key and every server you added by hand**.
- **aggregate** — the tool reads one document and has no rule mechanism, so rules
  are folded in under their own headings. Stays a plain symlink while no rules
  exist.

## Windows, macOS, Linux

| Platform | Behaviour |
|---|---|
| macOS / Linux | real symlinks |
| Windows + Developer Mode (or admin) | real symlinks |
| Windows without either | automatic fallback to real copies |
| Checkout with `core.symlinks=false` | copies, with a warning |

`--mode {link,copy,auto}` overrides the probe. `auto` attempts an actual symlink
in a temp directory and degrades gracefully — never a traceback. The test suite
runs on all three platforms and on Python 3.9 through 3.13.

## Mirrors are committed

By default the mirrors are checked in, so teammates and CI **without**
agentmeld installed still get working AI config. Set `git_policy = "ignore"`
in `.ai/agentmeld.toml` for the opposite tradeoff.

## Safety

- `init` is the only destructive command. It backs everything up to
  `.ai/.backup/<timestamp>/` and refuses to run on a dirty worktree without
  `--force`.
- Nothing is ever written inside the canonical tree.
- A file agentmeld did not create is never overwritten — it is reported as a
  conflict and left alone.
- `sync` twice in a row produces byte-identical output.
- `--dry-run` on every command that writes.

## Status

Alpha. The engine and the verified adapters work and are tested end to end;
expect the matrix to keep moving, because the vendors keep moving.

## License

MIT
