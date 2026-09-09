#!/usr/bin/env python3
"""Classify repos carrying both AGENTS.md and CLAUDE.md.

Is CLAUDE.md a thin pointer at AGENTS.md, or a second copy of the same
knowledge that has to be maintained twice?

Symlink detection uses the git tree's file mode (120000). This matters: the raw
content endpoint serves a symlink's *target path text*, which once made a 9-byte
pointer look like total divergence from a 5KB file.
"""
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
API = "https://api.github.com"
LOCK = threading.Lock()
DONE = [0]


def api(path, tries=4):
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "agentmeld-research"},
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read()), None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "404"
            if e.code in (403, 429):                     # rate limit / abuse
                reset = e.headers.get("x-ratelimit-reset")
                remaining = e.headers.get("x-ratelimit-remaining")
                if remaining == "0" and reset:
                    wait = max(0, int(reset) - int(time.time())) + 2
                    sys.stderr.write(f"rate limited, sleeping {wait}s\n")
                    time.sleep(min(wait, 900))
                    continue
                time.sleep(2 ** attempt)
                continue
            if 500 <= e.code < 600:
                time.sleep(2 ** attempt)
                continue
            return None, f"http {e.code}"
        except Exception as e:                            # noqa: BLE001 - network
            if attempt == tries - 1:
                return None, f"{type(e).__name__}"
            time.sleep(2 ** attempt)
    return None, "exhausted"


WORDS = re.compile(r"[A-Za-z0-9_./-]+")


def tokens(text):
    return set(w.lower() for w in WORDS.findall(text) if len(w) > 1)


def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# a line that does nothing but point at the other file
POINTER = re.compile(
    r"""^\s*(?:
          [-*>]\s*                      # list item / quote
        | \#{1,6}\s*                    # heading
        )?
        (?:see\s+|read\s+|refer\s+to\s+|follow\s+|use\s+|all\s+|the\s+)*
        (?:
          @\.?/?AGENTS\.md              # Claude Code import syntax
        | \[[^\]]*\]\(\.?/?AGENTS\.md\) # markdown link
        | `?\.?/?AGENTS\.md`?           # bare mention
        )
        [\s.,;:!)]*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
NOISE = re.compile(r"^\s*(?:<!--.*?-->|#{1,6}\s*\S[^\n]*|[-=]{3,}|)\s*$")


def residual(text):
    """Content left once pointer lines and trivial noise are removed."""
    out = []
    for line in text.splitlines():
        if POINTER.match(line):
            continue
        if not line.strip():
            continue
        out.append(line.strip())
    return "\n".join(out)


def classify(repo):
    tree, err = api(f"/repos/{repo}/git/trees/HEAD")
    if err:
        return {"repo": repo, "class": "error", "error": f"tree: {err}"}
    entries = {e["path"]: e for e in tree.get("tree", []) if e["path"] in ("AGENTS.md", "CLAUDE.md")}
    if len(entries) < 2:
        # probe saw both at some point; HEAD may have moved, or one is not at root
        return {"repo": repo, "class": "error",
                "error": f"only {sorted(entries)} at HEAD root"}

    rec = {"repo": repo}
    blobs = {}
    for name, e in entries.items():
        rec[f"{name}_mode"] = e["mode"]
        rec[f"{name}_size"] = e.get("size")
        if e["mode"] == "120000":
            continue
        blob, berr = api(f"/repos/{repo}/git/blobs/{e['sha']}")
        if berr:
            return {"repo": repo, "class": "error", "error": f"blob {name}: {berr}"}
        try:
            blobs[name] = base64.b64decode(blob["content"]).decode("utf-8", "replace")
        except Exception:
            return {"repo": repo, "class": "error", "error": f"decode {name}"}

    a_link = entries["AGENTS.md"]["mode"] == "120000"
    c_link = entries["CLAUDE.md"]["mode"] == "120000"

    if c_link or a_link:
        rec["class"] = "symlink"
        rec["direction"] = "CLAUDE->AGENTS" if c_link else "AGENTS->CLAUDE"
        return rec

    agents, claude = blobs["AGENTS.md"], blobs["CLAUDE.md"]
    rec["claude_bytes"] = len(claude.encode())
    rec["agents_bytes"] = len(agents.encode())
    rec["jaccard"] = round(jaccard(agents, claude), 4)

    res = residual(claude)
    rec["claude_residual_bytes"] = len(res.encode())
    rec["points_at_agents"] = bool(re.search(r"AGENTS\.md", claude, re.IGNORECASE))

    if claude == agents:
        rec["class"] = "duplicate_exact"
    elif rec["points_at_agents"] and len(res.encode()) <= 200:
        rec["class"] = "thin_import"
    elif rec["points_at_agents"] and len(res.encode()) <= 1000:
        rec["class"] = "import_plus_overlay"
    elif rec["jaccard"] >= 0.90:
        rec["class"] = "duplicate_near"
    else:
        rec["class"] = "divergent"
    return rec


def main():
    repos = [r["repo"] for r in json.load(open("/tmp/frame3/pair_repos.json"))]
    out_path = "/tmp/frame3/pair_classified.json"
    done = {}
    if os.path.exists(out_path):
        done = {r["repo"]: r for r in json.load(open(out_path))}
    todo = [r for r in repos if r not in done or done[r].get("class") == "error"]
    sys.stderr.write(f"{len(repos)} repos, {len(todo)} to do\n")

    results = list(done.values())
    results = [r for r in results if r["repo"] not in set(todo)]

    def work(repo):
        rec = classify(repo)
        with LOCK:
            results.append(rec)
            DONE[0] += 1
            if DONE[0] % 25 == 0:
                sys.stderr.write(f"  {DONE[0]}/{len(todo)}\n")
                json.dump(results, open(out_path, "w"), indent=1)
        return rec

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(work, todo))

    json.dump(results, open(out_path, "w"), indent=1)
    sys.stderr.write(f"wrote {out_path}: {len(results)} records\n")


if __name__ == "__main__":
    main()
