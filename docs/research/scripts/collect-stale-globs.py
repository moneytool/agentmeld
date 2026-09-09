"""Stale globs, with brace expansion handled and failures classified."""
import json, re, subprocess, sys, time, urllib.request

def gh(a,t=60):
    try: return subprocess.run(["gh"]+a,capture_output=True,text=True,timeout=t).stdout
    except Exception: return ""
def search(q,pages=4):
    o=[]
    for p in range(1,pages+1):
        s=gh(["api","-X","GET","search/code","-f",f"q={q}","-f","per_page=100","-f",f"page={p}",
              "--jq",".items[].repository.full_name"])
        g=[x for x in s.split("\n") if x.strip()]; o+=g
        if len(g)<100: break
        time.sleep(2.5)
    return o
def raw(r,p):
    try:
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{r}/HEAD/{p}",timeout=10) as f:
            return f.read().decode("utf-8","replace")
    except Exception: return None

def parse_globs(text):
    """Extract the raw globs value, keeping {a,b} braces intact."""
    if not text.startswith("---"): return []
    end=text.find("\n---",3)
    if end==-1: return []
    body=text[3:end]
    m=re.search(r"^(?:globs|applyTo):(.*)$", body, re.M)
    if not m: return []
    val=m.group(1).strip()
    items=[]
    if val:
        # split on commas that are NOT inside {...}
        depth=0; cur=""
        for ch in val.strip("[]"):
            if ch=="{": depth+=1
            if ch=="}": depth-=1
            if ch=="," and depth==0:
                items.append(cur); cur=""
            else: cur+=ch
        items.append(cur)
    else:  # YAML list form
        for line in body[m.end():].split("\n"):
            if re.match(r"^\s*-\s", line): items.append(line.strip()[1:])
            elif line.strip() and not line.startswith(" "): break
    return [x.strip().strip('"\'') for x in items if x.strip()]

def expand(g):
    """{js,ts} -> two patterns."""
    m=re.search(r"\{([^}]*)\}", g)
    if not m: return [g]
    out=[]
    for opt in m.group(1).split(","):
        out += expand(g[:m.start()]+opt.strip()+g[m.end():])
    return out

def match(g,p):
    if g in ("**","**/*","*"): return True
    rx=re.escape(g).replace(r"\*\*/","(?:.*/)?").replace(r"\*\*",".*")
    rx=rx.replace(r"\*","[^/]*").replace(r"\?","[^/]")
    try: return re.match("^"+rx+"$",p) is not None
    except re.error: return False

def files(r):
    s=gh(["api",f"repos/{r}/git/trees/HEAD?recursive=1","--jq",'.tree[]|select(.type=="blob")|.path'])
    return [x for x in s.split("\n") if x.strip()]
def rules_of(r):
    o=[]
    for d in (".cursor/rules",".github/instructions"):
        s=gh(["api",f"repos/{r}/contents/{d}","--jq",'.[]|select(.type=="file")|.path'])
        o+=[x for x in s.split("\n") if x.strip() and (x.endswith(".mdc") or x.endswith(".md"))]
    return o

def classify(gs, fl):
    """Why did this rule match nothing?"""
    pats=[p for g in gs for p in expand(g)]
    if any(any(match(p,f) for f in fl) for p in pats):
        return None                                  # not stale after all
    # would it match if the author had written **/ ?
    for p in pats:
        if "/" not in p and p.startswith("*."):
            if any(match("**/"+p,f) for f in fl):
                return "missing_globstar"            # *.ts written where **/*.ts was meant
    return "path_absent"                             # scoped to something that isn't there

def main():
    repos=sorted(set(search("path:.cursor/rules extension:mdc")+search("path:.github/instructions extension:md")))
    st={"repos":0,"scoped":0,"missing_globstar":0,"path_absent":0,"repos_affected":0}
    ex={"missing_globstar":[], "path_absent":[]}
    for repo in repos:
        if st["repos"]>=110: break
        try:
            rfs=rules_of(repo)
            if not rfs: continue
            fl=files(repo)
            if len(fl)<10: continue
            scoped=[]
            for rf in rfs[:40]:
                t=raw(repo,rf)
                if not t: continue
                g=parse_globs(t)
                if g: scoped.append((rf,g))
            if not scoped: continue
            st["repos"]+=1; hit=False
            for rf,gs in scoped:
                st["scoped"]+=1
                c=classify(gs,fl)
                if c:
                    st[c]+=1; hit=True
                    if len(ex[c])<8: ex[c].append({"repo":repo,"rule":rf.split("/")[-1],"globs":gs[:3]})
            if hit: st["repos_affected"]+=1
            if st["repos"]%10==0:
                json.dump({"stats":st,"examples":ex},open("/tmp/stale2/out.json","w"),indent=1)
                print(f"  {st['repos']} repos, {st['missing_globstar']}+{st['path_absent']}/{st['scoped']}",file=sys.stderr)
        except Exception: continue
    json.dump({"stats":st,"examples":ex},open("/tmp/stale2/out.json","w"),indent=1)
    print(f"  DONE {st}",file=sys.stderr)
main()
