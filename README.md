# agentmeld

[![PyPI](https://img.shields.io/pypi/v/agentmeld)](https://pypi.org/project/agentmeld/)
[![Python](https://img.shields.io/pypi/pyversions/agentmeld)](https://pypi.org/project/agentmeld/)
[![CI](https://github.com/moneytool/agentmeld/actions/workflows/ci.yml/badge.svg)](https://github.com/moneytool/agentmeld/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/agentmeld)](LICENSE)

**One AI context, every agent.**

![agentmeld demo](assets/agentmeld-demo.gif)

Your repo is used with Claude Code, Copilot, and Cursor. So you maintain
`CLAUDE.md`, `.github/copilot-instructions.md`, and `.cursor/rules/*.mdc` — the
same knowledge in three places, drifting apart. Add a fourth tool, write it a
fourth time.

agentmeld gives you **one source of truth plus a per-tool overlay**: the shared
part is written once, and whatever is genuinely specific to one tool stays
specific to that tool. Your `AGENTS.md` stays exactly where it is and becomes the
source; every other location is a pointer, a small generated file, or a surgical
merge.

```
AGENTS.md                     ← you edit this, once (not moved anywhere)
   ├─ CLAUDE.md                                    @AGENTS.md   (a one-line import)
   ├─ .github/copilot-instructions.md              shared base + .ai/overlays/copilot.md
   └─ GEMINI.md                                    symlink, or a copy on Windows

.ai/rules/testing.md          ← scoped rules, also once
   ├─ .cursor/rules/testing.mdc                    generated: description / globs / alwaysApply
   ├─ .github/instructions/testing.instructions.md generated: applyTo
   └─ CLAUDE.md                                    folded in (Claude has no rule files)
```

**Why an overlay and not just one identical file everywhere?** Because that is
not what people actually want. Of 210 public repos carrying both `AGENTS.md` and
`CLAUDE.md`, 30.5% deliberately write *different* things in each — release
procedure, CI specifics, tool invocation — and only 5.7% keep two copies of the
same document. Blindly mirroring one over the other destroys work. So agentmeld
shares the base and keeps the difference.

## Install

```bash
uv tool install agentmeld
```

Or `pipx install agentmeld`, or `pip install agentmeld`. `agm` is a shorter
alias for the same CLI.

Try it without installing anything:

```bash
uvx agentmeld detect
```

## Quickstart

In the repo you actually work in:

```bash
agentmeld detect
```

That only reads — it tells you which AI tools it found and what it would manage.
Then look before you leap:

```bash
agentmeld init --dry-run
```

`init` is the one command that moves files, so it shows you the list first. When
it looks right:

```bash
agentmeld init
```

This makes your root `AGENTS.md` the source of truth **without moving it**, adopts
`.cursor/rules` / skills / commands / MCP servers into `.ai/`, and replaces the
rest with mirrors. Anything that said something genuinely different is kept as
that tool's overlay rather than overwritten. Every original is backed up to
`.ai/.backup/<timestamp>/` first, and it refuses to run on a dirty worktree
unless you pass `--force` — so commit first and the whole thing is one
`git checkout` away from undone.

Finally, make it automatic:

```bash
agentmeld install-hooks
```

## Commands

```bash
agentmeld detect          # which AI tools does this repo actually use?
agentmeld init            # create .ai/, adopt existing config, mirror it back
agentmeld sync            # materialise every mirror
agentmeld sync --adopt    # pull in new vendor files first, then mirror
agentmeld sync --check    # CI: exit 1 if any mirror is stale
agentmeld install-hooks   # auto-sync on agent writes and on commit
agentmeld watch           # report changes live (--write to fan out too)
agentmeld restore         # stop managing this repo, leaving every tool working
agentmeld doctor          # drift, conflicts, orphans, dropped keys
agentmeld list-adapters   # the support matrix, with confidence levels
```

Every command that writes accepts `--dry-run`. `--include-unverified` opts into
paths not confirmed against vendor docs.

## Working on agentmeld itself

```bash
git clone https://github.com/moneytool/agentmeld && cd agentmeld
```

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run agentmeld --help
```

The suite must also pass on the oldest supported Python:

```bash
uv run --python 3.9 --with pytest --with pyyaml --with tomli python -m pytest -q
```

## Background

[**Where every AI coding tool keeps its config**](docs/where-ai-coding-tools-keep-their-config.md)
— the vendor-documentation research this tool is built on: the real paths, the
frontmatter keys, and the five differences that surprised me. Useful even if you
never install agentmeld.

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
agentmeld sync --check          # 1. in CI -- the one trigger that cannot be lost
agentmeld install-hooks         # 2. a Claude Code PostToolUse hook + git pre-commit
agentmeld watch                 # 3. report changes as they happen
agentmeld watch --write         # ... and fan them out, if you really want that
```

CI first, on purpose: **a daemon dies quietly and nobody notices for a week**,
whereas a failing check cannot be silently lost.

`watch` is **report-only unless you pass `--write`**. Fanning out automatically
sounds like the point of the tool and mostly is not: copying one tool's new
content to every other tool is wrong for the ~30% of repos whose tools differ
deliberately, and Claude Code's `#` shortcut appends to `CLAUDE.md`, so an eager
watcher would take a Claude-specific note and broadcast it everywhere.

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

## Where the source of truth lives

**`AGENTS.md`, at the repo root, in place.** If you already have one, adopting
agentmeld moves nothing at all — it is the most common AI config file in public
repos, its share grows with a project's popularity, and most tools read it
directly. A repo with only `CLAUDE.md` gets that file renamed to `AGENTS.md`, and
`CLAUDE.md` comes straight back as a one-line `@AGENTS.md` import, so nothing
about Claude Code changes.

Everything else lives in `.ai/`:

```
AGENTS.md                # the source of truth (root, unmoved)
.ai/
├── agentmeld.toml       # config, including where the source of truth is
├── overlays/<tool>.md   # content that belongs to ONE tool only
├── rules/<slug>.md      # scoped rules (frontmatter: description, globs, always)
├── skills/<slug>/SKILL.md
├── agents/<slug>.md
├── commands/<slug>.md
├── mcp.json             # canonical MCP servers (mcpServers schema)
└── .state.json          # what we manage, and its hashes
```

An overlay is appended to that one tool's file, below a marker, and never reaches
any other tool. It is also where a tool's own append lands — Claude Code's `#`
shortcut writes to `CLAUDE.md`, and that note is Claude-specific, so it stays
Claude-specific instead of being broadcast everywhere.

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

So there are five strategies:

- **import** — the vendor can be told to read another file, so the mirror is one
  line: `@AGENTS.md`. Preferred over `link` wherever it exists, because a symlink
  has four silent failure modes an ordinary file does not (see below). It is also
  simply what people already write: of 30 hand-written pointer files sampled from
  public repos, 21 were exactly `@AGENTS.md`.
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

A symlink fails **silently** in four common situations, and in each one the tool
reads the pointer text as its instructions and follows nothing:

- Windows without Developer Mode or admin,
- a checkout with `core.symlinks=false`,
- archive and container builds that dereference or drop links,
- non-POSIX filesystems — SMB/CIFS serialises the link into the file body as
  `XSym`.

None of these are hypothetical. In a sample of 210 public repos carrying both
`AGENTS.md` and `CLAUDE.md`, 67 use a symlink and **three are already corrupted**
this way — one `XSym` blob, two committed as a plain file whose entire body is the
word `AGENTS.md`. Nobody had noticed, because on the author's machine it works.

That is why `import` is preferred where a vendor supports it, and why
`agentmeld doctor` reports files in this state. For the rest:

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

## Getting back out

```bash
agentmeld restore
```

Turns every symlinked mirror into a real file, removes the hooks, and stops
managing the repo. Every tool keeps working exactly as it did; agentmeld is
simply no longer involved. Your `.ai/` tree is left in place for you to delete.

To go all the way back to how things were before `init`:

```bash
agentmeld restore --from-backup
```

That puts the original files back byte for byte from `.ai/.backup/`, and removes
the mirrors that did not exist beforehand. Both accept `--dry-run`.

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
