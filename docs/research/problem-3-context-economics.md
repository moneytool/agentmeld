# Problem 3: Context economics

**Status:** open, unmeasured
**Prerequisite reading:** none — this document is self-contained

---

## Background you need

AI coding assistants (Claude Code, GitHub Copilot, Cursor, Gemini CLI, and
others) are configured through files committed to a repository. Broadly:

- an **instructions** file that is always sent to the model — `CLAUDE.md`,
  `AGENTS.md`, `.github/copilot-instructions.md`
- **rules**, which are scoped instructions that apply only to certain files.
  Cursor stores these in `.cursor/rules/*.mdc` with a `globs:` frontmatter key;
  GitHub Copilot stores them in `.github/instructions/*.instructions.md` with an
  `applyTo:` key. Claude Code has no rule mechanism at all — it reads one
  document.

**agentmeld** (https://github.com/moneytool/agentmeld) is a CLI that keeps one
canonical copy of this configuration in a `.ai/` directory and mirrors it into
each tool's expected location — a symlink where the formats agree, a generated
file where they differ. That part works and is published on PyPI.

Everything below concerns a claim agentmeld has not tested.

---

## The problem

As a project accumulates instructions and rules, all of that text is sent to the
model on **every request**. Input tokens cost money and consume the context
window.

Scoping is the obvious remedy: a rule tagged `globs: ["tests/**"]` is loaded only
when the agent is working on test files. Both Cursor and Copilot implement this.
agentmeld carries the glob metadata across tools.

**The claim that has never been checked: does scoping actually reduce what you
spend?**

---

## Why the obvious answer is probably wrong

Scoping loads fewer tokens. That is not the same as costing less, because of
**prompt caching**.

The Claude API (and equivalents elsewhere) prices repeated context very
differently from new context:

| | Multiplier on base input price |
|---|---|
| Uncached input | 1.0× |
| Cache **write** (first time) | 1.25× |
| Cache **read** (subsequent) | ~0.1× |

Two properties matter enormously:

1. **Caching is a prefix match.** Any byte change anywhere in the prefix
   invalidates everything after it. Render order is `tools` → `system` →
   `messages`.
2. **The cache expires.** Default TTL is 5 minutes; a 1-hour TTL is available.

### Worked example

A repository with 10,000 tokens of rules.

**Monolithic** — everything loaded, byte-identical on every request:
- first request: 10,000 × 1.25 = **12,500** token-equivalents
- each subsequent request while warm: 10,000 × 0.1 = **1,000**

**Scoped** — only matching rules, so the content differs per request:
- every request: 2,000 × 1.0 = **2,000**

The scoped version loads **5× fewer tokens** and costs **twice as much**,
because varying the content defeats the cache.

Break-even is roughly: scoping wins only when the scoped subset is under **~10%**
of the full set. Above that threshold, scoping is more expensive.

**This is the counterintuitive result at the centre of this problem: loading
less context can cost more.**

---

## The design that might get both

Because caching is prefix-matched, ordering matters more than volume:

1. put **stable** content (instructions, always-on rules) at the front, with a
   cache breakpoint after it → charged at ~0.1×
2. put **scoped, varying** rules *after* that breakpoint → they change freely
   without invalidating anything before them
3. full price is then paid only on the small varying portion

The principle is **partition by volatility**, not "load less". This is a
different design from what agentmeld currently implies, and it is unvalidated.

---

## What is actually unknown

1. **Does scoping reduce cost in realistic conditions?** Depends on the ratio of
   scoped subset to full set, and on request cadence.
2. **How does request cadence change the answer?** With a 5-minute TTL, a
   developer working in bursts lets the cache expire repeatedly, so monolithic
   pays 1.25× again and again. For sparse usage, scoping may win after all. This
   is measurable and nobody has measured it.
3. **Does the volatility-partitioned layout deliver both benefits in practice?**
4. **Does scoping hurt output quality?** If a rule is genuinely relevant but its
   globs do not match the file being edited, the model never sees it. This
   false-negative rate is the real risk of scoping and is separate from cost.

---

## How to measure it

**Conditions** — a 2×2, not a straight comparison:

| | Cache warm | Cache cold |
|---|---|---|
| Monolithic | | |
| Scoped | | |

Crossed with realistic request cadences (rapid iteration vs. sparse).

**Cost measurement** is objective. Read `usage.cache_read_input_tokens`,
`usage.cache_creation_input_tokens`, and `usage.input_tokens` from each response
and price them at the three multipliers above. **If `cache_read_input_tokens` is
zero across repeated requests, something is silently invalidating the prefix** —
a timestamp, a UUID, unsorted JSON serialisation, or a varying tool list. Verify
this before trusting any result.

**Quality measurement** is the hard part. A workable approach: write rules whose
compliance can be checked programmatically. For example, a rule stating "use
pytest fixtures, not setUp" can be verified by scanning generated code for
`setUp`. Then measure compliance rate under each condition. The interesting case
is deliberately constructing tasks where a rule is relevant but out of glob
scope, to quantify the false-negative rate.

---

## Pitfalls

- **Minimum cacheable prefix is 512–4096 tokens**, model-dependent. Below that
  nothing caches and the whole analysis collapses to "smaller is cheaper".
  Check the threshold for whichever model is used.
- **Every experimental run costs real money.** Budget it and get approval before
  running anything at scale.
- **Model choice is a confound.** Different models have different tokenizers,
  context windows, and instruction-following behaviour. Hold the model fixed, or
  treat it as an explicit variable.
- **Do not conflate token count with cost.** That mistake is the entire reason
  this problem is interesting.

---

## Why it matters beyond agentmeld

If scoping does not save money under caching, then a substantial amount of
tooling in this space is optimising the wrong quantity. The result is useful
whichever way it lands, and as far as I can tell it is unpublished.
