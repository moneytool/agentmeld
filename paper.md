---
title: 'agentmeld: one source of truth for AI coding-agent configuration'
tags:
  - Python
  - AI coding agents
  - developer tooling
  - configuration management
  - reproducibility
authors:
  - name: Vamshidher Reddy Jannapu Reddy
    orcid: 0009-0005-1167-2026
    affiliation: 1
affiliations:
  - name: Independent researcher, USA
    index: 1
date: SUBMIT_DATE
bibliography: paper.bib
---

# Summary

Every AI company ships its own frontier model, and every one of them reads
its own instruction files from the repository. Claude Code reads `CLAUDE.md`,
Copilot reads a file under `.github`, Cursor has its `.cursor/rules` folder,
Gemini CLI reads `GEMINI.md`, and the newer tools read `AGENTS.md`
[@agentsmd2025; @claudecode-memory; @copilot-instructions; @cursor-rules;
@gemini-cli-config]. So if you want to try a competitor's model on your
repository, you have to explain everything from the beginning: the rules,
the skills, the agents you had already defined. The same knowledge ends up in three or four
places, and those places drift apart.

`agentmeld` is a Python command-line tool that solves exactly this problem.
You keep one copy of the instructions, rules, skills, sub-agent definitions,
commands and MCP server configuration [@mcp2024], and the tool produces
every other company's file from it. Your `AGENTS.md` stays where it is;
each other location becomes a symlink to it, a one-line import, a generated
file with that vendor's frontmatter, or a merge into a shared config file,
whichever the tool supports. Anything one tool genuinely needs that the
others do not goes in a small per-tool overlay instead of a separate copy.
`agentmeld doctor` finds the drift between one company's instruction set
and another's, along with conflicts and broken symlinks, and
`agentmeld sync --check` fails the CI build when a mirror is stale.

# Statement of need

The problem is not hypothetical. In 2026 one vendor withdrew its models from
a popular editor, and every user of that editor who wanted to keep using
those models had to switch tools. There is nothing today that lets you take
an existing project and start work in a different agent on day one. You
have to explain your instructions again: the rules, which tools the agent
may connect to, how you want it to work. You can ask the new agent to
read the old file and write its own instruction set, but it costs tokens
every time, and again when you switch back. `agentmeld` exists to make that switch
free.

We took a sample of 2,421 public repositories that carry at least one
agent instruction file; 2,255 of them are active and not forks
[@agentmeld-pilot]. Half of those configure more than one tool. About 696
have both `AGENTS.md` and `CLAUDE.md`, and of those 46.8 % are two
separate documents, 12.4 % have an import statement pointing at the other
file, 11.9 % point at it in prose, 9.6 % use a symlink, and only 3 % are
identical copies. Four repositories had committed a symlink as a plain-text
file, which the tool then reads as its instructions, and 36 have import
lines pointing at files that do not exist. Of 330 pairs with enough
history to follow, half started out the same, a third of those diverged,
and half of the divergences happened within nine days. Two consequences
follow. The maintenance cost grows with the number of tools, not the
amount of knowledge. And researchers cannot know what context an agent
actually read: two agents run on the same repository may have followed
different instructions. The existing fixes fail in
practice. A symlink that works on a Mac stops working on Windows, or on a
filesystem that cannot store it, and the committed plain-text symlinks are
that failure in the wild. Vendor import directives cover one pair of tools.
Copying one file over the others destroys what the half of maintainers
who wrote separate documents did deliberately. Prior studies describe
these files one tool at a time [@agentreadmes2025; @jiang2026cursor;
@galster2026configuring; @ruletaxonomy2026]; none addresses the repository
that configures several. `agentmeld` is built for that repository: a
shared base plus a per-tool overlay, each vendor's rule-file frontmatter
(`globs`, `applyTo`, `alwaysApply`) derived from one schema, and the
corrupted-symlink case detected.

# State of the field

Today a `CLAUDE.md` can hold a one-line `@AGENTS.md` import, but that
covers one pair of tools and nothing else. The AGENTS.md initiative
[@agentsmd2025] standardises the file, not how it relates to the tools
that read a different path, and the rule managers built for a single
editor manage that editor only. General configuration tools, dotfile
managers and templating, are generic: they do not know what these files
mean to the agent you are using, so they cannot fold a path-scoped rule
into a tool that has no rule mechanism, or keep a hand-added MCP server
when they merge a JSON file. `agentmeld` knows which tool needs which
file, in which format. Each vendor's documented
paths and keys are a declarative TOML record, tagged with a confidence
level and a link to the vendor page that proves it. An adapter without that verification is
left out of the default sync: the tool does not convert or symlink
everything it finds, it writes exactly the files each agent requires.

# Functionality

A user runs `detect` first to see which AI tools the repository is built
for, then `init` or `sync --adopt` to move the existing configuration into
`.ai/`, and from then on `sync` keeps every tool's files written from it.

- `detect`: which AI tools a repository is configured for.
- `init` / `sync --adopt`: adopt the existing vendor files into `.ai/`,
  with a timestamped backup, refusing to run on a dirty worktree.
- `sync` / `sync --check` / `watch`: write the mirrors, fail the CI check
  when one is stale, or watch and fan out changes live.
- `doctor`: identify drift, conflicts, orphaned mirrors, dropped frontmatter
  keys, and `XSym` or plain-text symlink corruption.
- `restore`: turn every mirror back into a real file and remove the hooks.
- Strategies per file kind: `link`, `generate`, `merge`, `aggregate`; a
  symlink probe falls back to copies on Windows without Developer Mode.
- Adapters: Claude Code, GitHub Copilot, Cursor, Gemini CLI, Zed, and the
  AGENTS.md standard. CI runs on Linux, macOS and Windows under Python
  3.9, 3.12 and 3.13; the package declares support for 3.9 to 3.14.

# Research applications

Because `agentmeld` writes each agent's instruction set from one `.ai/`
folder, it was also the instrument for our study of how open-source projects configure these agents
[@agentmeld-pilot]: its adapter registry classified the files, and `doctor`
is what found the broken and plain-text symlinks. For the same reason it
is a precondition for comparing one agent against another. With one
unified instruction set, every agent reads byte-identical context, so a
comparison on a benchmark such as SWE-bench [@jimenez2024swebench;
@yang2024sweagent], where the instruction file is otherwise an unmeasured
variable, measures the agents and not their files.

# Acknowledgements

The manuscript was drafted in the author's own words with AI assistance
(Anthropic Claude) for fact-checking against the data and for editing;
much of the software was written with the same assistance under the
author's direction. The author takes full responsibility for the content.
No external funding.

# References
