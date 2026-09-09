# Finding 2: a typical edit loads ~32% of the rule set

**Date:** 2026-09-08 · **Status:** stable across sample sizes
**Data:** `data/glob-ratios.json` · **Collector:** `scripts/collect-glob-ratios.py`

> **Superseded for prevalence.** The rates here come from a GitHub code-search
> sample, which only returns repos that already contain the file being counted.
> They describe *adopters*, not repositories in general. For population rates see
> [finding 07](07-prevalence-stratified.md).

## Question

Scoped rules (Cursor's `globs:`, Copilot's `applyTo:`) load only when the agent
touches matching files. **What fraction of a repo's rule set actually matches a
typical source file?**

This number decides whether scoping saves money — see
`findings/04-caching-economics.md` for why the break-even sits near 10%.

## Method

Sampled repos containing `.cursor/rules/*.mdc` or `.github/instructions/*.md`.
For each: parsed frontmatter from every rule file, read the repo's file tree via
the git trees API, and for each source file computed

    (bytes of rules that match this file) / (bytes of all rules)

taking the median across up to 300 source files per repo. Rules with
`alwaysApply: true` count as matching everything.

Glob matching implements gitignore-ish semantics (`**` spans directories, `*`
does not) and was validated against 9 hand-checked cases before use.

## Results

Stable as the sample grew — the key reason to believe it:

| | n=21 | n=50 | n=110 | **n=120** |
|---|---|---|---|---|
| Median match ratio | 24.2% | 31.0% | 31.9% | **31.9%** |
| Repos where scoping wins (<10%) | 10% | 6% | 6% | **7%** |

At n=120 (1,001 rules): median **31.9%**, mean 40.1%, p25 7.2%, p75 68.7%.

| Regime (break-even ≈10%) | Share of repos |
|---|---|
| 0% — nothing ever matches | 22% |
| 0–10% — scoping wins | **7%** |
| 10–50% — scoping loses on a warm cache | 36% |
| >50% — scoping loses badly | 35% |

**72% of repos are above the break-even.**

Median rule set: 5 rules, ~14,500 chars (~3,600 tokens) — which sits at the
**minimum cacheable prefix boundary** (512–4096 tokens, model-dependent), so for
a typical repo caching may not engage at all.

## Interpretation

The intuition "scoping loads less, so it costs less" fails for most real repos
once prompt caching is considered. People write broad globs.

## Caveats

- n = 120 repos / 1,001 rules; GitHub code search is relevance-ranked
- Characters used as a token proxy — acceptable for a *ratio*, since numerator
  and denominator share the proxy
- Glob semantics approximate Cursor's actual matcher; 9/9 on hand-checked cases
  is not the same as matching their implementation
- Match ratio is computed over source files, weighted uniformly; real edits are
  not uniformly distributed across a repo
