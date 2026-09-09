# Finding 3: ~21% of real-world rules never load automatically

**Date:** 2026-09-08 · **Status:** strongest result among adopters; frame cannot support a population claim
**Data:** `data/glob-ratios.json` (`rulestats`) · **Collector:** `scripts/collect-glob-ratios.py`

> **Superseded for prevalence.** The rates here come from a GitHub code-search
> sample, which only returns repos that already contain the file being counted.
> They describe *adopters*, not repositories in general. For population rates see
> [finding 07](07-prevalence-stratified.md).

## The finding

Of 1,001 rule files sampled from 120 public repositories, **21.4% have no automatic trigger** -- they load only when
explicitly @-mentioned.

They have:
- no `globs:` / `applyTo:` — so nothing triggers them by path
- `alwaysApply: false` (or absent) — so they are not always on
- no `description:` — so the agent has nothing to judge relevance from

In Cursor's model that combination has no activation path. The file sits in
`.cursor/rules/`, looks like configuration, is committed, reviewed, and
maintained — and is never read.

**22% of repos have at least one.**

## Full distribution (1,001 rules)

| Configuration | Count | Share |
|---|---|---|
| has globs (scoped) | 417 | 46.3% |
| `alwaysApply: true` | 182 | 20.2% |
| **never loads** | **207** | **21.4%** |
| description only (agent decides) | 95 | 10.5% |

Stable across sample sizes: 21.7% at n=50, 23.0% at n=110, 21.4% at n=120.

## Why this is the most useful result here

Unlike the cost question, it depends on **no contested assumption**. There is no
pricing model, no caching argument, no break-even threshold to defend. The rule
is simply inert, the author cannot tell, and nothing in the tooling reports it.

## Discovery

Found by accident. The first repo processed by the ratio collector scored
`median_match = 0.000`, which looked like a bug in the glob matcher. The matcher
turned out to be correct (9/9 on hand-checked cases); the repo genuinely had
three rules with empty `globs`, `alwaysApply: false`, and empty `description`.

## Actionable consequence

An `agentmeld doctor` check. agentmeld already parses this frontmatter to mirror
it, so detection is nearly free:

```
rules
-----
.ai/rules/security.md
    can never load: no globs, always is false, no description
    add globs, set always: true, or write a description
```

## Correction (2026-09-08)

The first version of this finding, and the `doctor` check shipped in agentmeld
0.1.3, claimed these rules "can never load". **That was wrong**, and it was
caught by an external review from Claude Fable 5.1.

Cursor documents four rule types, and the fourth — **"Apply Manually"** — has
exactly this frontmatter (`alwaysApply: false`, no `description`, no `globs`) and
loads when the user `@`-mentions it. Verified against
https://cursor.com/docs/context/rules.

So 21.4% is the share of rules with **no automatic trigger**, not the share that
are broken. Some are deliberate Manual rules. Frontmatter alone cannot separate
intent from oversight, and any headline claiming otherwise is overstated.

The wording in `doctor` was corrected to ask rather than accuse.

## Caveats
- Copilot's `applyTo` is required by its documentation, so a Copilot rule
  without it may be malformed rather than merely inert.
- Frontmatter parsing is a hand-rolled reader, not a YAML parser; malformed
  frontmatter could be miscounted.
