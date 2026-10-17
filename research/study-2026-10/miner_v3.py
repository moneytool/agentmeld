#!/usr/bin/env python3
"""Miner v3: one repository, many agents.

Extends miner v2 (AGENTS.md × CLAUDE.md pairs) to every agent instruction
file at the repository root plus per-file commit history, for RQ1 (multiplicity
and trend), RQ2 (co-existence mechanism), RQ4 (drift: first/last commit per
file, shas for a later content-at-sha pass), RQ5 (breakage), RQ6 (AGENTS.md as
canonical). Stdlib only; token from `gh auth token`; resumable; JSONL out.

Usage:
  miner_v3.py [--max-repos-per-file N] [--files AGENTS.md,CLAUDE.md,...]
              [--out data/v3.jsonl] [--no-history] [--max-file-bytes 200000]

Budget: code search is 10 req/min (shared across files); per repo ≈ 1 repo
+ 1 tree + k contents + k commits calls (k = number of instruction files
present), i.e. ~450 repos/hour under the 5000/h core limit.
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
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

API = "https://api.github.com"
TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
       "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "agent-config-miner-v3"}

# Root-level instruction files, keyed by the tool that reads them. Directory-based
# rule systems are detected from the tree, not searched.
ROOT_FILES = {
    "AGENTS.md": "agents-md",
    "CLAUDE.md": "claude-code",
    "GEMINI.md": "gemini-cli",
    ".cursorrules": "cursor-legacy",
    ".windsurfrules": "windsurf",
    ".clinerules": "cline",
    "codex.md": "codex",
    "AGENT.md": "amp",
}
DIR_MARKERS = {
    ".cursor": "cursor-rules",        # .cursor/rules/*.mdc
    ".github": "copilot",            # .github/copilot-instructions.md, .github/instructions/*
    ".claude": "claude-code-dir",     # .claude/agents, commands, settings
    ".windsurf": "windsurf-dir",
    ".clinerules": "cline-dir",       # may be a dir in newer cline
    ".ai": "agentmeld-or-generic",
}
COPILOT_PATH = ".github/copilot-instructions.md"
SIZE_BUCKETS = ["size:<500", "size:500..1500", "size:1500..3000", "size:3000..6000", "size:>6000"]


def get(url, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for attempt in range(6):
        req = urllib.request.Request(url, headers=HDR)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
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
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}")


def search_repos_with_file(filename: str, path_qualifier: str, max_repos: int) -> dict[str, dict]:
    """Stratified code search; returns {full_name: {bucket, seed_file}}."""
    repos: dict[str, dict] = {}
    quota = max(1, max_repos // len(SIZE_BUCKETS))
    for b in SIZE_BUCKETS:
        q = f"filename:{Path(filename).name} {path_qualifier} {b}"
        start = len(repos)
        for page in range(1, 11):
            data = get(f"{API}/search/code", {"q": q, "per_page": 100, "page": page})
            items = (data or {}).get("items", [])
            for it in items:
                if it.get("path") == filename:
                    r = it["repository"]
                    repos.setdefault(r["full_name"], {"bucket": b, "seed_file": filename, "fork": r.get("fork", False)})
            print(f"  [{q}] page {page}: {len(items)} items, {len(repos)} repos", file=sys.stderr)
            if len(items) < 100 or len(repos) - start >= quota:
                break
            time.sleep(6.5)
        time.sleep(6.5)
    return repos


def repo_meta(full_name: str) -> dict | None:
    d = get(f"{API}/repos/{full_name}")
    if not d:
        return None
    return {"fork": d.get("fork", False), "archived": d.get("archived", False), "pushed_at": d.get("pushed_at"),
            "created_at": d.get("created_at"), "stars": d.get("stargazers_count", 0),
            "default_branch": d.get("default_branch"), "language": d.get("language")}


def root_tree(full_name: str, branch: str) -> dict[str, dict]:
    d = get(f"{API}/repos/{full_name}/git/trees/{urllib.parse.quote(branch)}")
    if not d or "tree" not in d:
        return {}
    return {e["path"]: {"mode": e["mode"], "type": e["type"], "size": e.get("size"), "sha": e["sha"]} for e in d["tree"]}


def subtree(full_name: str, sha: str) -> list[str]:
    d = get(f"{API}/repos/{full_name}/git/trees/{sha}", {"recursive": 1})
    if not d or "tree" not in d:
        return []
    return [e["path"] for e in d["tree"] if e["type"] == "blob"]


def blob_text(full_name: str, sha: str, size: int | None, max_bytes: int) -> str | None:
    if size is not None and size > max_bytes:
        return None
    d = get(f"{API}/repos/{full_name}/git/blobs/{sha}")
    if not d or d.get("encoding") != "base64":
        return None
    return base64.b64decode(d["content"]).decode("utf-8", "replace")


def file_history(full_name: str, path: str) -> dict | None:
    """First/last commit dates, count (capped at 100), and shas for a later
    content-at-sha pass (RQ4)."""
    d = get(f"{API}/repos/{full_name}/commits", {"path": path, "per_page": 100})
    if not d or not isinstance(d, list):
        return None
    dates = [c["commit"]["committer"]["date"] for c in d if c.get("commit")]
    return {"n_commits": len(d), "capped": len(d) == 100,
            "first": dates[-1] if dates else None, "last": dates[0] if dates else None,
            "shas": [c["sha"] for c in d][:100]}


def classify_pair(primary: dict, secondary: dict, primary_name: str, secondary_name: str) -> str:
    """Mechanism by which `secondary` relates to `primary` (miner v2 taxonomy,
    generalised: the import directive is `@<primary>`)."""
    if secondary["mode"] == "120000":
        tgt = (secondary.get("target") or "")
        if not tgt and secondary.get("text") is not None and secondary.get("text") == primary.get("text"):
            tgt = primary_name  # contents API resolved the link; identical resolved text identifies the target
        return "symlink_to_primary" if tgt.endswith(primary_name) else "symlink_other"
    if primary["mode"] == "120000":
        tgt = (primary.get("target") or "")
        return "primary_symlink_to_secondary" if tgt.endswith(secondary_name) else "primary_symlink_other"
    st, pt = (secondary.get("text") or ""), (primary.get("text") or "")
    ss, ps = st.strip(), pt.strip()
    if ss.startswith("XSym") or ps.startswith("XSym"):
        return "corrupted_xsym"
    if ss in (primary_name, f"./{primary_name}") or ps in (secondary_name, f"./{secondary_name}"):
        return "corrupted_plain_pointer"
    if ss == f"@{primary_name}" or (len(ss) < 200 and f"@{primary_name}" in ss):
        return "import_pointer"
    if len(ss) < 400 and (primary_name in ss) and any(w in ss.lower() for w in ("see", "read", "follow", "refer")):
        return "prose_pointer"
    if not ss or not ps:
        return "unavailable"  # too large / binary / not fetched
    if ss == ps:
        return "identical"
    if len(pt) + len(st) < 60000:
        ratio = difflib.SequenceMatcher(None, pt, st, autojunk=False).ratio()
    else:
        ratio = difflib.SequenceMatcher(None, pt, st).ratio()
    if ratio >= 0.9:
        return "near_identical"
    if ratio >= 0.5:
        return "overlapping"
    return "distinct"


def mine_repo(full_name: str, seed: dict, args) -> dict:
    rec: dict = {"repo": full_name, "seed_file": seed.get("seed_file"), "bucket": seed.get("bucket")}
    meta = repo_meta(full_name)
    if not meta:
        rec["status"] = "gone"
        return rec
    rec.update(meta)
    cutoff = datetime.now(UTC) - timedelta(days=365)
    rec["active_12mo"] = bool(meta["pushed_at"]) and datetime.fromisoformat(meta["pushed_at"].replace("Z", "+00:00")) >= cutoff
    tree = root_tree(full_name, meta["default_branch"] or "HEAD")
    if not tree:
        rec["status"] = "no_tree"
        return rec

    files: dict[str, dict] = {}
    for name, tool in ROOT_FILES.items():
        e = tree.get(name)
        if e and e["type"] == "blob":
            files[name] = {"tool": tool, "mode": e["mode"], "size": e["size"], "sha": e["sha"]}
    dirs = {name: tool for name, tool in DIR_MARKERS.items() if name in tree and tree[name]["type"] == "tree"}
    rec["dirs"] = sorted(dirs.values())

    # Directory-based systems: list what is inside (cheap, one call each).
    for dname in (".cursor", ".github", ".claude"):
        if dname in tree and tree[dname]["type"] == "tree":
            paths = subtree(full_name, tree[dname]["sha"])
            if dname == ".cursor":
                rec["cursor_rules"] = sorted(p for p in paths if p.startswith("rules/"))
            elif dname == ".github":
                rec["copilot_instructions"] = "copilot-instructions.md" in paths
                rec["copilot_instruction_files"] = sorted(p for p in paths if p.startswith("instructions/"))
                if rec["copilot_instructions"]:
                    files[COPILOT_PATH] = {"tool": "copilot", "mode": "100644", "size": None, "sha": None}
            elif dname == ".claude":
                rec["claude_dir"] = sorted(paths)[:50]

    # Contents (symlink targets, text) for root instruction files.
    for name, f in files.items():
        if name == COPILOT_PATH:
            d = get(f"{API}/repos/{full_name}/contents/{urllib.parse.quote(name)}")
            if d and d.get("type") == "file" and d.get("encoding") == "base64":
                f["size"] = d.get("size"); f["sha"] = d.get("sha")
                f["text"] = base64.b64decode(d["content"]).decode("utf-8", "replace") if (d.get("size") or 0) <= args.max_file_bytes else None
            continue
        if f["mode"] == "120000":
            d = get(f"{API}/repos/{full_name}/contents/{urllib.parse.quote(name)}")
            f["target"] = (d or {}).get("target") if isinstance(d, dict) else None
            # contents API resolves the link; capture resolved text for pairing
            if isinstance(d, dict) and d.get("encoding") == "base64":
                f["text"] = base64.b64decode(d["content"]).decode("utf-8", "replace")
        else:
            f["text"] = blob_text(full_name, f["sha"], f["size"], args.max_file_bytes)

    # Pairs: AGENTS.md as primary against every other generic instruction file (RQ2, RQ6).
    pairs = {}
    generic = [n for n in ("CLAUDE.md", "GEMINI.md", COPILOT_PATH, "AGENT.md", "codex.md", ".cursorrules", ".windsurfrules", ".clinerules") if n in files]
    if "AGENTS.md" in files:
        for n in generic:
            pairs[f"AGENTS.md~{n}"] = classify_pair(files["AGENTS.md"], files[n], "AGENTS.md", n)
    if "CLAUDE.md" in files and "GEMINI.md" in files:
        pairs["CLAUDE.md~GEMINI.md"] = classify_pair(files["CLAUDE.md"], files["GEMINI.md"], "CLAUDE.md", "GEMINI.md")
    rec["pairs"] = pairs

    # RQ5 breakage: import pointing at a missing file.
    broken_imports = []
    for name, f in files.items():
        t = (f.get("text") or "")
        for tok in t.split():
            if tok.startswith("@") and tok.endswith(".md") and len(tok) < 60:
                target = tok[1:].lstrip("./")
                if target not in tree:
                    broken_imports.append({"in": name, "import": tok})
    rec["broken_imports"] = broken_imports

    # History (RQ1 trend, RQ4 drift).
    if not args.no_history:
        for name, f in files.items():
            h = file_history(full_name, name)
            if h:
                f["history"] = h

    rec["files"] = {n: {k: v for k, v in f.items() if k != "text"} for n, f in files.items()}
    rec["tools"] = sorted({f["tool"] for f in files.values()} | set(dirs.values()))
    rec["n_tools"] = len(rec["tools"])
    if args.keep_text:
        rec["texts"] = {n: f.get("text") for n, f in files.items()}
    rec["status"] = "ok"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="AGENTS.md,CLAUDE.md,GEMINI.md,.cursorrules,copilot-instructions.md")
    ap.add_argument("--max-repos-per-file", type=int, default=600)
    ap.add_argument("--max-repos", type=int, default=0, help="stop after this many repos mined (0 = all candidates)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "v3.jsonl"))
    ap.add_argument("--candidates", default=None, help="reuse a saved candidate list instead of searching")
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--keep-text", action="store_true", help="store file bodies (large; off by default)")
    ap.add_argument("--max-file-bytes", type=int, default=200_000)
    args = ap.parse_args()

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    cand_path = Path(args.candidates) if args.candidates else out.with_name(out.stem + "_candidates.json")
    if cand_path.exists():
        candidates = json.loads(cand_path.read_text())
        print(f"loaded {len(candidates)} candidates from {cand_path}", file=sys.stderr)
    else:
        candidates: dict[str, dict] = {}
        for fname in args.files.split(","):
            fname = fname.strip()
            if fname == "copilot-instructions.md":
                found = search_repos_with_file(COPILOT_PATH, "path:.github", args.max_repos_per_file)
            else:
                found = search_repos_with_file(fname, "path:/", args.max_repos_per_file)
            for k, v in found.items():
                candidates.setdefault(k, v)
            print(f"{fname}: {len(found)} repos; union {len(candidates)}", file=sys.stderr)
        cand_path.write_text(json.dumps(candidates, indent=1))

    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                done.add(json.loads(line)["repo"])
            except Exception:
                pass
    todo = [(k, v) for k, v in candidates.items() if k not in done]
    if args.max_repos:
        todo = todo[: args.max_repos]
    print(f"{len(candidates)} candidates, {len(done)} done, {len(todo)} to mine", file=sys.stderr)
    with out.open("a") as f:
        for i, (fn, seed) in enumerate(todo, 1):
            try:
                rec = mine_repo(fn, seed, args)
            except Exception as exc:  # keep going; record the failure
                rec = {"repo": fn, "status": f"error: {exc}"}
            f.write(json.dumps(rec) + "\n"); f.flush()
            if i % 20 == 0:
                print(f"  {i}/{len(todo)} mined", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
