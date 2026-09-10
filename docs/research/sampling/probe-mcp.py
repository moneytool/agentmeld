#!/usr/bin/env python3
"""Probe the frozen frame for MCP server *configuration*.

Same 4,314 repos, same frozen frame (fingerprint 8fd846e908911bf9), so this is
directly comparable to finding 07 rather than a new sample.

Absence and failure are kept apart: has_file returns None when the result is
indeterminate, so a timeout is never silently recorded as "no file". The earlier
version of this probe conflated the two and could only ever undercount.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()

# Only unambiguous, MCP-dedicated paths. .gemini/settings.json and
# .zed/settings.json are general settings files that *may* contain servers, so
# their presence would not prove MCP use -- counting them would inflate the rate.
FILES = {
    "mcp_claude": ".mcp.json",
    "mcp_vscode": ".vscode/mcp.json",
    "mcp_cursor": ".cursor/mcp.json",
}
LOCK = threading.Lock()
DONE = [0]


def has_file(repo, path, tries=3):
    url = "https://raw.githubusercontent.com/{}/HEAD/{}".format(repo, path)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url, method="HEAD", headers={"User-Agent": "agentmeld-research"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False                       # authoritative absence
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(1 + attempt)
                continue
            return None
        except Exception:
            time.sleep(1 + attempt)
    return None                                    # indeterminate


def main():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    base = json.loads((root / "data/probe-slice-a.json").read_text()) + json.loads(
        (root / "data/probe-slice-b.json").read_text()
    )
    out_path = str(root / "data/probe-mcp.json")
    done = {}
    if os.path.exists(out_path):
        done = {r["repo"]: r for r in json.load(open(out_path))}
    todo = [r for r in base if r["repo"] not in done]
    sys.stderr.write("{} repos, {} to do\n".format(len(base), len(todo)))
    results = list(done.values())

    def work(r):
        rec = {"repo": r["repo"], "stars": r["stars"], "band": r["band"], "has": {}}
        for key, path in FILES.items():
            rec["has"][key] = has_file(r["repo"], path)
        rec["indeterminate"] = [k for k, v in rec["has"].items() if v is None]
        rec["any"] = any(v is True for v in rec["has"].values())
        with LOCK:
            results.append(rec)
            DONE[0] += 1
            if DONE[0] % 250 == 0:
                sys.stderr.write("  {}/{}\n".format(DONE[0], len(todo)))
                json.dump(results, open(out_path, "w"))
        return rec

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, todo))
    json.dump(results, open(out_path, "w"))
    sys.stderr.write("wrote {}: {} records\n".format(out_path, len(results)))


if __name__ == "__main__":
    main()
