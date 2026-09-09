# r/ClaudeAI — Showcase-rule compliant rewrite

Wait the full hour before reposting. Post as a TEXT post.

The modbot flagged two things: no detail on how Claude was used to build it, and
no description of the project beyond a docs link. Both are fixed below. The
checklist it applies:

- [x] says you built it
- [x] says it was built with Claude Code
- [x] describes what was built, how Claude helped, and what it does
- [x] says it is free, and shows how to try it
- [x] marketing language minimal
- [x] no affiliate links
- [x] no job seeking

---

## TITLE

I built agentmeld with Claude Code — one AI config file, symlinked into every assistant (and what I got wrong on the way)

---

## BODY

**What I built.** agentmeld, a Python CLI that keeps one canonical copy of your
AI assistant configuration in a `.ai/` directory and mirrors it into each tool's
own location. If you use Claude Code alongside Copilot or Cursor, you are
probably maintaining `CLAUDE.md`, `.github/copilot-instructions.md` and
`.cursor/rules/*.mdc` separately, and they drift. This keeps one source and
propagates it — a real symlink where the formats agree, so editing any mirror
edits the source, and a generated file only where a symlink genuinely cannot
work.

**Free, MIT licensed, no paid tier, nothing to sign up for:**

```
uv tool install agentmeld    # or: pip install agentmeld
cd your-repo
agentmeld detect             # read-only: what does this repo actually use?
agentmeld init --dry-run     # shows what it would move, changes nothing
agentmeld init               # backs originals up to .ai/.backup/ first
agentmeld restore            # full undo, whenever you want out
```

**How Claude Code helped build it.** The whole thing was written in Claude Code
sessions, and the parts I found most useful were not the code generation:

- *Reading the vendor docs.* Most of the work was establishing where each tool
  actually keeps its config. Claude Code fetched the primary documentation for
  six tools and I marked each path `verified` or `unverified` based on whether it
  appeared in the vendor's own docs. Unverified paths are excluded from syncing
  unless you opt in — a tool that moves your files should not act on a guess.

- *Finding a data-loss bug before release.* Testing against throwaway repos
  caught that adopting config was moving `.gemini/settings.json` — all of
  Gemini's settings, not just the MCP section — into the canonical tree. That
  would have deleted real config from where Gemini reads it. Fixed in 0.1.1.

- *Catching a factual error I had already shipped.* I added a check reporting
  rules with no globs, no `alwaysApply` and no description as "nothing will load
  this". A separate Claude session reviewing the project pointed out that this is
  exactly Cursor's documented **"Apply Manually"** rule type — it loads when you
  `@`-mention it. The check was wrong, in a version already on PyPI. It now says
  "loads only if you @-mention it" and asks rather than accuses.

That last one is the honest reason I am posting rather than just linking a repo:
having a second model review the work found something my own tests did not,
because my tests asserted the same wrong belief the code did.

**Things I learned about these config formats that might save you an afternoon:**

- **Cursor only reads `.mdc` in `.cursor/rules`.** A plain `.md` there is ignored
  silently — no warning, no error. This cost me two hours.
- **Gemini CLI commands are TOML**, not Markdown, with a `prompt` key. Which
  means you cannot symlink a command between Claude and Gemini; the container
  format differs, not just the field names.
- **Scoping is spelled three ways**: `globs:`+`alwaysApply:` in Cursor,
  `applyTo:` in Copilot, and Claude Code has no per-file rule mechanism at all —
  it reads one document.
- **MCP config has three incompatible schemas**: `mcpServers` (Claude),
  `servers` (VS Code), `context_servers` (Zed).

Full writeup with every path linked to the vendor's own docs:
https://github.com/moneytool/agentmeld/blob/main/docs/where-ai-coding-tools-keep-their-config.md

**Scope, honestly:** six tools, alpha, and I am the only user I know of. If you
want breadth, rulesync supports 40+ and is far more mature — genuinely, use that
if coverage is what you need. Mine differs in two ways: symlinks instead of
generated copies, and it runs automatically from a git hook or watcher rather
than when you remember.

Repo: https://github.com/moneytool/agentmeld

Happy to be corrected on any of the format details — these change often.

---

## IF IT GETS REMOVED AGAIN

Modmail them, politely, with: "I have updated the post to include how Claude Code
was used in building it and a full description of the project rather than only a
docs link. Could you take another look?" Do not repost a third time without
asking first — that reads as evasion.

## NOTE FOR NEXT TIME

Any post linking your own GitHub triggers Showcase rules in this sub, even when
the post is mostly educational. Read the Showcase requirements *before* writing,
not after. r/cursor and r/ChatGPTCoding have different rules — check each
separately rather than reusing this text blind.
