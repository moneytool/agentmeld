# Finding 1: repos carry multiple AI configs, and they diverge

**Date:** 2026-09-08 · **Status:** preliminary · **Data:** `data/config-cooccurrence.json`
**Collector:** `scripts/collect-config-cooccurrence.py`

> **Superseded for prevalence.** The rates here come from a GitHub code-search
> sample, which only returns repos that already contain the file being counted.
> They describe *adopters*, not repositories in general. For population rates see
> [finding 07](07-prevalence-stratified.md).

## Question

Do repositories carry configuration for more than one AI coding assistant, and
when they do, does the content diverge?

## Method

Sampled repos from GitHub code search for `CLAUDE.md`, `AGENTS.md`,
`copilot-instructions.md`, `GEMINI.md`, `.cursorrules`. For each repo, probed all
five paths via `raw.githubusercontent.com` and compared any pair that existed,
using both `difflib.SequenceMatcher` and token Jaccard on normalised text (code
blocks stripped, lowercased, punctuation removed).

## Population size

Whole-of-GitHub counts from code search:

| File | Repos (approx) |
|---|---|
| `AGENTS.md` | 972,800 |
| `CLAUDE.md` | 770,048 |
| `copilot-instructions.md` | 163,328 |
| `GEMINI.md` | 69,504 |
| `.cursorrules` | 32,512 |

## Results (n = 150 repos probed, 122 with ≥1 config)

- **35% carried two or more** AI config files
- Most common pairing by far: `AGENTS.md` + `CLAUDE.md`
- **20% of multi-config repos already use a symlink** to unify them — developers
  independently converged on the approach agentmeld automates
- Of repos keeping genuinely separate files, Jaccard median **0.246**: they share
  roughly a quarter of their vocabulary
- 17.8% were near-copies (Jaccard > 0.5); 42.6% largely independent (< 0.2)

An illustrative near-copy pair (`0x3639/go-syrius`):

> `CLAUDE.md`: "This file provides guidance to Claude Code (claude.ai/code)…"
> `AGENTS.md`: "This file provides guidance to Codex (Codex.ai/code)…"

94% identical — copy-pasted with the tool name swapped.

## Interpretation

Two distinct populations, not one behaviour:

1. **copy-paste duplicates** that then drift
2. **genuinely independent documents** written separately per tool

Characterising both is a better contribution than a single "drift rate".

## Method corrections made along the way

Three, all of which invalidated an earlier version of this result:

1. **Symlink contamination.** `raw.githubusercontent.com` returns the link
   *target text* for a symlink, so a 9-byte pointer was being compared against
   5 KB of content and scored as total divergence.
2. **Wrong API field.** The contents API resolves symlinks when fetching a file
   directly and reports `type: file`; only the *directory listing* exposes the
   link (`size: 9`).
3. **Wrong similarity metric.** `SequenceMatcher` is dominated by length
   differences on long documents — median 0.019 where Jaccard gave 0.246.
   Jaccard is the defensible choice here.

## Caveats

- n = 150 sampled repos; GitHub code search is relevance-ranked, not random
- Similarity is lexical, not semantic
- No manual qualitative coding of *how* pairs differ

## To make this publishable

Sampling frame from GH Archive or the BigQuery GitHub dataset; 5,000+ repos;
manual coding of ~100 pairs; a longitudinal slice showing adoption growth.
