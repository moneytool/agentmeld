"""Real-world glob match ratios, v2: bigger sample, per-rule classification."""
import json, re, subprocess, sys, time, urllib.request
from pathlib import Path

def gh(args, timeout=60):
    try:
        return subprocess.run(["gh"]+args, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""

def search(q, pages=5):
    out=[]
    for p in range(1,pages+1):
        s=gh(["api","-X","GET","search/code","-f",f"q={q}","-f","per_page=100",
              "-f",f"page={p}","--jq",".items[].repository.full_name"])
        got=[x for x in s.split("\n") if x.strip()]
        out+=got
        if len(got)<100: break
        time.sleep(2.5)
    return out

def raw(repo,path):
    try:
        with urllib.request.urlopen(
            f"https://raw.githubusercontent.com/{repo}/HEAD/{path}",timeout=10) as fh:
            return fh.read().decode("utf-8","replace")
    except Exception:
        return None

def frontmatter(text):
    if not text.startswith("---"): return {}
    end=text.find("\n---",3)
    if end==-1: return {}
    fm={}; last=None
    for line in text[3:end].split("\n"):
        if re.match(r"^\s*-\s", line) and last:
            fm[last]=(fm[last]+"," if fm[last] else "")+line.strip()[1:].strip().strip('"\'')
        elif ":" in line:
            k,_,v=line.partition(":"); k=k.strip()
            fm[k]=v.strip().strip('"\''); last=k
    return fm

def globs_of(fm):
    g=(fm.get("globs") or fm.get("applyTo") or "").strip("[]")
    return [x.strip().strip('"\'') for x in g.split(",") if x.strip()]

def matches(glob,path):
    if glob in ("**","**/*","*"): return True
    rx=re.escape(glob).replace(r"\*\*/","(?:.*/)?").replace(r"\*\*",".*")
    rx=rx.replace(r"\*","[^/]*").replace(r"\?","[^/]")
    try: return re.match("^"+rx+"$",path) is not None
    except re.error: return False

CODE={".py",".js",".ts",".tsx",".jsx",".go",".rs",".java",".rb",".php",".c",".cpp",".cs",".swift",".kt"}
def tree(repo):
    s=gh(["api",f"repos/{repo}/git/trees/HEAD?recursive=1",
          "--jq",'.tree[] | select(.type=="blob") | .path'])
    files=[x for x in s.split("\n") if x.strip()]
    return [f for f in files if Path(f).suffix in CODE]

def rule_files(repo):
    out=[]
    for d in (".cursor/rules",".github/instructions"):
        s=gh(["api",f"repos/{repo}/contents/{d}",
              "--jq",'.[] | select(.type=="file") | .path'])
        out+=[x for x in s.split("\n") if x.strip() and (x.endswith(".mdc") or x.endswith(".md"))]
    return out

def main():
    queries=["path:.cursor/rules extension:mdc","path:.github/instructions extension:md",
             "filename:*.instructions.md","path:.cursor/rules alwaysApply"]
    repos=[]
    for q in queries:
        got=search(q); repos+=got
        print(f"  query '{q[:40]}': {len(got)}",file=sys.stderr)
    repos=sorted(set(repos))
    print(f"  unique candidate repos: {len(repos)}",file=sys.stderr)

    results=[]; rulestats={"total":0,"globs":0,"always":0,"desc_only":0,"dead":0}
    for i,repo in enumerate(repos):
        if len(results)>=320: break
        try:
            rfs=rule_files(repo)
            if len(rfs)<2: continue
            rules=[]
            for rf in rfs[:50]:
                txt=raw(repo,rf)
                if not txt: continue
                fm=frontmatter(txt); g=globs_of(fm)
                always=str(fm.get("alwaysApply","")).lower()=="true"
                desc=bool((fm.get("description") or "").strip())
                rules.append({"size":len(txt),"globs":g,"always":always,"desc":desc})
            if len(rules)<2: continue
            total=sum(r["size"] for r in rules)
            if total==0: continue
            files=tree(repo)
            if len(files)<5: continue
            for r in rules:
                rulestats["total"]+=1
                if r["always"]: rulestats["always"]+=1
                elif r["globs"]: rulestats["globs"]+=1
                elif r["desc"]: rulestats["desc_only"]+=1
                else: rulestats["dead"]+=1
            ratios=[]
            for f in files[:300]:
                m=sum(r["size"] for r in rules
                      if r["always"] or any(matches(g,f) for g in r["globs"]))
                ratios.append(m/total)
            ratios.sort()
            results.append({"repo":repo,"n_rules":len(rules),"total_chars":total,
                            "median_ratio":ratios[len(ratios)//2],
                            "n_files":len(files)})
            if len(results)%10==0:
                print(f"  {len(results)} repos measured",file=sys.stderr)
                json.dump({"repos":results,"rulestats":rulestats},
                          open("/tmp/ratio2/out.json","w"),indent=1)
        except Exception:
            continue
    json.dump({"repos":results,"rulestats":rulestats},open("/tmp/ratio2/out.json","w"),indent=1)
    print(f"  DONE {len(results)} repos, {rulestats['total']} rules",file=sys.stderr)

main()
