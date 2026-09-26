---
title: 'agentmeld: one source of truth for AI coding-agent configuration'
tags:
  - Python
  - AI coding agents
  - developer tooling
  - configuration management
  - reproducibility
authors:
  - name: AUTHOR_FULL
    orcid: 0009-0005-1167-2026
    affiliation: 1
affiliations:
  - name: Independent researcher, USA
    index: 1
date: SUBMIT_DATE
bibliography: paper.bib
---

# Summary

AI coding agents — Claude Code, GitHub Copilot, Cursor, Gemini CLI, Codex and
others — read natural-language instruction files from the repository they work
in: `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/*.mdc`,
`GEMINI.md`, `AGENTS.md` [@agentsmd2025; @claudecode-memory;
@copilot-instructions; @cursor-rules; @gemini-cli-config]. Each tool has its
own path, its own file format, and its own frontmatter keys for scoping rules
to paths. A repository used with three tools therefore carries the same
knowledge in three places, and those places drift.

`agentmeld` is a Python command-line tool that keeps **one canonical copy** of
a repository's agent instructions, rules, skills, sub-agent definitions,
commands and MCP server configuration [@mcp2024], and materialises every
tool-specific location from it. The canonical `AGENTS.md` stays where it is;
each other location becomes a symlink, a one-line vendor import, a generated
file with the vendor's frontmatter, or a surgical merge into shared config.
Where a tool genuinely needs something different, that difference lives in a
per-tool *overlay* rather than a divergent copy. `agentmeld doctor` reports
drift, conflicts, orphaned mirrors and silently broken symlinks; `agentmeld
sync --check` fails CI when a mirror is stale; a GitHub Action wraps the same
check for pull requests.

# Statement of need

This is not hypothetical. In a stratified sample of 1,905 public GitHub
repositories carrying a root `AGENTS.md` (September 2026), 649 (34%) also
carry a `CLAUDE.md` [@agentmeld-pilot]. Of those pairs, 40% are two distinct
documents, a further 10% are copies that have already diverged partially,
19% make `CLAUDE.md` a symlink to `AGENTS.md`, 19% use the vendor import
directive `@AGENTS.md`, 6% point at the other file in prose, and 5% are
byte-identical copies. Two repositories had committed a symlink as a plain
text file whose entire body is the word `AGENTS.md` — a file the tool reads
as its instructions. Half of all such repositories, in other words, have
deliberately written something different for each tool; blindly mirroring
one file over the other would destroy that work.

Two consequences follow. For practitioners, the maintenance cost of AI
instructions scales with the number of tools rather than the amount of
knowledge. For researchers, the *context an agent actually received* is an
uncontrolled variable: two agents run on the same repository may have read
different instructions, which confounds any comparison of their behaviour.
Existing remedies — hand-maintained symlinks, vendor-specific import
directives, or copying one file over the others — either break silently on
Windows and non-POSIX filesystems (the pilot found committed symlinks already
serialised into plain files), or destroy the tool-specific content that
maintainers wrote deliberately.

Recent empirical work has characterised these files tool by tool — their
content [@agentreadmes2025], Cursor rules specifically [@jiang2026cursor],
adoption of each tool's mechanisms across 2,853 repositories
[@galster2026configuring], and rule taxonomies over time
[@ruletaxonomy2026] — but none addresses the repository that configures
several tools at once, and @galster2026configuring name longitudinal
evolution and AGENTS.md adoption as open questions. `agentmeld` is built for
exactly that repository. It models the problem as *shared base plus
per-tool overlay*, derives each vendor's rule-file frontmatter (`globs`,
`applyTo`, `alwaysApply`) from one canonical schema, and detects the
corrupted-symlink failure mode.

# State of the field

Vendor import directives (`@AGENTS.md` in `CLAUDE.md`) cover one tool pair
and nothing else. The AGENTS.md initiative [@agentsmd2025] standardises the
*file* but not its relationship to tools that read a different path. Rule
managers for a single editor manage that editor only. General configuration
tools (dotfile managers, templating) know nothing about agent-file semantics
— they cannot fold path-scoped rules into a tool that has no rule mechanism,
or preserve a hand-added MCP server in a merged JSON file. `agentmeld`'s
adapters are declarative TOML records of each vendor's documented paths and
keys, each tagged with a confidence level and a link to the vendor page that
proves it; unverified adapters are excluded from the default sync.

# Functionality

- `detect` — which AI tools a repository is configured for.
- `init` / `sync --adopt` — adopt existing vendor files into `.ai/` with a
  timestamped backup, refusing to run on a dirty worktree.
- `sync` / `sync --check` / `watch` — materialise mirrors; CI check; live
  fan-out.
- `doctor` — drift, conflicts, orphans, dropped frontmatter keys, `XSym`
  and plain-text symlink corruption.
- `restore` — turn every mirror back into a real file and remove hooks.
- Strategies per file kind: `link`, `generate`, `merge`, `aggregate`; a
  symlink probe that degrades to copies on Windows without Developer Mode.
- Adapters: Claude Code, GitHub Copilot, Cursor, Gemini CLI, Zed, and the AGENTS.md standard. CI runs the suite on Linux, macOS and Windows under Python 3.9, 3.12 and 3.13; the package declares support for 3.9–3.14.

# Research applications

`agentmeld` is the instrument for an ongoing empirical study of how
open-source projects configure AI coding agents [@agentmeld-pilot]: its
adapter registry is the file classifier, and `doctor` is the corruption
detector. Because it makes the instruction context byte-identical across
tools, it is also a precondition for controlled comparisons of agent
behaviour on benchmarks such as SWE-bench [@jimenez2024swebench;
@yang2024sweagent], where instruction files are otherwise an unmeasured
confound.

# Acknowledgements

Portions of the code, tests and documentation were drafted with AI
assistance (Anthropic Claude) under the author's direction and were reviewed,
tested and edited by the author, who is responsible for the content.

# References
