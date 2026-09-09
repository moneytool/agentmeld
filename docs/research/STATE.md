# Project state — 2026-09-08 (probe complete)

Written so this work can be resumed cold. Everything here is fact, with the
uncertain parts marked.

---

## Shipped

**agentmeld 0.1.4** on PyPI. https://github.com/moneytool/agentmeld

| Version | Contents |
|---|---|
| 0.1.0 | first release. **Contains a data-loss bug** — moved `.gemini/settings.json` (all of Gemini's settings, not just MCP) into the canonical tree. Should be yanked on PyPI. |
| 0.1.1 | data-loss fix; `agentmeld restore`; JSONC comment warning; exact-match hook removal |
| 0.1.2 | Gemini TOML command adoption (completes the round trip) |
| 0.1.3 | `doctor` reports rules with no automatic trigger |
| 0.1.4 | corrected `doctor` wording — those rules are *manual*, not dead (PR #17) |

### Repo gotchas

- **Never merge PRs.** The owner reviews and merges. Do not use `gh pr merge --admin`.
- **Never post to GitHub** (issues, comments, PRs) without being asked explicitly.
- The `PEER Review` ruleset requires **2 approving reviews**, which a solo
  maintainer cannot satisfy — every merge needs an admin bypass. Unresolved.
- The bump workflow fails at `gh pr create`: the repo setting
  `can_approve_pull_request_reviews` gates it and does not persist. A subagent
  investigated and recommends **dropping `gh pr create`** and printing a compare
  link instead — it needs no secret and cannot regress. Not yet implemented.
- Copilot auto-review was disabled by the owner (was burning credits on
  two-line release PRs).

---

## Research

Six findings in `findings/`, three datasets in `data/`, collectors in `scripts/`.
Read `README.md` first — it carries the method lessons, which are the most
transferable part.

**Status of each:**

| # | Finding | Confidence |
|---|---|---|
| 01 | 35% of repos carry 2+ configs; 20% of those already symlink | frame biased; **the 35% is confirmed on the good frame** as 34.6% *of adopters* — see 07 |
| 02 | median 31.9% of a rule set matches a typical file | **frame is wrong — see below** |
| 03 | 21.4% of rules have no automatic trigger | **frame is wrong**; claim already corrected once |
| 04 | scoping can cost more than monolithic under caching | analysis; **recommend cutting from any paper** |
| 05 | 14.9% of scoped rules match nothing | **frame is wrong**; own parser bug corrected once |
| 06 | rule count does not affect adherence; models barely differ | **most carefully checked**; 135 runs, code stored |
| 07 | **12.3% of active repos carry AI config; 9.5% → 32.2% by stars; `AGENTS.md` > `CLAUDE.md`** | **primary result**; frozen frame, n=4,314, stratified + weighted |

### The frame problem (important)

Findings 01, 02, 03 and 05 were measured on repos found via GitHub **code
search** for config filenames. That guarantees config-carrying, rule-heavy
repos, so those rates describe "repos that use scoped rules", not repos in
general.

A proper sampling frame (below) shows `.cursor/rules` in only ~0.6-1.0% of
active repos, while `CLAUDE.md`/`AGENTS.md` sit near 10% each. **The scoped-rule
findings therefore describe under 1% of repositories.** Recompute them on the
new frame, or state the selection openly as "among repos that use scoped rules".

---

## Sampling frame (`sampling/`)

Built after two failed designs. Current design in `sampling/build-frame.py`:

- **Population:** `>=10 stars, fork:false, archived:false, pushed:>2026-03-01`,
  created 2023-01-01 to 2026-09-01
- **Cells:** 576 = 6 star bands x 14-day creation windows
- **Cluster sample:** 48 cells (8 per band) chosen with a fixed seed, each
  harvested completely
- **Weights:** each cell records its true `total`, so estimates are weighted by
  real stratum sizes
- **Frozen pool:** 18,913 repos, fingerprint `8fd846e908911bf9`
  (`sampling/frozen-repo-list.json`, metadata in `frozen-meta.json`)

**Known limitation:** 2 of 48 cells hit GitHub's 1,000-result cap, both in the
10-25 band (populations 1,395 and 3,564; 2,959 repos unreachable). Measured, not
hidden.

**Why the first two attempts failed** — worth not repeating:

1. The builder restarted at the first stratum every invocation, so 59% of the
   pool landed in one star band, and the pool grew *during* probing, so parallel
   "slices" were never disjoint.
2. The second paid a separate API call to count each window before splitting it.
   A subagent correctly diagnosed that this could never finish in a bounded run
   and stopped rather than working around it. The fix was realising the search
   response already returns `total_count`, making the whole count phase redundant.

**Probe complete.** Two agents probed 4,314 repos in disjoint slices (verified
0 overlap) into `data/probe-slice-{a,b}.json`, summarised in
`data/probe-summary.json`. Results are finding **07**, which supersedes the
prevalence numbers in 01–03/05.

The 10-25 band enumerated 7,463 of GitHub's reported 10,422 (71.6%); every other
band is >=99.8%, and the two smallest were probed as a **census**. Finding 07
reports the estimate under both weighting schemes (12.3% vs 12.7%) so this
coverage gap is visible rather than assumed away.

---

## Numbers that are retired

Do not quote these; they were measured wrong and are recorded only so the same
errors are not made twice.

| Claim | Reality |
|---|---|
| "87% of config pairs diverge" | symlink pointer text compared against file content |
| "25.3% of scoped rules are stale" | brace-expansion parser bug; correct figure 14.9% |
| "Gemini collapses to 33% on constant naming" | my checker counted `logger = logging.getLogger(__name__)` as a badly-named constant |
| "17.3% of repos carry AI config" | unweighted average over a pool that was 59% one star band |
| "rules with no globs can never load" | that is Cursor's documented "Apply Manually" type; it loads on @-mention |

---

## Paper plan

Recommended shape, if pursued:

- **One claim**, not four. The adoption study is now the stronger candidate:
  finding 07 has a frozen, fingerprinted frame, a weighted estimator, a 3.4x
  monotonic gradient, and a standard-displacement result (`AGENTS.md` overtaking
  `CLAUDE.md`). The defect study rests on a frame that guarantees its own subject.
- Venue: **MSR**, deadline typically December-January.
- Cut finding 04 (vendor pricing, dates fast).
- Finding 06 works as a secondary section.
- Needed before submission: manual validation by a second **human** rater with
  Cohen's kappa; a content taxonomy; gitignore-aware `path_absent`; a replication
  package with a DOI.
- An LLM cannot be the independent second rater here — the checkers were
  LLM-written, so LLM validation is not independent.

**Honest expectation:** a first MSR paper earns single-digit citations over
years. It is a credential, not a lever.

---

## Promotion

- **LinkedIn:** posted.
- **HN:** posted, https://news.ycombinator.com/item?id=49600009 — 2 points.
  Data says config tools do badly on HN (rulesync, at 5M downloads, never
  cleared 2 points across five submissions).
- **r/ClaudeAI:** removed twice. First for failing Showcase criteria (fixed);
  second for a **minimum karma requirement**, which cannot be edited around.
  Redirected to the Build with Claude Showcase Megathread, where a comment has
  no karma gate.
- **Suggested next:** r/devtools, r/AIcodingProfessionals (both proposed by
  Reddit itself). Use the educational framing there, not "built with Claude".
- **awesome-claude-code:** eligible **2026-09-20** (14 days from first commit,
  or immediately at 100 stars). Submit via the **issue form**, not a PR.
  awesome-cursorrules and awesome-ai-agents are the **wrong lists** — they take
  rule files and autonomous agents respectively.

---

## Outstanding

1. **Measure the `AGENTS.md` + `CLAUDE.md` pair (170 repos in the sample).** How
   many have `CLAUDE.md` as a thin `@AGENTS.md` import rather than a duplicate?
   This is the single most important open number: it separates agentmeld's real
   addressable problem from a problem the ecosystem already solved in one line.
   Watch for the symlink-pointer trap — `raw.githubusercontent` serves the link
   *target text* for a symlink, which once produced a bogus divergence figure.
2. Fix `has_file`: distinguish 404 from exception and retry once, so a network
   error stops being indistinguishable from absence. Do this before finding 07 is
   cited anywhere.
3. Recompute findings 02/03/05 on the new frame, or re-scope their claims
4. Yank 0.1.0 from PyPI (data-loss bug) — needs the owner's PyPI login
5. Fix the bump workflow (drop `gh pr create`)
6. Trim the 51-second README demo GIF to ~20s
7. Manually inspect Gemini's `annotations` 80% — the last unexplained
   cross-model gap, and this project's history says check before quoting
