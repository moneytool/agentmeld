# agentmeld — what to post, where, when

All times US Central (your machine). ET in brackets.
Everything below is complete and paste-ready. No cross-referencing needed.

===========================================================================
SLOT 1 — MONDAY 7 SEP (today), any time
AWESOME-LIST PULL REQUESTS  (start now; review takes days)
===========================================================================

Open each, read its CONTRIBUTING, add one line, open a PR:

  https://github.com/hesreallyhim/awesome-claude-code
  https://github.com/PatrickJS/awesome-cursorrules
  https://github.com/e2b-dev/awesome-ai-agents

LINE TO ADD:

[agentmeld](https://github.com/moneytool/agentmeld) - Keeps one canonical copy of your AI instructions, rules, skills, agents, commands and MCP config, symlinked into every tool's own location.

PR TITLE:  Add agentmeld
PR BODY:
Adds agentmeld, an MIT-licensed CLI that keeps one canonical copy of AI config
in `.ai/` and mirrors it into each tool's own location — a symlink where the
formats agree, a generated file where they differ (Gemini's TOML commands, for
example). Published on PyPI, tested on Linux/macOS/Windows.


===========================================================================
SLOT 2 — TUESDAY 8 SEP, 7:30am CT  [8:30am ET]
HACKER NEWS — Show HN
===========================================================================

URL:  https://news.ycombinator.com/submit

TITLE (exactly, 80 char limit):
Show HN: Agentmeld – One AI config file, symlinked into every coding assistant

URL FIELD:
https://github.com/moneytool/agentmeld

TEXT FIELD: leave empty.

THEN IMMEDIATELY post this as the first comment on your own submission:

I use Claude Code, Copilot and Cursor on the same repos, and I was maintaining the same project knowledge in CLAUDE.md, .github/copilot-instructions.md and .cursor/rules/*.mdc. They drifted constantly.

rulesync and ruler already solve this by generating copies from a source directory. Two things bothered me: editing a generated mirror silently loses your work on the next run, and you have to remember to run it.

agentmeld keeps one canonical copy in .ai/ and symlinks it wherever the format allows, so editing a mirror edits the source — the same file, not a copy. Where a symlink genuinely can't work it generates a file carrying a content hash, so drift is detectable and hand edits become a reported conflict instead of being silently overwritten. It also runs automatically via a Claude Code PostToolUse hook, a git pre-commit hook, or a watcher, and a file any agent writes gets adopted into the canonical tree and fanned out to the others.

Reading the vendor docs was most of the work. Cursor ignores .md inside .cursor/rules — it must be .mdc. Gemini CLI commands are TOML with a "prompt" key, which is why a pure-symlink tool is impossible. MCP config has three incompatible schemas: mcpServers, servers, context_servers.

Deliberately narrow: six tools, each checked against primary vendor docs, and anything I couldn't verify is excluded from the default sync — it moves your files, so it shouldn't act on a guess. There's an `agentmeld restore` that undoes everything, either ejecting to plain files or putting your originals back. rulesync supports 40+ tools if you want breadth.

>>> STAY ONLINE UNTIL 9:00am CT AND REPLY TO EVERY COMMENT. <<<


===========================================================================
SLOT 3 — TUESDAY 8 SEP, 8:30am CT  [9:30am ET]
LINKEDIN  (native image post — attach your Gemini image)
===========================================================================

URL:  https://www.linkedin.com/feed/  → "Start a post" → add image

POST TEXT:

If your repo is used with more than one AI coding assistant, you are probably maintaining the same knowledge three times.

Claude Code reads CLAUDE.md. GitHub Copilot reads .github/copilot-instructions.md. Cursor reads .cursor/rules/*.mdc. Same guidance, three files, drifting apart — and adding a fourth tool means writing it a fourth time.

I spent a weekend reading the actual vendor documentation for six of these tools. The differences are sharper than I expected:

→ Cursor ignores plain .md files inside .cursor/rules — they must be .mdc
→ Gemini CLI commands are TOML with a "prompt" key, not Markdown
→ Copilot scopes rules with applyTo:, Cursor with globs: and alwaysApply:
→ MCP server config comes in three incompatible schemas: mcpServers (Claude), servers (VS Code), context_servers (Zed)

So I built agentmeld. One canonical copy in .ai/, mirrored into every tool's own location — a real symlink where the formats agree, a generated file where they genuinely differ. Edit any mirror and you have edited the source. A file one agent writes gets adopted back and fanned out to the others automatically.

pip install agentmeld

Three things I made myself do properly, because this tool moves people's files:

1. Every vendor path is marked verified or unverified against that vendor's own documentation. Unverified paths are excluded unless you opt in. A tool that reorganises your repo should not act on a guess.

2. There is a way back out. "agentmeld restore" turns every mirror into a real file and steps out of the way, or restores your originals exactly as they were.

3. Tested on Linux, macOS and Windows across Python 3.9 to 3.13 — 190 tests, plus scenario testing against the published package rather than only the source.

Honest about scope: it supports six tools, not forty. If you want the widest coverage, rulesync is excellent and supports 40+. agentmeld exists for the two things it does differently — symlinks instead of copies, and syncing that happens automatically instead of when you remember.

MIT licensed. Feedback and pull requests welcome.

#AI #DeveloperTools #OpenSource #Python #SoftwareEngineering

FIRST COMMENT (post immediately after — keeps the link out of the post body,
which LinkedIn penalises):

Repo and docs: https://github.com/moneytool/agentmeld


===========================================================================
SLOT 4 — WEDNESDAY 9 SEP, 9:00am CT  [10:00am ET]
REDDIT — r/ClaudeAI
===========================================================================

URL:  https://www.reddit.com/r/ClaudeAI/submit?type=TEXT
Read the sidebar rules first. If self-promotion is banned, skip this slot.

TITLE:
I read the docs for 6 AI coding tools to find where each one keeps its config

BODY:

I kept rewriting the same project instructions for Claude Code, Copilot and Cursor, so I went through the actual vendor documentation for each. A few things surprised me:

- Cursor ignores plain `.md` files inside `.cursor/rules` — they have to be `.mdc`
- Gemini CLI slash commands are TOML with a `prompt` key, not Markdown
- Copilot scopes rules with `applyTo:`, Cursor with `globs:` and `alwaysApply:`
- MCP config comes in three incompatible schemas: `mcpServers` (Claude), `servers` (VS Code), `context_servers` (Zed)
- Claude and Copilot both use hyphenated frontmatter keys like `allowed-tools`

The Gemini one is the interesting case: the container format differs, not just the field names, so you cannot solve this with symlinks alone.

I ended up building a tool that keeps one canonical copy and symlinks it into each location, generating a translated file only where a symlink genuinely can't work. Disclosure: it's mine, MIT, and it's alpha — 6 tools, not 40. rulesync covers far more if you need breadth.

Mostly posting because the format differences seem worth knowing even if you never touch my tool.

https://github.com/moneytool/agentmeld

>>> STAY ONLINE UNTIL 10:30am CT. <<<


===========================================================================
SLOT 5 — THURSDAY 10 SEP, 9:00am CT  [10:00am ET]
REDDIT — r/cursor
===========================================================================

URL:  https://www.reddit.com/r/cursor/submit?type=TEXT

TITLE:
PSA: Cursor ignores .md files in .cursor/rules — plus how 5 other tools differ

BODY:

Spent a weekend reading vendor docs for six AI coding tools. The one that cost me the most time: Cursor only reads `.mdc` inside `.cursor/rules`. A plain `.md` there is silently ignored, which is a fun way to spend an afternoon wondering why your rules do nothing.

The rest, for anyone juggling several tools:

- Gemini CLI slash commands are TOML with a `prompt` key, not Markdown
- Copilot scopes rules with `applyTo:`, Cursor with `globs:` and `alwaysApply:`
- MCP config comes in three incompatible schemas: `mcpServers` (Claude), `servers` (VS Code), `context_servers` (Zed)
- Claude and Copilot both use hyphenated frontmatter keys like `allowed-tools`

I got annoyed enough to build something that keeps one canonical copy and symlinks it into each location, generating a translated file only where a symlink can't work. Disclosure: it's mine, MIT, alpha — 6 tools, not 40. rulesync covers more if you want breadth.

https://github.com/moneytool/agentmeld


===========================================================================
SLOT 6 — MONDAY 14 SEP, 9:00am CT  [10:00am ET]
REDDIT — r/ChatGPTCoding
===========================================================================

URL:  https://www.reddit.com/r/ChatGPTCoding/submit?type=TEXT

Use the SAME title and body as Slot 4 (r/ClaudeAI).


===========================================================================
SLOT 7 — TUESDAY 15 SEP, 9:00am CT  [10:00am ET]
REDDIT — r/programming   (expect removal; last on purpose)
===========================================================================

URL:  https://www.reddit.com/r/programming/submit?type=LINK

TITLE:
One config file, symlinked into every AI coding assistant

URL:
https://github.com/moneytool/agentmeld

If automod removes it, do not argue with the moderators. Move on.


===========================================================================
THE ANSWER YOU WILL NEED IN EVERY THREAD
===========================================================================

Q: "Why not just use rulesync?"

rulesync is more mature and supports 40+ tools — if breadth is what you need, use it, genuinely. agentmeld does two things it doesn't: it symlinks instead of generating copies, so editing any mirror edits the source rather than being overwritten on the next run; and it syncs automatically via hooks or a watcher rather than when you remember to run it. It also adopts in reverse — a file your agent writes becomes canonical and reaches the other tools. The tradeoff is deliberate: 6 tools verified against vendor docs instead of 40.

Q: "What if I try it and hate it?"

`agentmeld restore` either ejects — turning every mirror into a real file and stepping out of the way, so every tool keeps working — or puts your original files back exactly as they were before you ran init. Both have --dry-run.

Never disparage rulesync. Half the audience uses it, and the honest comparison
is the most credible thing you have.
