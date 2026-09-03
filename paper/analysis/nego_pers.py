import json, sys, collections, math, random
J=sys.argv[1]
neg=[]; per=[]; bar=[]
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r['fam']=='negotiation': neg.append(r)
    elif r['fam']=='persuasion': per.append(r)
    else: bar.append(r)

def mean(v): return sum(v)/len(v) if v else float('nan')
def se(v):
    n=len(v)
    if n<2: return float('nan')
    m=mean(v); return math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n)

print("=== NEGOTIATION: rating per game by horizon x information x role ===")
print("  %-4s %-9s %-7s %7s %9s %8s %10s" % ("mxr","info","role","n","rd/game","se","agree%"))
g=collections.defaultdict(list)
for r in neg:
    k=(r.get('max_rounds'), 'complete' if r.get('ci') else 'hidden', r.get('role'))
    g[k].append(r)
for k in sorted(g, key=lambda k:(k[0] or 0,k[1],k[2] or '')):
    v=g[k]
    if len(v)<200: continue
    rds=[x['rd'] for x in v if x.get('rd') is not None]
    ag=sum(1 for x in v if x.get('outcome')=='agreement')/len(v)
    print("  %-4s %-9s %-7s %7d %+9.3f %8.3f %9.1f%%" % (k[0],k[1],k[2],len(v),mean(rds),se(rds),100*ag))

print("\n=== NEGOTIATION: complete-info seller, where does the surplus go? ===")
for mx in (1,10,12,None):
    v=[r for r in neg if r.get('max_rounds')==mx and r.get('ci') and r.get('role')=='seller'
       and r.get('my_val') is not None and r.get('their_val') is not None]
    if len(v)<80: continue
    cap=[]; 
    for r in v:
        s=r['their_val']-r['my_val']
        if s>0 and r.get('my_pay') is not None: cap.append(r['my_pay']/s)
    rds=[r['rd'] for r in v]
    ag=sum(1 for r in v if r['outcome']=='agreement')/len(v)
    print("  max_rounds=%-5s n=%-5d rd/game %+7.3f  agree %5.1f%%  surplus captured %.3f"
          % (mx,len(v),mean(rds),100*ag,mean(cap) if cap else float('nan')))

print("\n=== PERSUASION: buyer, rating vs banked payoff (does zero cost us?) ===")
by=collections.defaultdict(list)
for r in per:
    if r.get('role')!='buyer' or r.get('rd') is None: continue
    by[(r.get('m'),r.get('p'))].append(r)
print("  %-6s %-6s %7s %9s %9s %9s" % ("m","p","n","zero%","rd|zero","rd|pos"))
for k in sorted(by, key=lambda k:(k[0] or 0,k[1] or 0)):
    v=by[k]
    if len(v)<250: continue
    z=[r['rd'] for r in v if (r.get('my_pay') or 0)<=0]
    q=[r['rd'] for r in v if (r.get('my_pay') or 0)>0]
    if len(z)<20 or len(q)<20: continue
    print("  %-6s %-6.3f %7d %8.1f%% %+9.3f %+9.3f" % (k[0],k[1],len(v),100*len(z)/len(v),mean(z),mean(q)))

print("\n=== NOISE FLOOR: five near-identical builds, same window ===")
# restrict to a window where all five ran the same HEAD (run44: 2026-08-24)
w=[r for r in bar if '2026-08-24T' in (r.get('ts') or '') and r.get('my_share') is not None]
ag=collections.defaultdict(list)
for r in w: ag[r['agent']].append(r)
print("  %-16s %7s %10s %10s" % ("agent","n","share","rd/game"))
sh=[]
for a in sorted(ag):
    v=ag[a]
    if len(v)<150: continue
    s=mean([x['my_share'] for x in v]); sh.append(s)
    print("  %-16s %7d %10.4f %+10.3f" % (a,len(v),s,mean([x['rd'] for x in v])))
if len(sh)>=3:
    m=mean(sh); sd=math.sqrt(sum((x-m)**2 for x in sh)/(len(sh)-1))
    print("  --> spread across identical builds: mean %.4f, sd %.4f, range %.4f"
          % (m,sd,max(sh)-min(sh)))
