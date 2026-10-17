#!/usr/bin/env python3
"""Follow-up for RQ5: check whether nested `@import` targets exist (contents API).
Writes data/v3_imports.jsonl: {repo, import, target, exists}."""
import json, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
API = "https://api.github.com"
TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "agent-config-miner-v3"}
def exists(repo, path):
    req = urllib.request.Request(f"{API}/repos/{repo}/contents/{urllib.parse.quote(path)}", headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404: return False
        if e.code in (403, 429): time.sleep(60); return exists(repo, path)
        return None
src = Path(__file__).resolve().parents[1] / "data" / "v3.jsonl"
out = src.with_name("v3_imports.jsonl")
seen = set()
with out.open("w") as f:
    for line in src.read_text().splitlines():
        r = json.loads(line)
        for b in r.get("broken_imports", []):
            target = b["import"][1:].lstrip("./")
            key = (r["repo"], target)
            if key in seen: continue
            seen.add(key)
            ok = exists(r["repo"], target)
            f.write(json.dumps({"repo": r["repo"], "in": b["in"], "import": b["import"], "target": target, "exists": ok}) + "\n")
recs = [json.loads(l) for l in out.read_text().splitlines()]
missing = [x for x in recs if x["exists"] is False]
repos_missing = sorted({x["repo"] for x in missing})
print(f"checked {len(recs)} import targets in {len({x['repo'] for x in recs})} repos; missing: {len(missing)} targets in {len(repos_missing)} repos")
for x in missing[:15]: print(" ", x["repo"], x["in"], x["import"])
