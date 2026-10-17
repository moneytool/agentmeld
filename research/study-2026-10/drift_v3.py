#!/usr/bin/env python3
"""RQ4 drift pass: for co-existing instruction-file pairs, reconstruct the
relationship over time from each file's commit history.

For each selected pair (default AGENTS.md~CLAUDE.md in active repos where
both files have ≥2 commits), take the union of both files' commit shas
(≤ --max-commits per file, evenly spaced, always including first and last),
fetch both files at each sha, classify the pair state at that commit
(missing / symlink / import / identical / near / overlapping / distinct),
and derive: first date both existed, first date they were identical or
near-identical (if ever), first divergence after that, days between,
which file changed at the divergence commit, and whether they re-converged.

Output: data/v3_drift.jsonl, one record per pair. Resumable. Stdlib only.
Budget: ≤ 2 × max_commits calls per pair.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://api.github.com"
TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
       "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "agent-config-miner-v3-drift"}


def get(url, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429):
                reset = e.headers.get("X-RateLimit-Reset")
                retry = e.headers.get("Retry-After")
                wait = int(retry) if retry else (max(int(reset) - int(time.time()), 5) if reset else 60)
                print(f"  rate-limited; sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 900) + 1)
                continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}")


def content_at(repo: str, path: str, sha: str) -> dict:
    d = get(f"{API}/repos/{repo}/contents/{urllib.parse.quote(path)}", {"ref": sha})
    if not d or isinstance(d, list):
        return {"state": "missing"}
    if d.get("type") == "symlink":
        return {"state": "symlink", "target": d.get("target")}
    if d.get("encoding") == "base64":
        return {"state": "file", "text": base64.b64decode(d["content"]).decode("utf-8", "replace")}
    return {"state": "file", "text": None}


def relate(p: dict, s: dict, pname: str, sname: str) -> tuple[str, float | None]:
    if p["state"] == "missing" or s["state"] == "missing":
        return ("missing", None)
    if s["state"] == "symlink":
        return ("symlink", None)
    if p["state"] == "symlink":
        return ("primary_symlink", None)
    pt, st = p.get("text") or "", s.get("text") or ""
    ss = st.strip()
    if ss.startswith("XSym") or ss in (pname, f"./{pname}"):
        return ("corrupted", None)
    if ss == f"@{pname}" or (len(ss) < 200 and f"@{pname}" in ss):
        return ("import", None)
    if len(ss) < 400 and pname in ss and any(w in ss.lower() for w in ("see", "read", "follow", "refer")):
        return ("prose_pointer", None)
    if not pt or not st:
        return ("unavailable", None)
    if pt.strip() == ss:
        return ("identical", 1.0)
    ratio = difflib.SequenceMatcher(None, pt, st, autojunk=(len(pt) + len(st) >= 60000)).ratio()
    return (("near" if ratio >= 0.9 else "overlapping" if ratio >= 0.5 else "distinct"), round(ratio, 3))


def spaced(shas: list[str], k: int) -> list[str]:
    if len(shas) <= k:
        return shas
    idx = sorted({0, len(shas) - 1} | {round(i * (len(shas) - 1) / (k - 1)) for i in range(k)})
    return [shas[i] for i in idx]


def commit_dates(repo: str, path: str, per_page: int = 100) -> list[tuple[str, str]]:
    d = get(f"{API}/repos/{repo}/commits", {"path": path, "per_page": per_page})
    if not d or not isinstance(d, list):
        return []
    return [(c["sha"], c["commit"]["committer"]["date"]) for c in d if c.get("commit")][::-1]  # oldest first


def analyse(repo: str, pname: str, sname: str, max_commits: int) -> dict:
    hp = commit_dates(repo, pname)
    hs = commit_dates(repo, sname)
    dates = {sha: d for sha, d in hp + hs}
    shas = sorted(dates, key=lambda x: dates[x])
    sample = spaced(shas, max_commits)
    timeline = []
    for sha in sample:
        p = content_at(repo, pname, sha)
        s = content_at(repo, sname, sha)
        state, ratio = relate(p, s, pname, sname)
        touched = ("P" if sha in dict(hp) else "") + ("S" if sha in dict(hs) else "")
        timeline.append({"sha": sha[:10], "date": dates[sha], "state": state, "ratio": ratio, "touched": touched})
    rec = {"repo": repo, "pair": f"{pname}~{sname}", "n_commits_primary": len(hp), "n_commits_secondary": len(hs),
           "sampled": len(sample), "timeline": timeline}
    both = [t for t in timeline if t["state"] not in ("missing",)]
    rec["first_both"] = both[0]["date"] if both else None
    same = [t for t in timeline if t["state"] in ("identical", "near", "symlink", "import")]
    rec["ever_same"] = bool(same)
    rec["first_same"] = same[0]["date"] if same else None
    rec["final_state"] = timeline[-1]["state"] if timeline else None
    div = None
    if same:
        after = [t for t in timeline if t["date"] > same[0]["date"]]
        for t in after:
            if t["state"] in ("overlapping", "distinct"):
                div = t
                break
    rec["diverged"] = div is not None
    if div:
        d0 = datetime.fromisoformat(same[0]["date"].replace("Z", "+00:00"))
        d1 = datetime.fromisoformat(div["date"].replace("Z", "+00:00"))
        rec["days_to_divergence"] = (d1 - d0).days
        rec["divergence_touched"] = div["touched"]  # which file changed at the diverging commit
        later = [t for t in timeline if t["date"] > div["date"] and t["state"] in ("identical", "near", "symlink", "import")]
        rec["reconverged"] = bool(later)
    # mechanism migration: symlink -> import, etc.
    mechs = [t["state"] for t in timeline if t["state"] in ("symlink", "import", "prose_pointer")]
    rec["mechanism_sequence"] = [m for i, m in enumerate(mechs) if i == 0 or mechs[i - 1] != m]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path(__file__).resolve().parents[1] / "data" / "v3.jsonl"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "v3_drift.jsonl"))
    ap.add_argument("--pair", default="AGENTS.md~CLAUDE.md")
    ap.add_argument("--max-commits", type=int, default=12)
    ap.add_argument("--min-commits", type=int, default=2, help="both files need at least this many commits")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    pname, sname = a.pair.split("~")
    out = Path(a.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                done.add(json.loads(line)["repo"])
            except Exception:
                pass
    todo = []
    for line in Path(a.src).read_text().splitlines():
        r = json.loads(line)
        if r.get("status") != "ok" or not r.get("active_12mo") or r.get("fork") or r.get("archived"):
            continue
        if a.pair not in r.get("pairs", {}) or r["repo"] in done:
            continue
        fp, fs = r["files"].get(pname, {}), r["files"].get(sname, {})
        hp, hs = fp.get("history") or {}, fs.get("history") or {}
        if hp.get("n_commits", 0) >= a.min_commits and hs.get("n_commits", 0) >= a.min_commits:
            todo.append(r["repo"])
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} pairs to analyse ({len(done)} done)", file=sys.stderr)
    with out.open("a") as f:
        for i, repo in enumerate(todo, 1):
            try:
                rec = analyse(repo, pname, sname, a.max_commits)
            except Exception as exc:
                rec = {"repo": repo, "pair": a.pair, "error": str(exc)}
            f.write(json.dumps(rec) + "\n"); f.flush()
            if i % 10 == 0:
                print(f"  {i}/{len(todo)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
