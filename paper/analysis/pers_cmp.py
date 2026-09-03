import json,sys,collections
S=sys.argv[1]; J=sys.argv[2]
def mean(v): return sum(v)/len(v) if v else float('nan')
# ---- agent buyer cells
A=collections.defaultdict(lambda: dict(pay=[],rd=[],neg=[],zer=[],pos=[],buys=[]))
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r['fam']!='persuasion' or r.get('role')!='buyer': continue
    k=(float(r['m']),round(float(r['p']),3)); e=A[k]
    pr=r.get('price') or 1; pay=(r.get('my_pay') or 0)/pr
    e['pay'].append(pay); e['rd'].append(r['rd']); e['buys'].append(r.get('buys') or 0)
    (e['neg'] if pay<-1e-9 else e['zer'] if abs(pay)<=1e-9 else e['pos']).append(r['rd'])
# ---- human buyer cells
H=collections.defaultdict(lambda: dict(pay=[],buys=[],rounds=0,hi=0,lo=0))
d=json.load(open(S+"/human_persuasion.json",encoding='utf-8'))
hist={h['game_id']:h for h in json.load(open(S+"/human_hist_full.json",encoding='utf-8'))}
for g in d.values():
    c=g.get('config') or {}; me=g.get('your_player'); st=g.get('state') or {}
    if not ((me=='player_2')==(st.get('player_1_role')=='seller')): continue
    k=(float(c['v']),round(float(c['p']),3)); e=H[k]
    pr=c.get('product_price') or 1
    res=g.get('result') or {}
    pay=res.get('player_2_payoff' if me=='player_2' else 'player_1_payoff')
    if pay is None: continue
    e['pay'].append(pay/pr); b=0
    for h in st.get('history') or []:
        e['rounds']+=1
        if h.get('bought'):
            b+=1
            if h.get('quality')=='high': e['hi']+=1
            else: e['lo']+=1
    e['buys'].append(b)

print("=== PERSUASION BUYER: what the payoff is WORTH in rating (agent's own games) ===")
print("%-5s %-6s %8s | %8s %8s | %8s %8s | %8s %8s" %
      ("m","p","n","neg n","rd|neg","zero n","rd|zero","pos n","rd|pos"))
for k in sorted(A):
    e=A[k]
    if len(e['pay'])<400: continue
    print("%-5s %-6.3f %8d | %8d %+8.3f | %8d %+8.3f | %8d %+8.3f" %
          (k[0],k[1],len(e['pay']),len(e['neg']),mean(e['neg']) if e['neg'] else float('nan'),
           len(e['zer']),mean(e['zer']),len(e['pos']),mean(e['pos'])))

print("\n=== HUMAN vs AGENT buyer: purchases and realised payoff, per cell ===")
print("%-5s %-6s | %5s %7s %8s %10s | %7s %7s %10s | %10s" %
      ("m","p","hu n","hu buy","hu hit","hu pay/pr","ag n","ag buy","ag pay/pr","who wins"))
hw=aw=0
for k in sorted(set(H)&set(A)):
    h,a=H[k],A[k]
    if len(h['pay'])<10 or len(a['pay'])<400: continue
    hb=mean(h['buys']); ab=mean(a['buys'])
    hit=h['hi']/max(1,h['hi']+h['lo'])
    hp,ap=mean(h['pay']),mean(a['pay'])
    w="human" if hp>ap else "agent"
    hw+= hp>ap; aw+= hp<=ap
    print("%-5s %-6.3f | %5d %7.1f %7.3f %10.2f | %7d %7.1f %10.2f | %10s"
          % (k[0],k[1],len(h['pay']),hb,hit,hp,len(a['pay']),ab,ap,w))
print("\n  human banks more in %d of %d cells, agent in %d" % (hw,hw+aw,aw))
