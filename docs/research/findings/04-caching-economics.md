# Finding 4: loading less context can cost more

**Date:** 2026-09-08 · **Status:** analysis + one external experimental run

## The mechanism

Prompt caching prices repeated context very differently from new context:

| | Multiplier on base input price |
|---|---|
| Uncached input | 1.0× |
| Cache **write** (first time) | 1.25× |
| Cache **read** (subsequent) | ~0.1× |

Caching is a **prefix match** — any byte change anywhere in the prefix
invalidates everything after it. Render order is `tools` → `system` → `messages`.
Default TTL is 5 minutes; 1 hour is available. Minimum cacheable prefix is
512–4096 tokens, model-dependent.

## The consequence

A repo with 10,000 tokens of rules:

**Monolithic** — everything loaded, byte-identical each request:
- first request: 10,000 × 1.25 = **12,500** token-equivalents
- each subsequent warm request: 10,000 × 0.1 = **1,000**

**Scoped** — only matching rules, so content varies per request:
- every request: 2,000 × 1.0 = **2,000**

The scoped version loads **5× fewer tokens and costs twice as much**, because
varying the prefix defeats the cache.

**Break-even: scoping wins only when the matched subset is under ~10% of the
full rule set.**

## Experimental run (performed externally, via Copilot)

30 rules, ~11.6K-token rule block, Claude Haiku 4.5:

| Condition | Avg priced tokens/call | Cached? |
|---|---|---|
| Monolithic, warm | 1,175 | yes (11,653 @ 0.1×) |
| Scoped, warm | 411 | no |
| Monolithic, cold (TTL expired) | 7,876 | second call paid 1.25× = 14,576 |
| Scoped, cold | 411 | no |

That run concluded "scoping is the right default."

## Why that conclusion does not follow

1. **The scoped subset was 3.5% of the rule set** — comfortably inside the
   winning region. The result was determined by the chosen ratio, not
   discovered. Measured reality is **31.9%** (`findings/02`), where the
   comparison reverses.
2. **411 tokens is below the minimum cacheable prefix** (512–4096). "Scoped
   never caches" may be an artifact of *size*, not of *variation* — two
   different mechanisms with different implications, which the design cannot
   distinguish.

## What survives

- **Cold cache: scoping wins decisively at any ratio.** Monolithic re-pays 1.25×
  on every expiry (14,576 vs 411 — a 35× gap). This is mechanism, not parameter
  choice.
- **Warm cache: monolithic wins for ~72% of real repos** (`findings/02`).

Honest statement: *it depends on the matched-subset ratio and on request
cadence, and most real repos sit on the side where scoping costs more when the
cache is warm.*

## The design this suggests

Because caching is prefix-matched, **partition by volatility rather than volume**:

1. stable content (instructions, always-on rules) first, with a cache breakpoint
   after it → charged at ~0.1×
2. scoped, varying rules *after* the breakpoint → they change without
   invalidating anything before them
3. full price paid only on the small varying portion

Unvalidated.

## Open

- Re-run the experiment at a **31%** ratio to confirm the flip empirically
- Quality side: the false-negative rate when a relevant rule fails to match
- Other vendors cache differently; results here are Anthropic-specific
