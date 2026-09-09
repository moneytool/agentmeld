"""Collect AI-assistant config co-occurrence and divergence across public repos."""
import json, subprocess, sys, time, urllib.request, difflib, re
from pathlib import Path

CONFIGS = {
    "CLAUDE.md": "CLAUDE.md",
    "AGENTS.md": "AGENTS.md",
    "copilot": ".github/copilot-instructions.md",
    "GEMINI.md": "GEMINI.md",
    "cursorrules": ".cursorrules",
}
OUT = Path("/tmp/study/data.json")

def search_repos(filename, pages=4):
    repos = []
    for p in range(1, pages + 1):
        try:
            r = subprocess.run(
                ["gh", "api", "-X", "GET", "search/code",
                 "-f", f"q=filename:{filename}", "-f", "per_page=100", "-f", f"page={p}",
                 "--jq", ".items[].repository.full_name"],
                capture_output=True, text=True, timeout=60)
            got = [x for x in r.stdout.split("\n") if x.strip()]
            repos += got
            if len(got) < 100:
                break
        except Exception as e:
            print("search fail", filename, p, e, file=sys.stderr)
            break
        time.sleep(2.5)          # search API: 30 req/min
    return repos

def fetch(repo, path):
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
    try:
        with urllib.request.urlopen(url, timeout=12) as fh:
            return fh.read().decode("utf-8", "replace")
    except Exception:
        return None

def norm(t):
    t = t.lower()
    t = re.sub(r"```.*?```", " ", t, flags=re.S)   # code blocks vary for unrelated reasons
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(t.split())

def similarity(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return {"seq": round(seq, 4), "jaccard": round(jac, 4)}

def main():
    seen = []
    for name, path in CONFIGS.items():
        got = search_repos(Path(path).name)
        print(f"  {name}: {len(got)} hits", file=sys.stderr)
        seen += got
    repos = sorted(set(seen))
    print(f"  unique repos: {len(repos)}", file=sys.stderr)

    records = []
    for i, repo in enumerate(repos):
        present = {}
        for name, path in CONFIGS.items():
            c = fetch(repo, path)
            if c is not None and c.strip():
                present[name] = c
        if not present:
            continue
        rec = {"repo": repo, "has": sorted(present), "count": len(present),
               "sizes": {k: len(v) for k, v in present.items()}, "pairs": {}}
        keys = sorted(present)
        for a in range(len(keys)):
            for b in range(a + 1, len(keys)):
                ka, kb = keys[a], keys[b]
                rec["pairs"][f"{ka}|{kb}"] = {
                    "identical": present[ka].strip() == present[kb].strip(),
                    **similarity(present[ka], present[kb]),
                }
        records.append(rec)
        if i % 25 == 0:
            print(f"  processed {i}/{len(repos)}", file=sys.stderr)
            OUT.write_text(json.dumps(records, indent=1))
    OUT.write_text(json.dumps(records, indent=1))
    print(f"  DONE: {len(records)} repos with >=1 config", file=sys.stderr)

main()
