# Where every AI coding tool keeps its config

If you use more than one AI coding assistant on the same repository, you are
probably storing the same project knowledge several times over.

Claude Code reads `CLAUDE.md`. GitHub Copilot reads
`.github/copilot-instructions.md`. Cursor reads `.cursor/rules/*.mdc`. Same
guidance, three files, drifting apart the moment one of them is edited.

I went through the primary documentation for six of these tools, because most of
what a search returns on this subject is generated filler that contradicts
itself. Every path below is linked to the vendor's own docs. Where I could not
confirm something at the source, I say so rather than guessing.

---

## The map

| | Instructions | Scoped rules | Commands | MCP |
|---|---|---|---|---|
| **Claude Code** | `CLAUDE.md` | — | `.claude/commands/*.md` | `.mcp.json` |
| **GitHub Copilot** | `.github/copilot-instructions.md` | `.github/instructions/*.instructions.md` | `.github/prompts/*.prompt.md` | `.vscode/mcp.json` |
| **Cursor** | `AGENTS.md` | `.cursor/rules/*.mdc` | `.cursor/commands/` | `.cursor/mcp.json` |
| **Gemini CLI** | `GEMINI.md` | — | `.gemini/commands/*.toml` | `.gemini/settings.json` |
| **Zed** | `AGENTS.md` | `.rules` | — | `.zed/settings.json` |
| **AGENTS.md** | `AGENTS.md` | — | — | — |

Claude Code additionally uses `.claude/skills/<name>/SKILL.md` for
directory-shaped capabilities and `.claude/agents/*.md` for subagents.

---

## Five things that surprised me

### 1. Cursor ignores `.md` files inside `.cursor/rules`

Rules must be `.mdc`. A plain `.md` file sitting in that directory is silently
ignored — no warning, no error, it simply does nothing. This is a fun way to
spend an afternoon wondering why your carefully written rules have no effect.

From [Cursor's rules documentation](https://cursor.com/docs/context/rules):
project rules live in `.cursor/rules` as `.mdc` files, and "plain `.md` files in
this directory are ignored by the rules system."

### 2. Gemini CLI commands are TOML, not Markdown

Every other tool here stores a slash command as a Markdown file with YAML
frontmatter. Gemini stores it as TOML:

```toml
description = "Review the staged diff"
prompt = """
Review this diff and report only real defects.
"""
```

Confirmed in the
[gemini-cli custom commands docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md):
`.gemini/commands/*.toml`, required key `prompt`, optional `description`, with
file paths mapping to namespaced command names via colons.

This is the detail that defeats the obvious solution. You can symlink
`CLAUDE.md` to `AGENTS.md` because they are the same bytes in the same format.
You cannot symlink a Markdown command into a `.toml` file that expects a
`prompt` key — the container format differs, not just the field names.

### 3. Scoping a rule means a different key in every tool

The same idea — "this rule applies to these files" — is spelled three ways.

**Copilot** ([docs](https://docs.github.com/copilot/how-tos/configure-custom-instructions/add-repository-instructions))
uses `applyTo` with glob syntax, plus an optional `excludeAgent`:

```yaml
---
applyTo: "app/models/**/*.rb"
---
```

**Cursor** uses `globs` plus a boolean `alwaysApply`, and a separate
`description` the agent reads to decide relevance:

```yaml
---
description: How to write tests here
globs: ["tests/**"]
alwaysApply: false
---
```

**Claude Code** has no per-file rule mechanism at all. It reads one document.
Skills accept a `paths` glob to limit activation, but that is a different
concept — an on-demand capability, not an always-on rule.

So "always apply this rule" is `alwaysApply: true` in Cursor, `applyTo: "**"` in
Copilot, and in Claude Code it is simply a paragraph in `CLAUDE.md`.

### 4. MCP configuration has three incompatible schemas

Model Context Protocol is a shared standard. Its configuration file is not.

```jsonc
// .mcp.json — Claude
{ "mcpServers": { "fs": { "command": "npx", "args": ["-y", "server-fs"] } } }

// .vscode/mcp.json — VS Code / Copilot
{ "servers": { "fs": { "command": "npx", "args": ["-y", "server-fs"],
                       "type": "stdio" } } }

// .zed/settings.json — Zed
{ "context_servers": { "fs": { "source": "custom", "command": "npx" } } }
```

Three top-level keys — `mcpServers`, `servers`, `context_servers` — and
per-server shapes that differ too: VS Code wants an explicit `type`, Zed tags
externally-defined servers with `source`.

Worse, two of these files are not exclusively about MCP. `.vscode/mcp.json` also
holds the user's `inputs` for prompted variables, and `.gemini/settings.json` is
*all* of Gemini's settings. Anything that rewrites them has to preserve
everything it does not own. `.vscode/mcp.json` is also JSONC — it permits `//`
comments, which `json.load` rejects outright, and which no rewrite can preserve.

### 5. Frontmatter keys are hyphenated in some places and not others

Claude Code and Copilot prompt files both use `allowed-tools` and
`argument-hint` — hyphens, not underscores. Claude subagents use `tools` as a
comma-separated string (`tools: Read, Grep`) while other places take a list.
Small, but it is the kind of detail that silently drops a field.

---

## AGENTS.md is the one thing converging

The bright spot. [AGENTS.md](https://agents.md) is a plain Markdown file at the
repo root, stewarded by the Linux Foundation's Agentic AI Foundation, and read
natively by Cursor, Copilot, Codex, Aider, Zed, Amp, Continue, Roo, Windsurf,
Jules and Amazon Q. GitHub's own documentation confirms Copilot reads
`AGENTS.md`, `CLAUDE.md` and `GEMINI.md`, with the nearest `AGENTS.md` in the
directory tree taking precedence.

If you use one file and nothing else, use this one. Most of the fragmentation
above is in the layers *above* plain instructions — scoped rules, commands,
skills, MCP — where no standard has emerged.

---

## What this means practically

Three options, in increasing order of effort:

1. **Write only `AGENTS.md`.** Most tools read it. You lose per-file scoping and
   tool-specific commands, and gain never thinking about this again.
2. **Generate the rest from one source.** Several tools do this;
   [rulesync](https://github.com/dyoshikawa/rulesync) supports 40+ tools and
   [ruler](https://github.com/intellectronica/ruler) is also well established.
   Both generate copies from a source directory.
3. **Symlink where the formats agree, generate only where they don't.** Editing
   any mirror then edits the source, because it is the same file. This is the
   approach I took in [agentmeld](https://github.com/moneytool/agentmeld) —
   disclosure, that one is mine, and it is deliberately narrower than the
   alternatives above.

Whichever you pick, the thing worth internalising is that these formats are
*not* converging above the AGENTS.md layer, and every tool that claims to unify
them is making judgement calls about what to drop in translation. Copilot's rule
files have no field for a description. Claude has nowhere to put a glob. Those
are lossy conversions, and it is worth knowing which ones your tooling is making
quietly on your behalf.

---

*Every path here was checked against the vendor's own documentation in September
2026. These formats change; if you find one that has moved, corrections are
welcome.*
