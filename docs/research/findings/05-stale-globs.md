# Finding 5: ~15% of scoped rules match nothing in their own repo

**Date:** 2026-09-08 · **Status:** preliminary
**Data:** `data/stale-globs.json` · **Collector:** `scripts/collect-stale-globs.py`

> **Superseded for prevalence.** The rates here come from a GitHub code-search
> sample, which only returns repos that already contain the file being counted.
> They describe *adopters*, not repositories in general. For population rates see
> [finding 07](07-prevalence-stratified.md).

## The finding

Of 255 rules that *do* carry globs, across 60 public repositories, **14.9% match
zero files in the repository they live in.** 25% of repos have at least one.

| Cause | Share of scoped rules |
|---|---|
| `path_absent` — scoped to a directory that is not there | 13.7% |
| `missing_globstar` — wrote `*.py` where `**/*.py` was meant | 1.2% |

The second is small but instructive: `globs: ['*.tsx', '*.css']` in a repository
where every `.tsx` file lives in a subdirectory. `*` does not cross directory
boundaries, so the rule matches only the repository root — nothing. The author
believed the rule was scoped.

Together with [finding 03](03-dead-rules.md) (21.4% with no automatic trigger),
roughly **a third of rules in the wild do not do what their author expects**.

## Method correction

The first version of this measurement reported **25.3%**. That was wrong.

The glob parser split on commas without respecting braces, so
`globs: ['**/*.{js,ts}']` became the two patterns `**/*.{js` and `ts}` — neither
of which matches anything. A large share of the "stale" rules were my parser's
failures, not the authors'.

After adding brace expansion and classifying the remaining failures by cause,
the figure fell to 14.9%. **The examples gave it away**: several flagged rules
displayed globs like `['**/*.{js', 'ts']`, which is not something a human would
write.

## Caveats

- n=60 repos / 255 scoped rules; GitHub code search is relevance-ranked
- `path_absent` is computed against the **default branch only**. A rule scoped to
  a directory that exists on a feature branch, or to a gitignored build output
  (`dist/**`, `.venv/**`), counts as stale here and should not.
  **This is the largest known weakness in the number** and would need fixing
  before the figure is quoted anywhere.
- Glob semantics approximate Cursor's matcher; validated on 9 hand-checked cases
- Forward-looking rules ("when you create `migrations/`…") are indistinguishable
  from stale ones
