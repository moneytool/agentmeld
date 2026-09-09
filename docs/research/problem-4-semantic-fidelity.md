# Problem 4: Semantic fidelity across models

**Status:** open, entirely unexamined
**Prerequisite reading:** none — this document is self-contained

---

## Background you need

AI coding assistants are configured through files committed to a repository.
Different tools read different files in different formats:

- Claude Code reads `CLAUDE.md`
- GitHub Copilot reads `.github/copilot-instructions.md`, and scoped rules from
  `.github/instructions/*.instructions.md` using an `applyTo:` frontmatter key
- Cursor reads `AGENTS.md`, and rules from `.cursor/rules/*.mdc` using `globs:`
  and `alwaysApply:`
- Gemini CLI reads `GEMINI.md`, and stores commands as **TOML** with a `prompt`
  key rather than Markdown

**agentmeld** (https://github.com/moneytool/agentmeld) keeps one canonical copy
of this content and mirrors it into each location — a symlink where formats
agree, a generated file where they differ.

Its promise is "one source of truth, every agent." That promise contains an
assumption nobody has tested.

---

## The problem

agentmeld solves **syntactic** portability: getting the same text into the right
file, in the right format, with the right frontmatter keys.

It assumes **semantic** portability follows — that the same instruction produces
the same behaviour regardless of which model reads it.

That assumption is unexamined, and there are concrete reasons to doubt it:

- models differ in how strongly they follow instructions, and in how they
  weight instructions against the immediate request
- models differ in sensitivity to phrasing, ordering, emphasis, and formatting
- an instruction tuned through trial and error against one model has been
  implicitly overfitted to it — the phrasing that finally worked is the phrasing
  that worked *for that model*
- position matters differently across models; the same rule at the end of a long
  document may be attended to differently

**If the same text produces materially different behaviour across models, then
"one source of truth" is a weaker promise than it sounds, and some content may
genuinely need per-model variants.**

---

## Why this is uncomfortable

An honest negative result here partially undermines the tool's central claim. It
would mean the correct design is not one canonical file mirrored everywhere, but
one canonical file *plus* per-model overrides where behaviour diverges — closer
to internationalisation, where a shared source has locale-specific overrides.

That is a worse story for marketing and a better answer for users. Approach it
willing to find that out.

---

## What is unknown

1. **Does identical instruction text produce equivalent compliance across
   models?** Nobody has published a measurement.
2. **If not, which kinds of instruction transfer badly?** Plausible candidates,
   all untested:
   - prohibitions ("never use X") versus positive directions ("prefer Y")
   - instructions relying on implicit context versus fully explicit ones
   - long rules versus short ones
   - rules stated once versus repeated
3. **Does the mirroring itself change behaviour?** agentmeld drops frontmatter
   keys a vendor cannot express — Copilot's rule files have no field for a
   description; Claude has nowhere to put a glob. Those are lossy conversions.
   Does the loss matter behaviourally, or only cosmetically?
4. **Is there a phrasing style that transfers better across models?** If so, that
   is directly actionable guidance for anyone writing these files, and useful
   independently of any tool.

---

## How to approach measuring it

The core difficulty is that "did the model follow the instruction?" is usually a
judgement call. Make it mechanical instead.

**Use programmatically checkable rules.** Construct instructions whose compliance
can be verified by inspecting the output, not by opinion:

- "use pytest fixtures, never `setUp`" → scan generated code for `setUp`
- "every public function needs a docstring" → parse the AST and check
- "use `pathlib`, not `os.path`" → scan imports
- "British spelling in comments" → dictionary check

**Then:** hold the task, the repository, and the instruction text fixed. Vary
only the model. Measure compliance rate.

**Materially different compliance rates across models on identical text is the
finding.** Either direction is publishable — equivalence would be a reassuring
and useful negative result.

**Second experiment, if divergence appears:** take an instruction that transfers
badly, rewrite it in several styles (imperative vs. explanatory, short vs. long,
positive vs. prohibition), and see whether any style transfers better. That
produces actionable writing guidance.

---

## Pitfalls

- **Confounds are everywhere.** Model, effort/reasoning settings, temperature,
  context length, task difficulty, and file format all move compliance. Vary one
  thing at a time.
- **Rule ordering and position** within the document affect attention. Randomise
  or control it.
- **Do not test only the rules that are easy to check** — that biases toward
  short, mechanical instructions, which are exactly the ones most likely to
  transfer well. The interesting failures are probably in nuanced instructions,
  which are also the hardest to score. Acknowledge this limitation explicitly
  rather than hiding it.
- **Sample size.** Model outputs vary run to run. A single generation per
  condition tells you nothing; repeat and report variance.
- **Every run costs real money.** Budget it and get approval before running at
  scale.
- **This overlaps with Problem 3** (context economics). Do that one first if
  possible — it establishes the measurement harness, and its quality-measurement
  approach is the same technique.

---

## Why it matters beyond agentmeld

Every tool in this category — rulesync, ruler, agentmeld — assumes semantic
portability implicitly, and none has demonstrated it. Whether shared AI
configuration behaves consistently across vendors is a foundational question for
the whole category, and it is currently unanswered.
