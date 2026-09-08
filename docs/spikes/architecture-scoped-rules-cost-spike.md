---
title: "Does scoped rule loading actually reduce AI cost under prompt caching?"
category: "Architecture & Design"
status: "🔴 Not Started"
priority: "High"
timebox: "2 weeks"
created: 2026-09-08
updated: 2026-09-08
owner: "moneytool"
tags: ["technical-spike", "architecture", "prompt-caching", "cost-optimization", "research"]
---

# Does scoped rule loading actually reduce AI cost under prompt caching?

## Summary

**Spike Objective:** Determine whether per-file rule scoping (`globs:` in Cursor, `applyTo:` in Copilot) reduces token cost compared to monolithic loading, given prompt caching's prefix-match behaviour and pricing multipliers.

**Why This Matters:** agentmeld carries scoping metadata across tools under the assumption that loading fewer tokens costs less. If prompt caching inverts this assumption, agentmeld's architecture optimises the wrong quantity. The result affects every multi-tool AI configuration system, not just agentmeld.

**Timebox:** 2 weeks (experiment design + execution + analysis)

**Decision Deadline:** Before agentmeld v0.2.0 feature freeze — the answer changes whether we partition rules by volatility instead of by file scope.

## Research Question(s)

**Primary Question:** Does loading scoped rules (subset matching the current file) cost less than loading all rules monolithically, under realistic prompt-caching behaviour?

**Secondary Questions:**

- How does request cadence (rapid iteration vs. sparse work) interact with the 5-minute cache TTL to change the answer?
- Can a volatility-partitioned layout (stable prefix + varying suffix) deliver both cache efficiency and scoping precision?
- Does scoping introduce false negatives (relevant rules not loaded) that hurt output quality?
- What is the break-even point where scoped subset size crosses monolithic cost?

## Investigation Plan

### Research Tasks

- [ ] Survey vendor documentation on prompt caching pricing and TTL (Anthropic, OpenAI, Google, GitHub Copilot internals where public)
- [ ] Identify minimum cacheable prefix thresholds for each target model family
- [ ] Design 2×2 experimental matrix: {monolithic, scoped} × {cache warm, cache cold}
- [ ] Build a test harness that sends controlled prompts with measured `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`, `usage.input_tokens`
- [ ] Write programmatically verifiable rules (e.g., "use pytest fixtures, not setUp") for quality measurement
- [ ] Create a test repo with realistic instruction/rule volume (~5,000–15,000 tokens total)
- [ ] Run cost experiments across request cadences: rapid (30s interval), medium (3min), sparse (10min)
- [ ] Run quality experiments: deliberately out-of-scope tasks where a rule is relevant but unmatched
- [ ] Analyse results: break-even curve, TTL sensitivity, volatility partition simulation
- [ ] Write up findings and recommendation

### Success Criteria

**This spike is complete when:**

- [ ] Cost per token measured for both monolithic and scoped loading across warm/cold cache conditions
- [ ] Break-even ratio (scoped subset / total rules) identified for at least one model
- [ ] Request cadence impact quantified (rapid vs. sparse cost comparison)
- [ ] Quality false-negative rate measured (rules missed due to glob mismatch)
- [ ] Clear recommendation documented for agentmeld's rule partitioning strategy
- [ ] Results written up in a format suitable for blog post / conference talk

## Technical Context

**Related Components:**
- `src/agentmeld/planner.py` — `_plan_instructions` (aggregate strategy folds all rules)
- `src/agentmeld/transform/aggregate.py` — how rules are concatenated into single-document tools
- `src/agentmeld/registry/adapters/copilot.toml` — `applyTo` scoping
- `src/agentmeld/registry/adapters/cursor.toml` — `globs`/`alwaysApply` scoping
- `.ai/rules/*.md` — canonical rule format with `globs:` frontmatter

**Dependencies:**
- Requires access to Anthropic API (or equivalent) with usage metering
- Requires budget approval for API costs (estimated < $50 for full experiment matrix)
- No blocking dependencies on other spikes

**Constraints:**
- Each experimental run costs real money — budget approval required before scale runs
- Model choice is a confound — must hold model constant or treat as explicit variable
- Cache TTL varies by vendor — 5min default (Anthropic), may differ elsewhere
- Minimum cacheable prefix (512–4096 tokens) is model-dependent — below threshold, "smaller is cheaper" and the analysis collapses

## Experiment Design

### Cost Experiment

| | Cache Warm | Cache Cold |
|---|---|---|
| **Monolithic** | all rules loaded, expect ~0.1× on repeat | all rules loaded, first call pays 1.25× |
| **Scoped** | only matching rules, cache miss per scope change | only matching rules, pays 1.0× every time |

Cross with cadence: rapid (30s), medium (3min), sparse (10min — past 5-min TTL).

**Pricing model** (Anthropic example):
| Type | Multiplier |
|---|---|
| Uncached input | 1.0× |
| Cache write | 1.25× |
| Cache read | ~0.1× |

**Key metric:** `usage.cache_read_input_tokens` must be > 0 on warm runs. If zero, prefix invalidation is silently happening (timestamp, UUID, unsorted JSON). Verify before trusting results.

### Quality Experiment

Write rules with programmatically checkable compliance:
- "Use pytest fixtures, not setUp" → scan output for `setUp`
- "Use dataclasses, not namedtuples" → scan output for `namedtuple`
- "Return early, no else blocks" → scan for `else:` after `return`

Construct tasks where a rule is relevant but its `globs:` pattern does not match the target file. Measure how often the model violates the rule it never saw.

## Known Pitfalls

- **Minimum cacheable prefix**: 512–4096 tokens depending on model. Below this, nothing caches and "smaller is cheaper" trivially.
- **Prefix invalidation sources**: timestamps, UUIDs, unsorted JSON, varying tool lists, model version changes. Any of these silently zero out `cache_read_input_tokens`.
- **Tokenizer differences**: different models tokenize the same text differently. Hold model fixed.
- **Vendor pricing differences**: Anthropic, OpenAI, Google each have different cache pricing. Results for one vendor may not generalise.
- **Hawthorne effect in quality measurement**: if the model "knows" it is being tested on rule compliance, results may be skewed. Use natural-seeming prompts.

## The Counterintuitive Hypothesis

Loading less context can cost more. Worked example with 10,000 tokens of rules:

| Strategy | First call | Repeat (warm) | Repeat (cold) |
|---|---|---|---|
| Monolithic | 10K × 1.25 = 12,500 | 10K × 0.1 = 1,000 | 12,500 again |
| Scoped (20% match) | 2K × 1.0 = 2,000 | 2K × 1.0 = 2,000 | 2K × 1.0 = 2,000 |

Scoped loads 5× fewer tokens but pays 2× on warm cache. Break-even: scoped wins only when subset < ~10% of full set (warm) or when cache always expires (sparse cadence).

## Status History

| Date | Status | Notes |
|------|--------|-------|
| 2026-09-08 | 🔴 Not Started | Spike created from promotion-readiness analysis |

---

_Last updated: 2026-09-08 by moneytool_
