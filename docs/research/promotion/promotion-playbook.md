# agentmeld promotion playbook — everything to post, and where

You post all of this. Reddit is blocked in my browser, so none of it is automated.

Package: https://pypi.org/project/agentmeld/ (0.1.2)
Repo:    https://github.com/moneytool/agentmeld

Order matters. Do 1 → 2 → 3 over a few days. Posting everywhere in one hour is
the pattern Reddit's spam filters look for.

---------------------------------------------------------------------------
## 1. REDDIT — r/ClaudeAI   (do this one first)
---------------------------------------------------------------------------

Submit here (TEXT post, not link post):
  https://www.reddit.com/r/ClaudeAI/submit?type=TEXT

Check the sidebar rules first. If self-promotion is banned outright, skip and
go to r/cursor.

TITLE:
I read the docs for 6 AI coding tools to find where each one keeps its config

BODY:
I kept rewriting the same project instructions for Claude Code, Copilot and
Cursor, so I went through the actual vendor documentation for each. A few things
surprised me:

- Cursor ignores plain `.md` files inside `.cursor/rules` — they have to be `.mdc`
- Gemini CLI slash commands are TOML with a `prompt` key, not Markdown
- Copilot scopes rules with `applyTo:`, Cursor with `globs:` + `alwaysApply:`
- MCP config comes in three incompatible schemas: `mcpServers` (Claude),
  `servers` (VS Code), `context_servers` (Zed)
- Claude and Copilot both use hyphenated frontmatter keys (`allowed-tools`)

The Gemini one is the interesting case: because the container format differs and
not just the field names, you cannot solve this with symlinks alone.

I ended up building a tool that keeps one canonical copy and symlinks it into
each location, generating a translated file only where a symlink genuinely can't
work. Disclosure: it's mine, MIT, and it's alpha — 6 tools, not 40. rulesync
covers far more if you need breadth.

Mostly posting because the format differences seem worth knowing even if you
never touch my tool.

https://github.com/moneytool/agentmeld

---------------------------------------------------------------------------
## 2. REDDIT — r/cursor   (next day)
---------------------------------------------------------------------------

  https://www.reddit.com/r/cursor/submit?type=TEXT

TITLE:
PSA: Cursor ignores .md files in .cursor/rules — plus how 5 other tools differ

BODY:
Same as above, but move the Cursor bullet to the top and open with:

"Spent a weekend reading vendor docs for six AI coding tools. The one that cost
me the most time: Cursor only reads `.mdc` inside `.cursor/rules` — a plain `.md`
there is silently ignored, which is a fun way to wonder why your rules do
nothing."

Keep the same disclosure line and link at the end.

---------------------------------------------------------------------------
## 3. REDDIT — r/ChatGPTCoding   (next day)
---------------------------------------------------------------------------

  https://www.reddit.com/r/ChatGPTCoding/submit?type=TEXT

Same title and body as r/ClaudeAI.

---------------------------------------------------------------------------
## 4. REDDIT — r/programming   (expect removal)
---------------------------------------------------------------------------

  https://www.reddit.com/r/programming/submit?type=LINK

Link posts only, no self-promo tolerance. Post the GitHub URL with the title:

  One config file, symlinked into every AI coding assistant

Honest expectation: likely removed by automod or moderators. Don't argue if so.

---------------------------------------------------------------------------
## 5. HACKER NEWS   (highest value; weekday, ~8-10am US Eastern)
---------------------------------------------------------------------------

  https://news.ycombinator.com/submit

TITLE:
Show HN: Agentmeld – One AI config file, symlinked into every coding assistant

URL: https://github.com/moneytool/agentmeld

Then immediately post this as the FIRST COMMENT on your own submission:

I use Claude Code, Copilot and Cursor on the same repos, and I was maintaining
the same project knowledge in CLAUDE.md, .github/copilot-instructions.md and
.cursor/rules/*.mdc. They drifted constantly.

rulesync and ruler already solve this by generating copies from a source
directory. Two things bothered me: editing a generated mirror silently loses
your work on the next run, and you have to remember to run it.

agentmeld keeps one canonical copy in .ai/ and symlinks it wherever the format
allows, so editing a mirror edits the source — the same file, not a copy. Where
a symlink genuinely can't work it generates a file carrying a content hash, so
drift is detectable and hand edits become a reported conflict instead of being
overwritten. It also runs automatically via a Claude Code PostToolUse hook, a
git pre-commit hook, or a watcher, and a file any agent writes gets adopted into
the canonical tree and fanned out.

Reading the vendor docs was most of the work. Cursor ignores .md inside
.cursor/rules. Gemini CLI commands are TOML with a "prompt" key, which is why a
pure-symlink tool is impossible. MCP config has three incompatible schemas.

Deliberately narrow: six tools, each checked against primary docs, with anything
unverified excluded from the default sync — it moves your files, so it shouldn't
act on a guess. There's also `agentmeld restore` to undo everything. rulesync
supports 40+ tools if you want breadth.

---------------------------------------------------------------------------
## 6. LOBSTERS   (needs an invite; skip if you don't have an account)
---------------------------------------------------------------------------

  https://lobste.rs/stories/new
  Tags: programming, practices

---------------------------------------------------------------------------
## 7. AWESOME LISTS — the part that outlasts a launch spike
---------------------------------------------------------------------------

These are PRs to real, high-traffic repos. Read each CONTRIBUTING first; they
have strict formatting rules and reject sloppy entries.

  awesome-claude-code   (53.6k stars)
  https://github.com/hesreallyhim/awesome-claude-code

  awesome-cursorrules   (40.7k stars)
  https://github.com/PatrickJS/awesome-cursorrules

  awesome-ai-agents     (29.9k stars)
  https://github.com/e2b-dev/awesome-ai-agents

Suggested entry line:

  [agentmeld](https://github.com/moneytool/agentmeld) - Keeps one canonical copy
  of your AI instructions, rules, skills, agents, commands and MCP config,
  symlinked into every tool's own location.

---------------------------------------------------------------------------
## WHERE TO COMMENT — and how, honestly
---------------------------------------------------------------------------

I won't write comments that pose as organic recommendations of your own tool.
That's astroturfing, it's against Reddit's rules, and it gets accounts banned
before your real post ever lands. What works instead:

Search these and reply ONLY where genuinely on-topic, always disclosing:

  https://www.reddit.com/search/?q=CLAUDE.md%20cursor%20rules%20sync&sort=new
  https://www.reddit.com/search/?q=%22copilot-instructions%22&sort=new
  https://www.reddit.com/search/?q=AGENTS.md&sort=new

REPLY TEMPLATE (adapt, never paste blind):

  Ran into this exact thing. Worth knowing that Cursor only reads `.mdc` inside
  `.cursor/rules` — a plain `.md` there is silently ignored — and Gemini's
  commands are TOML rather than Markdown, so they can't just be symlinked.

  Full disclosure, I got annoyed enough to build a tool for it
  (https://github.com/moneytool/agentmeld). rulesync is the more mature option
  if you want broader tool coverage.

Rules for yourself: answer the question first, mention the tool second, always
say it's yours, and never reply in a thread where it isn't genuinely relevant.

---------------------------------------------------------------------------
## EXPECT THIS QUESTION EVERYWHERE
---------------------------------------------------------------------------

"Why not just use rulesync?"

ANSWER:

  rulesync is more mature and supports 40+ tools — if breadth is what you need,
  use it, genuinely. agentmeld does two things it doesn't: it symlinks instead of
  generating copies, so editing any mirror edits the source rather than being
  overwritten on the next run; and it syncs automatically via hooks or a watcher
  rather than when you remember to run it. It also adopts in reverse — a file
  your agent writes becomes canonical and reaches the other tools. The tradeoff
  is deliberate: 6 tools verified against vendor docs instead of 40.

Never disparage rulesync. Half the audience uses it, and the honest comparison
is the most credible thing you have.
