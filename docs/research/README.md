# agentmeld research

Working notes, datasets and collectors behind agentmeld — a lab notebook, not
documentation. Kept on the `research` branch, off `main`.

Everything here is preliminary unless a document says otherwise. Sample sizes
and sampling bias are stated in each file; read the caveats before quoting a
number.

## Findings

| # | Finding | Headline | Confidence |
|---|---|---|---|
| [01](findings/01-config-fragmentation.md) | Repos carry multiple AI configs and they diverge | 35% carry 2+; 20% of those already symlink | preliminary, n=150 |
| [02](findings/02-glob-match-ratios.md) | A typical edit loads ~32% of the rule set | median 31.9%; only 7% of repos below the 10% break-even | stable across n=21→120 |
| [03](findings/03-dead-rules.md) | ~21% of rules have no automatic trigger | 207 of 1,001 rules; loads only on @-mention | strong among adopters |
| [04](findings/04-caching-economics.md) | Loading less context can cost more | scoping loses for ~72% of repos on a warm cache | analysis + 1 external run |
| [05](findings/05-stale-globs.md) | Scoped rules that match nothing | 14.9% of scoped rules match zero files | preliminary, n=60 |
| [06](findings/06-adherence.md) | Rule count does not affect adherence; models barely differ | all 9 cells within 96.4-100% | **most carefully checked** |
| [07](findings/07-prevalence-stratified.md) | How common AI config actually is | 12.3% of active repos; 9.5%→32.2% by stars; `AGENTS.md` has overtaken `CLAUDE.md` | **primary result**; frozen frame, n=4,314 |

Finding **07 supersedes the prevalence rates in 01–03 and 05**. Those were
measured on a GitHub code-search sample, which by construction only returns repos
that already have the file being counted — fine for describing adopters, useless
for estimating how many adopters there are. 07 uses a frozen, fingerprinted
probability frame with population weights.

## Problem statements

Both are now answered by [finding 06](findings/06-adherence.md), though the
briefs remain useful as self-contained descriptions of the questions.

- [Problem 3: context economics](problem-3-context-economics.md) — **answered.**
  Cost: scoping loses for ~72% of repos on a warm cache (finding 04). Quality:
  rule-set size has no measurable effect on adherence up to 120 rules
  (finding 06). Scoping's remaining justification is context-window pressure,
  which is not binding at these sizes.
- [Problem 4: semantic fidelity](problem-4-semantic-fidelity.md) — **largely
  answered.** Identical instruction text transfers across Claude, GPT-5 and
  Gemini for mechanically-checkable rules: seven of ten at 98%+ everywhere. This
  contradicts the critique that per-model variants are architecturally
  necessary. The untested half is nuanced, hard-to-score rules, which is where
  portability is most likely to fail.

## Layout

```
findings/   written-up results, with method and caveats
data/       raw JSON from the collectors
scripts/    the collectors themselves, re-runnable
```

| Dataset | Rows | Collector |
|---|---|---|
| `data/probe-slice-{a,b}.json` | 4,314 repos | `sampling/probe-frame.py` (analysis: `scripts/analyze-prevalence.py`) |
| `data/config-cooccurrence.json` | 150 repos probed | `scripts/collect-config-cooccurrence.py` |
| `data/config-cooccurrence-typed.json` | multi-config repos, file types resolved | — |
| `data/glob-ratios.json` | 120 repos / 1,001 rules | `scripts/collect-glob-ratios.py` |

Both collectors use the `gh` CLI for GitHub API access and
`raw.githubusercontent.com` for file contents. Neither needs an LLM API key and
neither costs anything to run.

## Method lessons worth not relearning

Recorded because each of these silently produced a wrong answer first:

1. **`raw.githubusercontent.com` returns link target text for a symlink**, not
   the file contents. A 9-byte response is a pointer, not an empty file.
2. **The contents API resolves symlinks** when fetching a file directly and
   reports `type: file`. Only the *directory listing* exposes the link.
3. **`SequenceMatcher` is dominated by length differences** on long documents.
   It gave 0.019 where Jaccard gave 0.246 on the same pairs. Use token overlap
   for documents of differing length.
4. **A null result from an API is worthless until the method is validated on a
   known positive.** A TMview trademark query returned empty for a name we knew
   was registered — proving the query was broken, not the name clear.
5. **Background collectors die when the parent shell exits.** Use `nohup`, and
   write partial results to disk as you go. In this sandbox even detached
   processes are killed; the pattern that works is a bounded subprocess
   (~100s) invoked repeatedly against a resumable, idempotent runner.
6. **Concurrent writers clobber a shared JSON file.** Two processes that each
   read-then-write the whole list will silently lose records. Give each writer
   its own file, or re-read under a lock before every save.
7. **Persist raw artifacts, not just verdicts.** Storing only pass/fail booleans
   meant a checker fix cost a full 135-call re-run. Store the generated output.
8. **An automated metric nobody has eyeballed at the row level is not
   evidence.** Three separate results here were confident, plausible and wrong,
   and each died on first contact with an individual row:
   - "87% of config pairs diverge" — was symlink pointer text
   - "25.3% of scoped rules are stale" — was a brace-expansion parser bug
   - "Gemini collapses to 33%" — was `logger = logging.getLogger(__name__)`
   The last is the sharpest: the model was penalised *for complying* with a
   different rule. Inspect the failures before quoting the aggregate.

## Status

Nothing here is publication-grade. The gap to publishable is a defensible
sampling frame (GH Archive or BigQuery rather than relevance-ranked code
search), an order of magnitude more repos, and manual qualitative coding of a
subsample.
