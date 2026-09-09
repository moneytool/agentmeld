# Finding 7: how common are AI config files, really — a stratified estimate

**Date:** 2026-09-08 · **Status:** primary result · **Data:** `data/probe-slice-{a,b}.json`,
`data/probe-summary.json` · **Frame:** `sampling/frozen-meta.json`
(fingerprint `8fd846e908911bf9`)

This finding supersedes the prevalence numbers in findings 01–03 and 05, which were
computed on a GitHub **code-search** sample. Code search only returns repos that
*already contain a matching file*, so it can describe adopters but cannot estimate how
many repos are adopters. Findings 01–03/05 must be re-scoped to "among adopters"
claims or recomputed on this frame.

## Question

Of active public GitHub repositories, what fraction carry configuration for at least
one AI coding assistant — and how many carry more than one?

## Method

**Frame.** Repos with ≥10 stars pushed within the sampling window, enumerated by
stratified search over six star bands × date cells (48 cells) to work around GitHub's
1000-results-per-query cap. 18,913 repos enumerated; GitHub's own reported per-band
totals sum to 21,886. The frame was **frozen and fingerprinted** before any probing,
so the sample cannot shift underneath the measurement — the failure mode that
invalidated two earlier attempts.

**Sample.** Deterministic selection of up to 800 repos per band; the two smallest bands
were probed in full (census). n = 4,314, probed in two disjoint slices by independent
agents, verified to have 0 overlapping repos.

**Probe.** Per repo, existence of `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md`, `.github/instructions/`, `.cursor/rules/`.
"Tool family" folds the two Copilot paths together, giving five families.

**Estimator.** Stratified mean weighted by band population, with finite-population
correction (variance is zero in the two censused bands).

## Result

**12.3% of active public repos carry at least one AI assistant config file**
(95% CI 11.2–13.4).

The unweighted sample rate is 15.4%. Reporting that number would overstate
prevalence by a quarter, because the design deliberately over-samples popular repos.
Weighting by the enumerated frame instead of GitHub's reported band totals gives
12.7% — so the estimate is not sensitive to that choice.

### Adoption rises with popularity — 3.4× across the range

| Stars | n | adopters | rate | 95% CI |
|---|---|---|---|---|
| 10–25 | 800 | 76 | 9.5% | 7.7–11.7 |
| 25–60 | 800 | 90 | 11.2% | 9.2–13.6 |
| 60–150 | 800 | 138 | 17.2% | 14.8–20.0 |
| 150–500 | 800 | 119 | 14.9% | 12.6–17.5 |
| 500–2000 | 788 | 138 | 17.5% | 15.0–20.3 |
| 2000+ | 326 | 105 | **32.2%** | 27.4–37.5 |

The gradient is the robust part of this finding: it is computed *within* strata and
does not depend on the weighting at all. It is near-monotonic (the 150–500 dip is
inside the confidence intervals) and the endpoints do not overlap.

### `AGENTS.md` has overtaken `CLAUDE.md`

| File | repos (sample) |
|---|---|
| `AGENTS.md` | 444 |
| `CLAUDE.md` | 379 |
| `.github/copilot-instructions.md` | 84 |
| `.cursor/rules/` | 41 |
| `GEMINI.md` | 19 |
| `.github/instructions/` | 8 |

On the earlier code-search sample `CLAUDE.md` led. On a proper probability sample the
vendor-neutral standard is ahead — and its margin widens with stars (44/44 tied at
10–25 stars; 80 vs 66 at 2000+). Scoped-rule directories are an order of magnitude
rarer than root instruction files.

### About a third of adopters run more than one tool

**4.25% of all repos** carry ≥2 tool families — **34.6% of adopters**, rising to
**49% of adopters at 2000+ stars**.

| Combination | repos |
|---|---|
| `AGENTS.md` only | 214 |
| **`AGENTS.md` + `CLAUDE.md`** | **170** |
| `CLAUDE.md` only | 155 |
| Copilot only | 34 |
| `AGENTS.md` + `CLAUDE.md` + Copilot | 16 |
| Cursor only | 14 |

This is the number that bears on agentmeld's premise, and it is a real one: a third of
adopters — half of the most-watched projects — maintain config for two or more tools.

But note *which* pair dominates. The single most common multi-tool configuration is
`AGENTS.md` + `CLAUDE.md`, and Claude Code supports `@AGENTS.md` as a one-line import
from `CLAUDE.md`. Some unknown share of those 170 repos have therefore already solved
the problem with one line of Markdown and no tooling. **Open question, and the most
important one for the project's positioning:** of those 170, how many are thin imports
versus genuine duplicates? Until that is measured, "34.6% of adopters have a
multi-tool problem" is an upper bound, not the addressable market.

## Threats to validity

- **`has_file` returns `False` on any exception.** Timeouts, DNS blips, and transient
  5xx are recorded identically to genuine absence, so the bias is always toward
  **undercounting**. Neither slice observed rate-limiting and per-band rates were
  stable across each run, which argues against this happening at scale — but the
  stored records cannot prove it either way. The fix (distinguish 404 from exception,
  retry once) is cheap and should land before this is cited.
- **Frame coverage is uneven.** The 10–25 band enumerated 7,463 of 10,422 reported
  repos (71.6%); every other band is ≥99.8%. If the un-enumerated 28% of that band
  differs systematically from the enumerated 72%, the lowest-rate and highest-weight
  stratum is the one affected. Both weighting schemes are reported above for this
  reason.
- **≥10 stars, recently pushed.** This is deliberately a sample of *active, visible*
  repos, not of all of GitHub. Prevalence across all public repos is certainly lower.
- **Existence is not use.** A committed `CLAUDE.md` may be stale, vendored from a
  template, or copied from a starter kit. This measures files, not behaviour.
- **Public repos only**, and adoption inside companies is plausibly very different.
