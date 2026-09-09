#!/usr/bin/env python3
"""Weighted prevalence estimates from the frozen-frame probe (finding 07).

Reads data/probe-slice-{a,b}.json and sampling/frozen-meta.json, prints every
number quoted in findings/07-prevalence-stratified.md.

    python3 docs/research/scripts/analyze-prevalence.py
"""
import collections
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAMILY = {
    "CLAUDE.md": "claude",
    "AGENTS.md": "agents-std",
    "GEMINI.md": "gemini",
    "copilot_root": "copilot",
    "copilot_rules": "copilot",
    "cursor_rules": "cursor",
}
BANDS = ["10-25", "25-60", "60-150", "150-500", "500-2000", "2000-1000000"]

# Two defensible population sizes per band, reported side by side because they
# disagree only in the 10-25 band and only by ~0.4pp in the estimate:
#   REPORTED  -- GitHub's own total_count per band (sampling/frozen-meta.json)
#   ENUMERATED -- repos we actually enumerated into the frozen frame; the 10-25
#                 band hit the 1000-results cap in 2 cells, so it under-covers.
# frozen-repo-list.json stores names only, so the enumerated counts are recorded
# here rather than recomputed.
ENUMERATED = {
    "10-25": 7463, "25-60": 4500, "60-150": 3458,
    "150-500": 2378, "500-2000": 788, "2000-1000000": 326,
}


def load():
    records = []
    for slice_ in ("a", "b"):
        records += json.loads((ROOT / f"data/probe-slice-{slice_}.json").read_text())
    names = [r["repo"] for r in records]
    assert len(names) == len(set(names)), "slices overlap -- estimates would double-count"
    meta = json.loads((ROOT / "sampling/frozen-meta.json").read_text())
    return records, meta["weights"]


def tabulate(records):
    """band -> {n, any, multi, <file>: count}"""
    out = collections.defaultdict(collections.Counter)
    for r in records:
        cell = out[r["band"]]
        cell["n"] += 1
        families = {FAMILY[k] for k, present in r["has"].items() if present}
        if families:
            cell["any"] += 1
            if len(families) >= 2:
                cell["multi"] += 1
        for k, present in r["has"].items():
            if present:
                cell[k] += 1
    return out


def weighted(cells, pop, key):
    """Stratified estimate of P(key) with finite-population correction.

    Variance vanishes in a censused stratum (n == N), which is why the two
    smallest bands contribute point values rather than intervals.
    """
    total = sum(pop.values())
    est = var = 0.0
    for band, size in pop.items():
        n = cells[band]["n"]
        p = cells[band][key] / n
        w = size / total
        fpc = max(0.0, (size - n) / (size - 1)) if size > 1 else 0.0
        est += w * p
        var += w * w * fpc * p * (1 - p) / n
    return est, math.sqrt(var)


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def main():
    records, reported = load()
    cells = tabulate(records)

    print(f"n probed = {len(records)}\n")
    for label, pop in (("GitHub-reported band totals", reported),
                       ("enumerated frame counts   ", ENUMERATED)):
        est, se = weighted(cells, pop, "any")
        print(
            f"P(any config), {label}: {est * 100:.2f}%  "
            f"95% CI {100 * (est - 1.96 * se):.2f}-{100 * (est + 1.96 * se):.2f}"
        )
    multi, se_m = weighted(cells, reported, "multi")
    any_, _ = weighted(cells, reported, "any")
    print(f"P(>=2 tool families): {multi * 100:.2f}%")
    print(f"P(>=2 | adopter):     {multi / any_ * 100:.1f}%\n")

    sample_n = sum(cells[b]["n"] for b in BANDS)
    sample_k = sum(cells[b]["any"] for b in BANDS)
    print(f"unweighted sample rate: {sample_k / sample_n * 100:.2f}%  "
          "(over-states prevalence -- the design over-samples popular repos)\n")

    print(f"{'band':<14}{'n':>5}{'k':>5}{'rate':>8}  95% CI (Wilson)   multi")
    for band in BANDS:
        c = cells[band]
        lo, hi = wilson(c["any"], c["n"])
        print(
            f"{band:<14}{c['n']:>5}{c['any']:>5}{c['any'] / c['n'] * 100:>7.1f}%"
            f"  [{lo * 100:.1f}-{hi * 100:.1f}]"
            f"{'':<6}{c['multi'] / c['any'] * 100:.0f}% of adopters"
        )

    print("\nfiles (repo counts across the whole sample):")
    files = collections.Counter()
    for band in BANDS:
        for k in FAMILY:
            files[k] += cells[band][k]
    for k, v in files.most_common():
        print(f"  {k:<34}{v:>5}")

    print("\ncombinations of tool families among adopters:")
    combos = collections.Counter()
    for r in records:
        fams = tuple(sorted({FAMILY[k] for k, v in r["has"].items() if v}))
        if fams:
            combos[fams] += 1
    for combo, count in combos.most_common(8):
        print(f"  {count:>4}  {' + '.join(combo)}")


if __name__ == "__main__":
    main()
