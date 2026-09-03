import json,sys,collections,math,random
J=sys.argv[1]
rd=collections.defaultdict(list); cells=collections.defaultdict(list)
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r.get('rd') is None: continue
    rd[r['fam']].append(r['rd'])
    if r['fam']=='bargaining' and r.get('d_them') is not None and r.get('my_share') is not None:
        cells[("open" if not r.get('hk') else "known", r['slot'], r['d_us'], r['d_them'])].append(
            (float(r['my_share']),float(r['rd'])))
def sd(v):
    m=sum(v)/len(v); return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
print("=== per-game rating-delta dispersion, and the sample a 3-sigma test needs ===")
print("%-12s %8s %8s %12s %12s" % ("family","n","sd(rd)","n for 0.25","n for 0.10"))
for f in sorted(rd):
    s=sd(rd[f])
    print("%-12s %8d %8.3f %12.0f %12.0f" % (f,len(rd[f]),s,(3*s*math.sqrt(2)/0.25)**2,(3*s*math.sqrt(2)/0.10)**2))
print("\n(two-arm comparison, 3 sigma, equal n per arm)")

print("\n=== SPLIT-HALF STABILITY of the break-even estimate (random halves) ===")
def fit(p):
    n=len(p); mx=sum(a for a,_ in p)/n; my=sum(b for _,b in p)/n
    sxx=sum((a-mx)**2 for a,_ in p); sxy=sum((a-mx)*(b-my) for a,b in p)
    if sxx<=0 or abs(sxy)<1e-12: return None
    b=sxy/sxx; return -(my-b*mx)/b
random.seed(11); xs=[];ys=[]
for k,v in cells.items():
    if len(v)<250: continue
    v=v[:]; random.shuffle(v); h=len(v)//2
    a=fit(v[:h]); b=fit(v[h:])
    if a is None or b is None or not(0<=a<=1.3 and 0<=b<=1.3): continue
    xs.append(a); ys.append(b)
n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
sxy=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
r=sxy/(math.sqrt(sum((a-mx)**2 for a in xs))*math.sqrt(sum((b-my)**2 for b in ys)))
print("  r = %.3f over %d cells (~125 games per half)" % (r,n))
print("  mean |half A - half B| = %.3f of pot" % (sum(abs(a-b) for a,b in zip(xs,ys))/n))
