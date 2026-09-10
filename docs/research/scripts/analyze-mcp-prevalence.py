#!/usr/bin/env python3
"""Weighted MCP-config prevalence, comparable to finding 07.

    python3 docs/research/scripts/analyze-mcp-prevalence.py

Reads the same frozen frame as finding 07, so the two are directly comparable.
"""
import collections
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

recs = json.loads((ROOT / 'data/probe-mcp.json').read_text())
base = {r['repo']: r for r in
        json.loads((ROOT / 'data/probe-slice-a.json').read_text())
        + json.loads((ROOT / 'data/probe-slice-b.json').read_text())}
POP = json.loads((ROOT / 'sampling/frozen-meta.json').read_text())['weights']
BANDS = ['10-25', '25-60', '60-150', '150-500', '500-2000', '2000-1000000']

cells = collections.defaultdict(collections.Counter)
types = collections.Counter()
indet = collections.Counter()
for r in recs:
    c = cells[r['band']]
    c['n'] += 1
    if r['any']:
        c['any'] += 1
    for k, v in r['has'].items():
        if v is True:
            types[k] += 1
        elif v is None:
            indet[k] += 1

def weighted(key):
    total = sum(POP.values()); est = var = 0.0
    for band, size in POP.items():
        n = cells[band]['n']
        if not n: continue
        p = cells[band][key] / n
        w = size / total
        fpc = max(0.0, (size - n) / (size - 1)) if size > 1 else 0.0
        est += w * p; var += w * w * fpc * p * (1 - p) / n
    return est, math.sqrt(var)

def wilson(k, n, z=1.96):
    if not n: return (0, 0)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return c - h, c + h

n = sum(cells[b]['n'] for b in BANDS)
k = sum(cells[b]['any'] for b in BANDS)
est, se = weighted('any')
print(f"probed {n} repos on the frozen frame (fingerprint 8fd846e908911bf9)\n")
print(f"WEIGHTED prevalence of any MCP config: {est*100:.2f}%"
      f"  95% CI {100*(est-1.96*se):.2f}-{100*(est+1.96*se):.2f}")
print(f"unweighted sample rate:                {k/n*100:.2f}%  ({k}/{n})\n")

print(f"{'band':<14}{'n':>5}{'k':>5}{'rate':>8}   95% CI")
for b in BANDS:
    c = cells[b]
    lo, hi = wilson(c['any'], c['n'])
    print(f"{b:<14}{c['n']:>5}{c['any']:>5}{(c['any']/c['n']*100 if c['n'] else 0):>7.1f}%"
          f"   [{lo*100:.1f}-{hi*100:.1f}]")

print("\nby file (repo counts):")
for key, label in (('mcp_claude', '.mcp.json (Claude)'),
                   ('mcp_vscode', '.vscode/mcp.json (VS Code)'),
                   ('mcp_cursor', '.cursor/mcp.json (Cursor)')):
    print(f"  {label:<30}{types[key]:>5}")

if sum(indet.values()):
    print("\nindeterminate probes (network, not absence):")
    for key, v in indet.most_common():
        print(f"  {key:<20}{v:>5}")
else:
    print("\nindeterminate probes: 0 -- every result is an authoritative 200 or 404")

# ---------------------------------------------------------------------------
# overlap with instruction config -- the decision-relevant part
# ---------------------------------------------------------------------------
both = mcp_only = inst_only = neither = 0
for repo, m in ((r['repo'], r) for r in recs):
    b = base[repo]
    if m['any'] and b['any']:
        both += 1
    elif m['any']:
        mcp_only += 1
    elif b['any']:
        inst_only += 1
    else:
        neither += 1

print("\noverlap with AI instruction config:")
print(f"  MCP config and instruction config  {both:>5}")
print(f"  MCP config only                    {mcp_only:>5}")
print(f"  instruction config only            {inst_only:>5}")
print(f"  neither                            {neither:>5}")
print(f"\n  P(instruction config | MCP config) = {both / (both + mcp_only) * 100:.0f}%")
print(f"  P(MCP config | instruction config) = {both / (both + inst_only) * 100:.1f}%")
print(f"  reachable ONLY via MCP: {mcp_only} of {len(recs)} "
      f"({mcp_only / len(recs) * 100:.1f}%)")
