#!/usr/bin/env python3
import collections, json, statistics
recs=json.load(open('/tmp/frame3/pair_classified.json'))
meta={r['repo']:r for r in json.load(open('/tmp/frame3/pair_repos.json'))}
ORDER=['symlink','thin_import','import_plus_overlay','duplicate_exact',
       'duplicate_near','divergent','error']
LABEL={'symlink':'symlink (one file IS the other)',
       'thin_import':'thin import (@AGENTS.md, <=200B of own content)',
       'import_plus_overlay':'import + small overlay (<=1KB own content)',
       'duplicate_exact':'byte-identical copies',
       'duplicate_near':'near-identical (Jaccard >=0.90)',
       'divergent':'genuinely different content',
       'error':'could not classify'}
c=collections.Counter(r['class'] for r in recs)
n=len(recs); ok=n-c['error']
print(f"{n} repos carry both AGENTS.md and CLAUDE.md; {ok} classified\n")
print(f"{'class':<52}{'n':>5}{'% of classified':>17}")
for k in ORDER:
    if not c[k]: continue
    pct = '' if k=='error' else f"{c[k]/ok*100:>16.1f}%"
    print(f"{LABEL[k]:<52}{c[k]:>5}{pct}")

solved = c['symlink']+c['thin_import']
dup = c['duplicate_exact']+c['duplicate_near']
print(f"\nalready one source of truth : {solved:>4}  ({solved/ok*100:.1f}%)")
print(f"maintaining two copies      : {dup:>4}  ({dup/ok*100:.1f}%)")
print(f"deliberately different      : {c['divergent']:>4}  ({c['divergent']/ok*100:.1f}%)")
print(f"import + overlay            : {c['import_plus_overlay']:>4}  ({c['import_plus_overlay']/ok*100:.1f}%)")

print("\nby star band:")
band_tot=collections.Counter(); band_solved=collections.Counter(); band_dup=collections.Counter()
for r in recs:
    if r['class']=='error': continue
    b=meta[r['repo']]['band']; band_tot[b]+=1
    if r['class'] in ('symlink','thin_import'): band_solved[b]+=1
    if r['class'] in ('duplicate_exact','duplicate_near'): band_dup[b]+=1
for b in ['10-25','25-60','60-150','150-500','500-2000','2000-1000000']:
    if not band_tot[b]: continue
    print(f"  {b:<14}n={band_tot[b]:<4} solved {band_solved[b]/band_tot[b]*100:>5.1f}%   dup {band_dup[b]/band_tot[b]*100:>5.1f}%")

js=[r['jaccard'] for r in recs if 'jaccard' in r]
if js:
    print(f"\ntoken overlap between the two files (n={len(js)}):")
    print(f"  median {statistics.median(js):.3f}   mean {statistics.mean(js):.3f}")
    for lo,hi in [(0,.1),(.1,.3),(.3,.5),(.5,.7),(.7,.9),(.9,1.01)]:
        k=sum(1 for j in js if lo<=j<hi)
        print(f"  {lo:.1f}-{hi if hi<=1 else 1.0:.1f}  {k:>4}  {'#'*round(k/max(1,len(js))*50)}")

if c['error']:
    print("\nerrors:")
    for e,k in collections.Counter(r.get('error','?') for r in recs if r['class']=='error').most_common(8):
        print(f"  {k:>4}  {e}")
json.dump({'counts':dict(c),'classified':ok}, open('/tmp/frame3/pair_summary.json','w'), indent=1)
