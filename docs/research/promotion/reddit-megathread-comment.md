# Megathread comment — post this now

Go to:
https://www.reddit.com/r/ClaudeAI/comments/1w7yvbn/built_with_claude_project_showcase_megathread/

Post the text below as a **comment**. No karma gate on comments, so this works
today. Keep it shorter than the standalone post — megathread readers are
skimming many entries.

---

## COMMENT

**agentmeld** — one AI config file, symlinked into every assistant. Built with
Claude Code. Free, MIT, no paid tier.

**The problem:** if you use Claude Code alongside Copilot or Cursor, you end up
maintaining `CLAUDE.md`, `.github/copilot-instructions.md` and
`.cursor/rules/*.mdc` separately, and they drift apart.

**What it does:** keeps one canonical copy in `.ai/` and mirrors it into each
tool's own location — a real symlink where the formats agree, so editing any
mirror edits the source, and a generated file only where a symlink genuinely
cannot work (Gemini CLI stores commands as TOML with a `prompt` key, so those
have to be translated).

```
uv tool install agentmeld    # or pip install agentmeld
agentmeld detect             # read-only: what does this repo use?
agentmeld init --dry-run     # shows what it would move, changes nothing
agentmeld init               # backs originals up to .ai/.backup/ first
agentmeld restore            # full undo whenever you want out
```

**How Claude Code helped**, beyond writing code:

- *Reading vendor docs.* Most of the work was establishing where each tool
  actually keeps its config. Every path is marked `verified` or `unverified`
  depending on whether it appears in the vendor's own documentation, and
  unverified paths are excluded from syncing unless you opt in — a tool that
  moves your files shouldn't act on a guess.
- *Catching a data-loss bug pre-release.* Testing on throwaway repos found that
  adopting config was moving `.gemini/settings.json` — all of Gemini's settings,
  not just the MCP part — into the canonical tree. Fixed in 0.1.1.
- *Catching an error I'd already shipped.* I added a check reporting rules with
  no globs, no `alwaysApply` and no description as "nothing will load this". A
  separate Claude session reviewing the project pointed out that's exactly
  Cursor's documented **"Apply Manually"** type — it loads on `@`-mention. The
  check was wrong in a version already on PyPI. It now says "loads only if you
  @-mention it" and asks rather than accuses.

That last one is the bit I found genuinely useful: my own tests passed because
they asserted the same wrong belief the code did. A second model reviewing the
work caught what the test suite structurally couldn't.

**Scope, honestly:** six tools, alpha, and I'm the only user I know of. If you
want breadth, rulesync supports 40+ and is far more mature — use that if
coverage is what you need.

https://github.com/moneytool/agentmeld

---

## THEN: the two communities Reddit suggested

Both were offered in the removal screen, which means they are plausible fits and
neither is a Claude-specific Showcase sub.

**r/devtools** — https://www.reddit.com/r/devtools/submit?type=TEXT
Best fit. Small but on-topic. Use the original educational framing (the
`.mdc` gotcha, format differences), not the "built with Claude Code" framing —
that angle only matters in r/ClaudeAI.

**r/AIcodingProfessionals** — https://www.reddit.com/r/AIcodingProfessionals/submit?type=TEXT
Also reasonable. Same content.

Read each sidebar first. Space them a day apart.

---

## ABOUT THE KARMA GATE

This is the real constraint and it is not fixable by editing text. r/ClaudeAI now
requires minimum karma for standalone Showcase posts.

The only honest fix is to participate normally for a while: answer questions in
r/ClaudeAI, r/cursor, r/devtools where you actually know the answer — and you
now know a genuinely useful thing most people don't, which is where each of
these tools keeps its config and how their formats differ. A week of that earns
the karma, and it builds recognition that makes the eventual post land better
anyway.

Do not buy karma, and do not farm it with low-effort comments. Both are visible
and both are worse than waiting.
