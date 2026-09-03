"""Validation of the break-even estimator + the field-vs-SPE comparison."""
import json, sys, collections, random, math

rows = collections.defaultdict(list)
for ln in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(ln)
    if r["fam"] != "bargaining" or r.get("d_them") is None or r.get("my_share") is None:
        continue
    key = ("open" if not r.get("hk") else "known", r["slot"], r["d_us"], r["d_them"])
    rows[key].append((float(r["my_share"]), float(r["rd"]), r["ts"]))

def fit(pairs):
    n=len(pairs); mx=sum(p[0] for p in pairs)/n; my=sum(p[1] for p in pairs)/n
    sxx=sum((p[0]-mx)**2 for p in pairs); sxy=sum((p[0]-mx)*(p[1]-my) for p in pairs)
    if sxx<=0 or abs(sxy)<1e-12: return None,None,None
    b=sxy/sxx; a=my-b*mx
    syy=sum((p[1]-my)**2 for p in pairs)
    r2=(sxy*sxy)/(sxx*syy) if syy>0 else 0.0
    return -a/b, b, r2

def spe(du,dt):
    den=1.0-du*dt
    return None if den<=1e-9 else (1.0-dt)/den

print("=== 1. MONOTONICITY: is rd increasing in banked share within a cell? ===")
pos=neg=0; r2s=[]
for k,v in rows.items():
    if len(v)<200: continue
    x,b,r2=fit(v)
    if b is None: continue
    (pos:=pos+1) if b>0 else (neg:=neg+1)
    r2s.append(r2)
r2s.sort()
print("  cells with positive slope: %d of %d   median R^2 = %.3f" % (pos,pos+neg,r2s[len(r2s)//2]))

print("\n=== 2. SPLIT-HALF STABILITY of the break-even estimate ===")
xs=[];ys=[]
for k,v in rows.items():
    if len(v)<400: continue
    v=sorted(v,key=lambda t:t[2]); h=len(v)//2
    a,_,_=fit(v[:h]); b,_,_=fit(v[h:])
    if a is None or b is None: continue
    if not(0<=a<=1.3 and 0<=b<=1.3): continue
    xs.append(a); ys.append(b)
def corr(x,y):
    n=len(x); mx=sum(x)/n; my=sum(y)/n
    sxy=sum((a-mx)*(b-my) for a,b in zip(x,y))
    sx=math.sqrt(sum((a-mx)**2 for a in x)); sy=math.sqrt(sum((b-my)**2 for b in y))
    return sxy/(sx*sy) if sx*sy>0 else 0
if xs: print("  first half vs second half: r = %.3f  (n=%d cells)" % (corr(xs,ys),len(xs)))

print("\n=== 3. FIELD MEDIAN vs RUBINSTEIN SPE ===")
inter=[];bound=[]
for k,v in sorted(rows.items()):
    hor,seat,du,dt=k
    if len(v)<200: continue
    x,_,_=fit(v)
    s=spe(du,dt)
    if x is None or s is None or not(0<=x<=1.3): continue
    (bound if (s<=1e-9 or s>=1.0-1e-9) else inter).append((x,s,k))
for tag,g in (("INTERIOR SPE (0<SPE<1)",inter),("BOUNDARY SPE (0 or 1)",bound)):
    if len(g)<3: continue
    xs=[a for a,_,_ in g]; ss=[b for _,b,_ in g]
    mad=sum(abs(a-b) for a,b in zip(xs,ss))/len(g)
    print("  %-24s n=%2d cells   r = %+.3f   mean |field - SPE| = %.3f"
          % (tag,len(g),corr(xs,ss),mad))
    if tag.startswith("BOUNDARY"):
        z=[a for a,b,_ in g if b<=1e-9]; o=[a for a,b,_ in g if b>=1.0-1e-9]
        if z: print("     SPE=0.000 -> field actually plays mean %.3f (n=%d)"%(sum(z)/len(z),len(z)))
        if o: print("     SPE=1.000 -> field actually plays mean %.3f (n=%d)"%(sum(o)/len(o),len(o)))

print("\n=== 4. OUR DEFICIT vs the field median, by horizon x seat ===")
agg=collections.defaultdict(list)
for k,v in rows.items():
    hor,seat,du,dt=k
    if len(v)<200: continue
    x,_,_=fit(v)
    if x is None or not(0<=x<=1.3): continue
    ours=sum(p[0] for p in v)/len(v)
    agg[(hor,seat)].append((ours-x,len(v)))
print("  %-6s %-9s %6s %10s %8s" % ("hor","seat","cells","mean gap","games"))
for k in sorted(agg):
    g=agg[k]; n=sum(c for _,c in g)
    print("  %-6s %-9s %6d %+10.3f %8d" % (k[0],k[1],len(g),sum(a for a,_ in g)/len(g),n))
