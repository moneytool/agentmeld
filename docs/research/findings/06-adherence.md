# Finding 6: rule-set size does not affect adherence, and models barely differ

**Date:** 2026-09-08 · **Status:** the most carefully checked result here
**Data:** `data/adherence-{claude,gpt5,gemini}.json` (135 runs, generated code included)
**Scripts:** `scripts/adherence-rules.py`, `scripts/adherence-run-*.py`

## Questions

This answers both open problem statements at once:

- **Problem 3** — does adherence degrade as the rule set grows? (The real reason
  to scope, once the cost argument collapsed — see [finding 04](04-caching-economics.md).)
- **Problem 4** — does identical instruction text produce the same behaviour
  across vendors?

## Method

Ten project rules whose compliance can be verified by parsing the generated
Python — no human judgement, no LLM-as-judge. Examples: *use `pathlib`, never
`os.path`*; *never use `print()`*; *annotate every function*; *no bare `except:`*.

Design: **3 rule-set sizes (10, 40, 120) x 5 coding tasks x 3 repetitions x 3
models = 135 runs.** The ten checkable rules appear in every condition; the
remainder is filler, so the only variable is how much other material surrounds
them. Rule order is shuffled per run and recorded.

Models: `claude-opus-5`, `gpt-5`, `gemini-2.5-pro`.

## Results

| Model | 10 rules | 40 rules | 120 rules | spread |
|---|---|---|---|---|
| claude-opus-5 | 100.0% | 99.2% | 99.3% | 0.8 |
| gpt-5 | 99.3% | 97.9% | 99.3% | 1.5 |
| gemini-2.5-pro | 96.9% | 97.1% | 96.4% | 0.7 |

**All nine cells fall between 96.4% and 100% — a total range of 3.6 points.**

Per rule, pooled across sizes:

| Rule | claude | gpt-5 | gemini |
|---|---|---|---|
| annotations | 96% | 98% | **80%** |
| docstrings | 100% | 93% | 98% |
| explicit-encoding | 100% | 97% | 97% |
| no-print | 100% | 100% | 98% |
| pathlib | 100% | 100% | 98% |
| british, constants-upper, fstrings, no-bare-except, no-mutable-default | 100% | 100% | 100% |

## Interpretation

**Problem 3: rule count has no effect.** Every model's spread across a 12x
increase in rule-set size is under 1.5 points, inside run-to-run noise. There is
no adherence-based reason to scope rules at these sizes.

Combined with finding 04 (scoping loses money for ~72% of repos on a warm
cache), scoping's remaining justification is context-window pressure, which is
not binding at 120 rules.

**Problem 4: semantic portability largely holds.** Five of ten rules are at 100%
on all three vendors; seven are at 98% or better. The single real difference is
`annotations` (Gemini 80% vs 96-98%).

This **contradicts** the architectural critique that shared instruction text
needs per-model variants. For mechanically-checkable project rules, identical
text transfers. One canonical file mirrored everywhere is defensible on this
evidence.

## The correction that matters more than the result

An earlier version of this experiment reported:

| Model | 10 | 40 | 120 |
|---|---|---|---|
| claude-opus-5 | 99.3% | 96.2% | 96.2% |
| gpt-5 | 97.9% | 97.1% | 98.7% |
| gemini-2.5-pro | **89.8%** | **91.7%** | **92.1%** |

with `constants-upper` at **33% for Gemini** — reported at the time as "the
answer to Problem 4: semantic portability fails sharply for specific rules".

**That was entirely a bug in my checker.** Three checkers penalised correct code:

1. **`constants-upper`** flagged *any* lowercase module-level assignment,
   including `logger = logging.getLogger(__name__)` — the standard Python idiom,
   and not a constant at all. Fixed to flag only assignments binding a literal.
   Gemini: 33% -> **100%**.
2. **`explicit-encoding`** demanded `encoding=` on every `open()`, including
   binary mode, where the argument is invalid. Gemini: 81% -> **97%**.
3. **`british`** scanned all source, so a library keyword argument such as
   `color="red"` counted as American spelling. Fixed to scan comments and
   docstrings only.

The first was the worst kind of error: Gemini followed the `no-print` rule by
using `logging`, which requires a module logger — so **complying with one rule
caused my checker to record a violation of another.** The model was penalised
precisely for obedience.

The correction raised every model (Claude +3.1 at 120 rules, Gemini +7.2 at 10)
and collapsed the apparent cross-model gap from ~8 points to ~2.5.

**Had this not been checked, the published claim would have been: "Gemini follows
shared instructions markedly worse than Claude or GPT-5, collapsing to 33% on
constant naming." Confident, specific, quantified, and false.**

## Caveats

- n=15 per cell
- Ten rules, all mechanically checkable, which biases toward simple, explicit
  instructions. Nuanced rules — the ones most likely to transfer badly — are the
  hardest to score and are not represented here. **This is the main threat to
  the Problem 4 conclusion.**
- One task family (small self-contained Python modules)
- Single-turn generation; no agentic loop, no tool use, no long context
- `annotations` at 80% for Gemini has not been manually inspected. Given this
  document's own history, it should be, before it is quoted.

## Reusability

Every record stores the generated code. A checker change can be re-scored
offline at zero API cost — the omission of this in the first pass is what made a
135-call re-run necessary.
