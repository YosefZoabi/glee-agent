"""Is the spread between identical builds larger than sampling error?"""
import json,sys,collections,math
J=sys.argv[1]
w=collections.defaultdict(lambda: collections.defaultdict(list))
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if not (r.get('ts') or '').startswith('2026-08-24T'): continue
    if r.get('rd') is None: continue
    w[r['fam']][r['agent']].append(r['rd'])
def mean(v): return sum(v)/len(v)
def sd(v):
    m=mean(v); return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
print("run44 window (2026-08-24): five agents, identical HEAD build\n")
print("%-12s %-16s %7s %9s %8s" % ("family","agent","n","rd/game","se"))
for fam in sorted(w):
    ms=[]; ses=[]
    for a in sorted(w[fam]):
        v=w[fam][a]
        if len(v)<300: continue
        m=mean(v); s=sd(v)/math.sqrt(len(v))
        ms.append(m); ses.append(s)
        print("%-12s %-16s %7d %+9.3f %8.3f" % (fam,a,len(v),m,s))
    if len(ms)>=4:
        obs=sd(ms); exp=math.sqrt(sum(s*s for s in ses)/len(ses))
        print("%-12s %-16s spread across builds: observed sd %.3f vs sampling sd %.3f  -> %.1fx"
              % ("","",obs,exp,obs/exp if exp>0 else float('nan')))
        print("%-12s %-16s implied resting-rating spread (rd/eta, eta=0.002): %.0f points\n"
              % ("","",(max(ms)-min(ms))/0.002))
