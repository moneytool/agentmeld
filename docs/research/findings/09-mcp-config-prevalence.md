# Finding 9: MCP config is a small surface inside repositories

**Date:** 2026-09-10 · **Status:** primary result, narrow scope · **Data:**
`data/probe-mcp.json` · **Scripts:** `sampling/probe-mcp.py`,
`scripts/analyze-mcp-prevalence.py` · **Frame:** the same frozen frame as
[finding 07](07-prevalence-stratified.md), fingerprint `8fd846e908911bf9`

## Read this first: what this does *not* measure

This counts **committed, repo-level** MCP configuration. A large share of people
configure MCP servers at the **user** level instead — `~/.claude.json`, VS Code
user settings — which never touches a repository at all.

So "1.24% of repos carry MCP config" is **not** "1.24% of developers use MCP",
and the second number is certainly higher. This finding cannot settle whether MCP
is popular. It settles a narrower question: *how much MCP configuration exists on
the surface agentmeld operates on*, which is repositories.

The distinction matters because the result was used to reason about shipping an
MCP server, and on its own it does not support that conclusion. The argument that
does is in "What this was for", below.

## Question

Should agentmeld ship an MCP server? Prompted by an unsolicited directory listing
that misidentified agentmeld as one. Before arguing about it, measure how much
MCP config actually exists in repos, and who has it.

## Method

The same 4,314 repos from the frozen frame used in finding 07, so the numbers are
directly comparable rather than a fresh sample with its own selection story.

Three **MCP-dedicated** paths only:

| File | Tool |
|---|---|
| `.mcp.json` | Claude Code |
| `.vscode/mcp.json` | VS Code / Copilot |
| `.cursor/mcp.json` | Cursor |

`.gemini/settings.json` and `.zed/settings.json` were **deliberately excluded**.
They are general settings files that *may* contain a server block, so their
presence would not prove MCP use — and counting them would have inflated the
result in exactly the direction that flattered the idea under test.

The probe distinguishes an authoritative 404 from a network failure and retries
transient errors, returning `None` when a result is indeterminate. **Zero of
12,942 probes came back indeterminate**, so unlike finding 07 there is no
undercounting caveat here: every result is a real 200 or 404.

## Result

**1.24% of active public repos carry MCP configuration** (95% CI 0.85–1.63).

| | weighted prevalence |
|---|---|
| any AI instruction config | **12.30%** |
| **MCP config** | **1.24%** |
| `.cursor/rules` | 0.70% |

MCP config is an order of magnitude rarer than instruction files, and sits in the
same size class as Cursor's scoped rules.

### By star band — flat, unlike instruction files

| Stars | n | k | rate | 95% CI |
|---|---|---|---|---|
| 10–25 | 800 | 9 | 1.1% | 0.6–2.1 |
| 25–60 | 800 | 10 | 1.2% | 0.7–2.3 |
| 60–150 | 800 | 14 | 1.8% | 1.0–2.9 |
| 150–500 | 800 | 6 | 0.8% | 0.3–1.6 |
| 500–2000 | 788 | 9 | 1.1% | 0.6–2.2 |
| 2000+ | 326 | 10 | 3.1% | 1.7–5.6 |

Every interval overlaps every other except the top band's against the 150–500
dip. Compare finding 07's instruction-file gradient over the same repos: a clean,
near-monotonic 9.5% → 32.2%. Whatever drives instruction-file adoption upward
with a project's visibility is not yet driving in-repo MCP config the same way.

### By file

| File | repos |
|---|---|
| `.mcp.json` (Claude) | 39 |
| `.vscode/mcp.json` (VS Code) | 18 |
| `.cursor/mcp.json` (Cursor) | 11 |

### The overlap is the decision-relevant number

Of 4,314 repos:

| | repos |
|---|---|
| MCP config **and** instruction config | 45 |
| MCP config only | **13** |
| instruction config only | 621 |
| neither | 3,635 |

- **P(instruction config | MCP config) = 78%.** Repos with MCP config are
  overwhelmingly already inside the population that carries instruction files.
- **P(MCP config | instruction config) = 6.8%.** Only a small slice of that
  population has in-repo MCP config at all.
- The genuinely distinct group — MCP config, no instruction files — is **13 repos
  out of 4,314, or 0.3%**.

## What this was for

The question was whether to ship agentmeld as an MCP server. **The answer is no,
and this data is the weakest of the three reasons.** Recorded here so the
reasoning is not later attributed to a number that cannot carry it:

1. **Lifecycle (decisive, and independent of any measurement).** Instruction
   files are read at session start. An MCP tool is called mid-session, and only
   if the agent chooses to call it. A server therefore cannot deliver
   instructions to the tool that needs them — by the time it could answer, the
   tool has already loaded, or failed to load, its config. For the motivating
   use case, someone moving between tools, what is needed is config already on
   disk in the new tool's format before it starts. That is filesystem state, not
   a runtime call.
2. **Every MCP client already has a shell.** Claude Code, Cursor, Copilot agent
   mode and Codex can all run `uvx agentmeld sync` with no install and no config
   entry. Wrapping a CLI the agent can already invoke adds a connection and a
   maintenance surface for nothing.
3. **Prevalence (this finding, supporting only).** Even within agentmeld's own
   audience, only 6.8% carry in-repo MCP config, and the population reachable
   *only* through MCP is 0.3%.

There is also a structural irony worth recording: MCP client config comes in
three incompatible schemas (`mcpServers`, `servers`, `context_servers`), which is
one of the fragmentation problems agentmeld exists to fix. Installing an
agentmeld MCP server across every tool would therefore require agentmeld.

**The correct relationship to MCP is the one the tool already has** — managing
MCP config, merging across the three schemas while preserving servers the user
added by hand. For the 58 repos in this sample that carry MCP config, that is
work already being done.

## Threats to validity

- **User-level config is invisible here**, as stated at the top. This is the
  dominant limitation and it bounds every inference to "in repositories".
- **A snapshot of a newer convention.** The frame was frozen 2026-09-08 and MCP
  is younger than the instruction-file convention, so this is more likely to
  move than finding 07's numbers. Re-run `sampling/probe-mcp.py` against the same
  frozen frame to get a comparable later reading.
- **Presence is not use.** A committed `.mcp.json` may be stale or vendored from
  a template.
- **≥10 stars, recently pushed, public.** Same population caveat as finding 07.
- Says nothing about how widely MCP *servers* are published or consumed — only
  about client configuration checked into repositories.
