# Pilot: AGENTS.md / CLAUDE.md co-occurrence in public GitHub repositories

Script and dataset behind the numbers in README.md and paper.md.

- `miner.py` — stdlib-only; uses `gh auth token`. GitHub code search for
  root `AGENTS.md`, stratified into five file-size buckets (~300 repos
  each) to avoid the 1,000-result cap biasing toward small files. For each
  repo with a root `CLAUDE.md`, both files are fetched; symlinks are
  detected from git tree mode `120000` (the contents API silently follows
  in-repo symlinks). Pairs are classified: symlink / `@AGENTS.md` import /
  prose pointer / identical / near-identical (≥0.9 similarity) /
  overlapping (≥0.5) / distinct / corrupted.
- `pilot_v2.jsonl` — one row per scanned repo: name, bucket, class, sizes.
  File bodies are not redistributed.
- `summary.json` — counts and percentages. Run: 2026-09-18, n=1,905
  scanned, 649 pairs.

Rerun: `python3 miner.py --max-repos 1500 --out pilot_v2.jsonl`.
Full archive with file bodies: Zenodo PILOT_DOI (added on release).
