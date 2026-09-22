#!/usr/bin/env python3
"""Pilot miner: repos carrying both AGENTS.md and CLAUDE.md at the root.

Reproduces the agentmeld README study. Uses the GitHub REST API with the
token from `gh auth token`. Output: JSONL, one record per repo, plus a
summary. Stdlib only.

Usage: miner.py [--max-repos N] [--out data/pilot.jsonl]
"""
import argparse, base64, difflib, json, os, subprocess, sys, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path

API = "https://api.github.com"
TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
       "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "agentmeld-pilot-miner"}

def get(url, params=None, raw=False):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for attempt in range(6):
        req = urllib.request.Request(url, headers=HDR)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429):
                reset = e.headers.get("X-RateLimit-Reset")
                retry = e.headers.get("Retry-After")
                wait = int(retry) if retry else (max(int(reset) - int(time.time()), 5) if reset else 60)
                print(f"  rate-limited ({e.code}); sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 900) + 1)
                continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1)); continue
            raise
    raise RuntimeError(f"gave up on {url}")

def search_repos_with_file(filename, max_repos):
    """Code search: files named `filename` at repo root. Cap: 1000 results/query.
    Stratified: an equal quota per size bucket so small files don't dominate."""
    repos = {}
    buckets = ["size:<500", "size:500..1500", "size:1500..3000", "size:3000..6000", "size:>6000"]
    quota = max_repos // len(buckets)
    for b in buckets:
        q = f"filename:{filename} path:/ {b}"
        start = len(repos)
        for page in range(1, 11):
            data = get(f"{API}/search/code", {"q": q, "per_page": 100, "page": page})
            items = (data or {}).get("items", [])
            for it in items:
                if it.get("path") == filename:
                    r = it["repository"]
                    repos.setdefault(r["full_name"], {"full_name": r["full_name"], "fork": r.get("fork", False), "bucket": b})
            print(f"  [{q}] page {page}: {len(items)} items, {len(repos)} repos so far", file=sys.stderr)
            if len(items) < 100 or len(repos) - start >= quota:
                break
            time.sleep(6.5)  # code search: 10 req/min
        time.sleep(6.5)
    return list(repos.values())

def root_modes(full_name):
    """{name: mode} for root entries; mode '120000' = symlink."""
    d = get(f"{API}/repos/{full_name}/git/trees/HEAD")
    if not d or "tree" not in d:
        return {}
    return {e["path"]: e["mode"] for e in d["tree"]}

def fetch_root_file(full_name, name):
    d = get(f"{API}/repos/{full_name}/contents/{urllib.parse.quote(name)}")
    if not d or isinstance(d, list):
        return None
    rec = {"type": d.get("type"), "size": d.get("size"), "sha": d.get("sha"),
           "target": d.get("target")}  # target set for symlinks
    if d.get("type") == "file" and d.get("encoding") == "base64":
        rec["text"] = base64.b64decode(d["content"]).decode("utf-8", "replace")
    elif d.get("type") == "symlink":
        rec["text"] = None
    return rec

def classify(a, c):
    """a = AGENTS.md record, c = CLAUDE.md record."""
    if c["type"] == "symlink":
        return "symlink_claude_to_agents" if (c.get("target") or "").endswith("AGENTS.md") else "symlink_claude_other"
    if a["type"] == "symlink":
        return "symlink_agents_to_claude" if (a.get("target") or "").endswith("CLAUDE.md") else "symlink_agents_other"
    ct, at = (c.get("text") or ""), (a.get("text") or "")
    cs, as_ = ct.strip(), at.strip()
    if cs.startswith("XSym") or as_.startswith("XSym"):
        return "corrupted_xsym"
    if cs in ("AGENTS.md", "./AGENTS.md") or as_ in ("CLAUDE.md", "./CLAUDE.md"):
        return "corrupted_plain_pointer"
    if cs == "@AGENTS.md" or (len(cs) < 200 and "@AGENTS.md" in cs):
        return "import_pointer"
    if len(cs) < 400 and ("AGENTS.md" in cs) and ("see" in cs.lower() or "read" in cs.lower() or "follow" in cs.lower()):
        return "prose_pointer"
    if cs == as_:
        return "identical"
    ratio = difflib.SequenceMatcher(None, at, ct, autojunk=False).ratio() if (len(at) + len(ct)) < 60000 else difflib.SequenceMatcher(None, at, ct).ratio()
    if ratio >= 0.9:
        return "near_identical"
    if ratio >= 0.5:
        return "overlapping"
    return "distinct"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-repos", type=int, default=1500)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "pilot_v2.jsonl"))
    args = ap.parse_args()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try: done.add(json.loads(line)["repo"])
            except Exception: pass
    print(f"searching repos with AGENTS.md at root (max {args.max_repos})…", file=sys.stderr)
    candidates = search_repos_with_file("AGENTS.md", args.max_repos)
    print(f"{len(candidates)} candidates; {len(done)} already done", file=sys.stderr)
    with out.open("a") as f:
        for i, r in enumerate(candidates, 1):
            fn = r["full_name"]
            if fn in done: continue
            c = fetch_root_file(fn, "CLAUDE.md")
            rec = {"repo": fn, "fork": r["fork"], "has_claude": c is not None}
            if c is not None:
                a = fetch_root_file(fn, "AGENTS.md")
                if a is None:
                    rec["has_claude"] = False  # AGENTS.md vanished; skip
                else:
                    modes = root_modes(fn)
                    for name, obj in (("CLAUDE.md", c), ("AGENTS.md", a)):
                        if modes.get(name) == "120000":
                            obj["type"] = "symlink"
                            # contents API already resolved it; the resolved text tells us the target
                            other = "AGENTS.md" if name == "CLAUDE.md" else "CLAUDE.md"
                            obj["target"] = other if (c.get("text") == a.get("text")) else (obj.get("target") or "?")
                    rec["bucket"] = r.get("bucket")
                    rec["class"] = classify(a, c)
                    rec["agents"] = {k: a.get(k) for k in ("type", "size", "target")}
                    rec["claude"] = {k: c.get(k) for k in ("type", "size", "target")}
                    rec["agents_text"] = a.get("text"); rec["claude_text"] = c.get("text")
            f.write(json.dumps(rec) + "\n"); f.flush()
            if i % 25 == 0:
                both = sum(1 for _ in open(out) if '"class"' in _)
                print(f"  {i}/{len(candidates)} checked; {both} with both files", file=sys.stderr)
    # summary
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    both = [r for r in recs if r.get("class")]
    from collections import Counter
    cnt = Counter(r["class"] for r in both)
    summ = {"scanned_with_agents_md": len(recs), "with_both": len(both),
            "classes": dict(cnt), "pct": {k: round(100 * v / len(both), 1) for k, v in cnt.items()} if both else {}}
    Path(out.parent / (out.stem + "_summary.json")).write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))

if __name__ == "__main__":
    main()
