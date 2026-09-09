"""Probe a frozen, reproducible sample for AI assistant configuration.

Sampling: within each star band, a deterministic random subsample (seed fixed)
of up to PER_BAND repos, drawn from the frozen pool. Bands are sampled equally
rather than proportionally, so each band gets usable precision; the overall
estimate is then weighted by the recorded band populations.

Parallel-safe: SLICE/NSLICE partition a *fixed* list, so slices are genuinely
disjoint (unlike the first attempt, where the pool grew mid-run).
"""
import json, os, pathlib, random, subprocess, sys, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor

PER_BAND = 800
FROZEN = json.loads(pathlib.Path("/tmp/frame3/frozen.json").read_text())
SLICE  = int(os.environ.get("SLICE","0")); NSLICE = int(os.environ.get("NSLICE","1"))
OUT    = pathlib.Path(os.environ.get("PROBE_OUT","/tmp/frame3/probed.json"))
LOCK   = threading.Lock()

FILES={"CLAUDE.md":"CLAUDE.md","AGENTS.md":"AGENTS.md","GEMINI.md":"GEMINI.md",
       "copilot_root":".github/copilot-instructions.md"}
DIRS ={"cursor_rules":".cursor/rules","copilot_rules":".github/instructions"}

def sample():
    by={}
    for r in FROZEN: by.setdefault(r["band"], []).append(r)
    out=[]
    for band in sorted(by):
        g=sorted(by[band], key=lambda r: r["repo"])       # deterministic base order
        rng=random.Random("agentmeld-2026-09-08|"+band)   # per-band fixed seed
        out += rng.sample(g, min(PER_BAND, len(g)))
    out.sort(key=lambda r: r["repo"])
    return out

def gh(a,t=20):
    try: return subprocess.run(["gh"]+a,capture_output=True,text=True,timeout=t).stdout
    except Exception: return ""
def has_file(repo,path):
    try:
        r=urllib.request.Request(f"https://raw.githubusercontent.com/{repo}/HEAD/{path}",method="HEAD")
        with urllib.request.urlopen(r,timeout=6) as x: return x.status==200
    except Exception: return False
def has_dir(repo,path):
    s=gh(["api",f"repos/{repo}/contents/{path}","--jq","length"]).strip()
    return s.isdigit() and int(s)>0

def main():
    target=sample()
    recs=json.loads(OUT.read_text()) if OUT.exists() else []
    seen={r["repo"] for r in recs}
    mine=[r for i,r in enumerate(target) if i%NSLICE==SLICE and r["repo"] not in seen]
    print(f"  sample {len(target)}  my slice {len(mine)} remaining", file=sys.stderr)
    def one(r):
        rec={"repo":r["repo"],"stars":r["stars"],"band":r["band"],"cell":r["cell"],"has":{}}
        for k,p in FILES.items(): rec["has"][k]=has_file(r["repo"],p)
        for k,p in DIRS.items():  rec["has"][k]=has_dir(r["repo"],p)
        rec["any"]=any(rec["has"].values())
        return rec
    with ThreadPoolExecutor(max_workers=8) as ex:
        for rec in ex.map(one, mine[:600]):
            with LOCK:
                recs.append(rec); OUT.write_text(json.dumps(recs))
            if len(recs)%50==0:
                h=sum(1 for x in recs if x["any"])
                print(f"  probed {len(recs)}  config {h} ({100*h/len(recs):.1f}%)", file=sys.stderr)
    print("  BATCH DONE", file=sys.stderr)

main()
