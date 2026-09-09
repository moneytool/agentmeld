"""Stratified frame builder, second design.

The first design paid one API call to *count* each window before deciding
whether to split it, then more calls to harvest. But a search response already
carries `total_count`, so counting separately doubled the cost for no
information. This version uses fixed windows and learns the population size from
the harvest itself.

Cells are (star band x fixed date window). A cell that returns 1000 results is
flagged `truncated` -- GitHub will not serve past that, so those cells are
reported as a known limitation rather than silently sampled.
"""
import json, random, subprocess, sys, time, pathlib, datetime as dt

BANDS = [(10,25),(25,60),(60,150),(150,500),(500,2000),(2000,1000000)]
START, END, STEP = dt.date(2023,1,1), dt.date(2026,9,1), 14
STATE = pathlib.Path("/tmp/frame3/cells.json")
POOL  = pathlib.Path("/tmp/frame3/pool.json")

def gh(args, t=40):
    try: return subprocess.run(["gh"]+args, capture_output=True, text=True, timeout=t).stdout
    except Exception: return ""

def cells():
    if STATE.exists(): return json.loads(STATE.read_text())
    out=[]
    for lo,hi in BANDS:
        d=START
        while d < END:
            e=min(d+dt.timedelta(days=STEP-1), END)
            out.append({"band":f"{lo}-{hi}","lo":lo,"hi":hi,"from":str(d),"to":str(e),
                        "page":1,"done":False,"total":None,"truncated":False,"got":0})
            d=e+dt.timedelta(days=1)
    STATE.write_text(json.dumps(out, indent=1))
    return out

PER_BAND = 8   # randomly selected cells per star band

def select(cs, seed=20260908):
    """Cluster sample: choose whole cells at random within each band, then
    harvest each completely. Weighting uses each cell's recorded `total`, so the
    population estimate does not depend on which cells were drawn."""
    if any(c.get("selected") for c in cs):
        return cs
    rng=random.Random(seed)
    by={}
    for c in cs: by.setdefault(c["band"], []).append(c)
    for band, group in by.items():
        for c in rng.sample(group, min(PER_BAND, len(group))):
            c["selected"]=True
    for c in cs: c.setdefault("selected", False)
    STATE.write_text(json.dumps(cs, indent=1))
    return cs

def main():
    cs=select(cells())
    pool=json.loads(POOL.read_text()) if POOL.exists() else {}
    todo=[c for c in cs if c["selected"] and not c["done"]]
    sel=[c for c in cs if c["selected"]]
    print(f"  cells total {len(cs)}, selected {len(sel)}, remaining {len(todo)}, "
          f"pool {len(pool)}", file=sys.stderr)
    for c in todo:
        q=(f"stars:{c['lo']}..{c['hi']} fork:false archived:false "
           f"pushed:>2026-03-01 created:{c['from']}..{c['to']}")
        while not c["done"]:
            raw=gh(["api","-X","GET","search/repositories","-f",f"q={q}",
                    "-f","per_page=100","-f",f"page={c['page']}",
                    "--jq",'"\\(.total_count)", (.items[] | "\\(.full_name)\\t\\(.stargazers_count)")'])
            lines=[l for l in raw.split("\n") if l.strip()]
            if not lines:
                c["done"]=True; break
            if c["total"] is None and lines[0].isdigit():
                c["total"]=int(lines[0])          # population size, for free
            rows=lines[1:]
            for line in rows:
                if "\t" not in line: continue
                name,st=line.split("\t")
                pool[name]={"repo":name,"stars":int(st),"band":c["band"],
                            "cell":f"{c['band']}|{c['from']}"}
                c["got"]+=1
            c["page"]+=1
            if len(rows)<100: c["done"]=True
            elif c["page"]>10: c["done"]=True; c["truncated"]=True
            STATE.write_text(json.dumps(cs, indent=1))
            POOL.write_text(json.dumps(pool, indent=1))
            time.sleep(2.2)
        d=sum(1 for x in sel if x["done"])
        print(f"  {c['band']} {c['from']} n={c['total']} got={c['got']} "
              f"({d}/{len(sel)} selected) pool={len(pool)}", file=sys.stderr)
    print(f"  BUILD DONE selected={len(sel)} pool={len(pool)}", file=sys.stderr)

main()
