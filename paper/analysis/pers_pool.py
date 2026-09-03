import json,sys,collections,math
S=sys.argv[1]; J=sys.argv[2]
def mean(v): return sum(v)/len(v) if v else float('nan')
def sd(v):
    m=mean(v); return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1)) if len(v)>1 else float('nan')
def band(m,p):
    z=m*p
    return "blind-LOSS (mp<1)" if z<0.995 else ("knife-edge (mp=1)" if z<1.005 else "blind-GAIN (mp>1)")
H=collections.defaultdict(lambda: dict(pay=[],buys=[],hi=0,lo=0,rounds=0))
d=json.load(open(S+"/human_persuasion.json",encoding='utf-8'))
for g in d.values():
    c=g.get('config') or {}; me=g.get('your_player'); st=g.get('state') or {}
    if not ((me=='player_2')==(st.get('player_1_role')=='seller')): continue
    k=band(float(c['v']),float(c['p'])); e=H[k]
    pr=c.get('product_price') or 1
    pay=(g.get('result') or {}).get('player_2_payoff' if me=='player_2' else 'player_1_payoff')
    if pay is None: continue
    e['pay'].append(pay/pr); b=0
    for h in st.get('history') or []:
        e['rounds']+=1
        if h.get('bought'):
            b+=1; e['hi' if h.get('quality')=='high' else 'lo']+=1
    e['buys'].append(b)
A=collections.defaultdict(lambda: dict(pay=[],buys=[],rd=[],hi=0,lo=0,rounds=0))
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r['fam']!='persuasion' or r.get('role')!='buyer': continue
    k=band(float(r['m']),float(r['p'])); e=A[k]
    pr=r.get('price') or 1
    e['pay'].append((r.get('my_pay') or 0)/pr); e['buys'].append(r.get('buys') or 0); e['rd'].append(r['rd'])
print("=== PERSUASION BUYER, pooled by whether buying BLIND is profitable (m*p vs 1) ===\n")
print("%-20s | %6s %7s %8s %11s %8s | %7s %7s %11s" %
      ("regime","hu n","hu buy","hu hit","hu pay/pr","hu se","ag n","ag buy","ag pay/pr"))
for k in sorted(set(H)&set(A)):
    h,a=H[k],A[k]
    hp=h['pay']; ap=a['pay']
    hit=h['hi']/max(1,h['hi']+h['lo'])
    print("%-20s | %6d %7.1f %8.3f %11.2f %8.2f | %7d %7.1f %11.2f" %
          (k,len(hp),mean(h['buys']),hit,mean(hp),sd(hp)/math.sqrt(len(hp)),
           len(ap),mean(a['buys']),mean(ap)))
    t=(mean(hp)-mean(ap))/math.sqrt(sd(hp)**2/len(hp)+sd(ap)**2/len(ap))
    print("%-20s   difference %+0.2f price-units,  t = %+.2f" % ("",mean(hp)-mean(ap),t))
# agent overall hit rate from the replay corpus
hi=lo=0
for ln in open(sys.argv[3],encoding='utf-8'):
    g=json.loads(ln)
    for h in g.get('history') or []:
        if h.get('bought'):
            if h.get('quality')=='high': hi+=1
            elif h.get('quality')=='low': lo+=1
print("\nagent buyer hit rate on purchases: %.4f  (n=%d purchases)" % (hi/max(1,hi+lo),hi+lo))
