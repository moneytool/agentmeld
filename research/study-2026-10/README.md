# Study, September–October 2026: how public repositories configure several AI coding agents

Dataset and scripts behind the numbers in `paper.md` (Statement of need). No file bodies are
included: each record holds repository metadata, which instruction files exist, their modes and
sizes, how the `AGENTS.md`/`CLAUDE.md` pair relates, and the result of resolving `@import` lines.

| File | What it is |
|---|---|
| `miner_v3.py` | Samples repositories by size bucket from the GitHub search API, fetches the five instruction files' metadata, classifies pairs. |
| `v3.jsonl` | 2,421 repositories (one JSON object per line); 2,255 active and non-fork. |
| `summarize_v3.py`, `v3_summary.md` | The tables: tools per repository, pair mechanism, breakage, canonicality. |
| `verify_imports.py`, `v3_imports.jsonl` | Every `@import` target resolved against the repository; 36 repositories with 107 missing targets. |
| `drift_v3.py`, `v3_drift.jsonl`, `v3_drift_summary.json` | Commit-history pass over 330 pairs with at least two commits per file; classification per sampled commit. |

Mechanism classes for a pair: identical, near (difflib ratio ≥ 0.9), symlink, import, prose
pointer, overlapping, distinct, corrupted (a symlink committed as a plain-text file). Sampling
seed and thresholds are in the scripts. The pilot that preceded this study is in `../pilot/`.
A full write-up is in preparation.
