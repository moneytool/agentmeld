# Finding 8: the `AGENTS.md` + `CLAUDE.md` pair is mostly already solved

**Date:** 2026-09-08 · **Status:** primary result · **Data:**
`data/agents-claude-pairs.json` · **Scripts:**
`scripts/classify-agents-claude-pairs.py`, `scripts/report-agents-claude-pairs.py`

This answers the open question left by [finding 07](07-prevalence-stratified.md),
and it is the least comfortable result in this folder: **for the most common
multi-tool configuration, the duplication agentmeld exists to remove is rare.**

## Question

Finding 07 established that 34.6% of adopters carry two or more tool families,
and that the dominant combination is `AGENTS.md` + `CLAUDE.md`. Claude Code reads
`@AGENTS.md` as a one-line import. So: of the repos carrying both, how many
actually maintain two copies of the same knowledge, and how many have already
reduced it to one source?

## Method

All 210 repos in the finding-07 sample carrying both files (170 carry *only*
that pair; 40 also run Copilot or Cursor). For each, the root tree from the git
trees API, then the blobs.

**Symlinks are detected by git file mode (`120000`), not by content.** This is
load-bearing. The raw content endpoint serves a symlink's *target path text*, so
a 9-byte pointer fetched that way looks like total divergence from a 5 KB file —
the exact bug that produced a retired "87% of config pairs diverge" figure
earlier in this programme. The first repo in the list is such a case.

Content overlap is Jaccard on token sets, not `SequenceMatcher`, which has a
length bias that put the same pairs at 0.019 vs 0.246.

## Result

| Class | n | % |
|---|---|---|
| **symlink** — one file *is* the other | 67 | 31.9% |
| **thin import** — `@AGENTS.md`, ≤200 B of own content | 58 | 27.6% |
| import + small overlay (≤1 KB own content) | 9 | 4.3% |
| byte-identical copies | 7 | 3.3% |
| near-identical (Jaccard ≥ 0.90) | 5 | 2.4% |
| genuinely different content | 64 | 30.5% |

Rolled up:

- **59.5% already have one source of truth** — a symlink or a one-line import.
- **5.7% maintain two copies.** That is the duplication problem, and it is 12
  repos out of 210.
- **30.5% carry deliberately different content** in the two files.

Median token overlap between the two files is **0.079**. The distribution is
strongly bimodal: 77 pairs below 0.1, and a separate spike of 12 above 0.9.
There is very little in between — repos either point one file at the other, or
write genuinely different things. Almost nobody writes *nearly* the same thing
twice.

Single-sourcing does not fall off with popularity — 58% in the 10–25 star band,
71% at 2000+. The practice is not confined to sophisticated projects.

### The divergent 30% are not a hidden duplication problem

19 of the 64 divergent repos mention `AGENTS.md` anyway, which raised the
possibility that they are verbose pointers misfiled as divergent. Re-fetched and
measured by non-heading, non-reference content: **18 of 19 carry substantial
content of their own** (median 5.7 KB); exactly one was a pointer document, and
it is counted as a thin import above.

Spot-checking what the divergent `CLAUDE.md` files contain: release procedure,
CI specifics, tool-invocation detail. It is Claude-Code-specific operational
knowledge, not a second copy of the project description.

## What this means for agentmeld

The honest reading is that this pair is **not** a duplication problem:

- Three fifths have already solved it, without tooling, in one line.
- Of the rest, most are deliberately writing different content per tool — and
  for those, a syncer that mirrors one file into the other would **destroy
  information**, not save effort.
- The genuinely-duplicated population is 5.7% of pairs, which against finding
  07's 4.25% of all repos carrying ≥2 families works out to roughly **0.2% of
  active public repos**.

This is direct evidence for the external critique that the vendor-neutral
convergence is closing the gap agentmeld's symlink strategy targets — and it
arrives from our own data rather than from argument. Note the shape of the
evidence, though: 31.9% of these repos reached single-sourcing *by symlinking*,
which is the mechanism agentmeld automates. The practice is validated; what is
in question is whether it needs a tool.

Two things this does **not** settle, and they are where any remaining case lives:

1. **It measures one pair.** `.cursor/rules` (`.mdc` frontmatter), Copilot's
   `applyTo`, and Gemini's TOML commands cannot be symlinked into each other at
   all — those need generation, and this finding says nothing about them. They
   are also, per finding 07, an order of magnitude rarer.
2. **It measures files, not effort.** A repo whose two files diverge may be
   diverged because keeping them in sync was too much work, which is a problem
   a tool could address. Nothing here distinguishes deliberate divergence from
   neglected divergence.

## Threats to validity

- The **1 KB boundary** between "import + overlay" and "divergent" is a judgment
  call, not a principled cut. It affects 9 repos; moving it does not change the
  rolled-up picture.
- **`points_at_agents` is a substring match**, so a `CLAUDE.md` that mentions
  `AGENTS.md` only in passing counts as referencing it. The re-examination above
  bounds the damage: 18 of 19 such cases had real content regardless.
- **HEAD, not the commit probed.** A handful of repos may have changed between
  the finding-07 probe and this classification; all 210 still had both files.
- Content classification is automated. A second **human** rater with a kappa
  score is required before this is published — the same requirement recorded for
  every other finding here.
