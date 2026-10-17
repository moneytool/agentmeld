#!/usr/bin/env python3
"""Summaries for miner v3 output: RQ1 multiplicity, RQ2 mechanism, RQ5 breakage,
RQ6 AGENTS.md canonicality, RQ4 first/last-commit spans. Prints Markdown."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def load(path: Path) -> list[dict]:
    recs = []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("status") == "ok":
            recs.append(r)
    return recs


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


# Collapse per-tool markers so a tool with both a root file and a directory
# (e.g. CLAUDE.md + .claude/) counts once. Generic dirs are not a tool.
CANON = {
    "agents-md": "agents-md", "claude-code": "claude-code", "claude-code-dir": "claude-code",
    "gemini-cli": "gemini-cli", "copilot": "copilot", "cursor-legacy": "cursor", "cursor-rules": "cursor",
    "windsurf": "windsurf", "windsurf-dir": "windsurf", "cline": "cline", "cline-dir": "cline",
    "codex": "codex", "amp": "amp", "agentmeld-or-generic": None,
}


def canon_tools(r: dict) -> list[str]:
    out = {CANON.get(t, t) for t in r.get("tools", [])}
    out.discard(None)
    # a bare .github/ dir is only "copilot" if copilot-instructions.md exists
    if "copilot" in out and not r.get("copilot_instructions") and not r.get("copilot_instruction_files"):
        out.discard("copilot")
    return sorted(out)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "v3.jsonl"
    recs = load(path)
    active = [r for r in recs if r.get("active_12mo") and not r.get("fork") and not r.get("archived")]
    print(f"# miner v3 summary — {path.name}\n\nmined ok: {len(recs)}; active non-fork non-archived: {len(active)}\n")

    print("## RQ1 — how many tools per repo (active set)\n")
    for r in active:
        r["ctools"] = canon_tools(r)
    c = Counter(len(r["ctools"]) for r in active)
    for k in sorted(c):
        print(f"- {k} tool(s): {c[k]} ({pct(c[k], len(active))})")
    multi = [r for r in active if len(r["ctools"]) >= 2]
    print(f"\n≥2 tools: {len(multi)} ({pct(len(multi), len(active))})")
    print("(Sampling frame: repos found by searching for one of five instruction files, so every repo has ≥1 tool; "
          "multiplicity is conditional on that. Size-stratified search; not population-weighted.)\n")
    by_seed = {}
    for r in active:
        by_seed.setdefault(r.get("seed_file"), []).append(len(r["ctools"]) >= 2)
    print("≥2 tools by seed file: " + ", ".join(f"{k}: {pct(sum(v), len(v))}" for k, v in sorted(by_seed.items(), key=lambda kv: str(kv[0]))) + "\n")
    combos = Counter(" + ".join(r["ctools"]) for r in multi)
    print("Top combinations:\n")
    for combo, n in combos.most_common(12):
        print(f"- {combo}: {n}")

    print("\n## RQ2 — mechanism for each co-existing pair (active set)\n")
    by_pair: dict[str, Counter] = {}
    for r in active:
        for pair, cls in r.get("pairs", {}).items():
            by_pair.setdefault(pair, Counter())[cls] += 1
    for pair, cnt in sorted(by_pair.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(cnt.values())
        print(f"\n### {pair} (n={total})\n")
        for cls, n in cnt.most_common():
            print(f"- {cls}: {n} ({pct(n, total)})")

    print("\n## RQ5 — breakage\n")
    corrupted = [r for r in active if any(v.startswith("corrupted") for v in r.get("pairs", {}).values())]
    # The miner only checked root-level existence; nested targets need a follow-up fetch.
    root_broken = [r for r in active if any("/" not in b["import"].lstrip("@./") for b in r.get("broken_imports", []))]
    nested = [r for r in active if r.get("broken_imports") and all("/" in b["import"].lstrip("@./") for b in r["broken_imports"])]
    print(f"- corrupted symlinks (XSym / plain pointer): {len(corrupted)}")
    for r in corrupted:
        print(f"  - {r['repo']}: {[k for k, v in r['pairs'].items() if v.startswith('corrupted')]}")
    print(f"- imports pointing at a missing ROOT file (verified against the root tree): {len(root_broken)}")
    for r in root_broken[:10]:
        print(f"  - {r['repo']}: {[b['import'] for b in r['broken_imports'] if '/' not in b['import'].lstrip('@./')][:3]}")
    print(f"- imports to nested paths, existence NOT yet verified (needs follow-up fetch): {len(nested)}")

    print("\n## RQ6 — is AGENTS.md canonical?\n")
    with_agents = [r for r in active if "AGENTS.md" in r.get("files", {})]
    pointing = [r for r in with_agents if any(v in ("symlink_to_primary", "import_pointer", "prose_pointer") for k, v in r.get("pairs", {}).items() if k.startswith("AGENTS.md~"))]
    print(f"- repos with AGENTS.md: {len(with_agents)} ({pct(len(with_agents), len(active))} of active)")
    print(f"- of those, at least one other tool file points at it: {len(pointing)} ({pct(len(pointing), len(with_agents))})")

    print("\n## RQ4 (prep) — file age and edit counts\n")
    spans = []
    for r in active:
        for name, f in r.get("files", {}).items():
            h = f.get("history")
            if h and h.get("first") and h.get("last"):
                a = datetime.fromisoformat(h["first"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(h["last"].replace("Z", "+00:00"))
                spans.append((name, (b - a).days, h["n_commits"]))
    by_name: dict[str, list] = {}
    for name, days, n in spans:
        by_name.setdefault(name, []).append((days, n))
    for name, lst in sorted(by_name.items(), key=lambda kv: -len(kv[1])):
        days = sorted(d for d, _ in lst); ns = sorted(n for _, n in lst)
        med_d = days[len(days) // 2]; med_n = ns[len(ns) // 2]
        print(f"- {name}: n={len(lst)}, median lifetime {med_d} days, median commits {med_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
